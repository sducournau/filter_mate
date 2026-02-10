"""
DockwidgetSignalManager - Extracted from filter_mate_dockwidget.py

v5.0 Phase 2 Sprint 2.1: Extract signal management from God Class.
Manages PyQt signal connections/disconnections for FilterMate dockwidget.

This module extracts ~570 lines of signal management code from the
filter_mate_dockwidget.py God Class (6,930 lines → target: 2,500 lines).

Key Methods:
    - getSignal: Get PyQt signal object from widget
    - manageSignal: Main signal connection/disconnection handler
    - changeSignalState: Low-level signal state change
    - connect_widgets_signals: Connect all widget signals
    - disconnect_widgets_signals: Disconnect all widget signals
    - force_reconnect_*: Force reconnection bypassing cache

Author: FilterMate Team
Created: January 2026
"""

import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from qgis.PyQt.QtCore import QObject

from ...core.domain.exceptions import SignalStateChangeError  # noqa: F401

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class DockwidgetSignalManager:
    """
    Manages PyQt signal connections/disconnections for FilterMate dockwidget.

    Extracted from filter_mate_dockwidget.py to reduce God Class complexity.
    This manager handles:
    - Signal connection state tracking via cache
    - Safe connect/disconnect operations
    - Force reconnection when cache becomes stale
    - Layer-specific signal management

    Attributes:
        dockwidget: Reference to the parent FilterMateDockWidget
        _signal_connection_states: Cache of signal connection states
        _layer_tree_view_signal_connected: Track LAYER_TREE_VIEW signal state
    """

    def __init__(self, dockwidget: "FilterMateDockWidget"):
        """
        Initialize DockwidgetSignalManager.

        Args:
            dockwidget: Parent FilterMateDockWidget instance
        """
        self.dockwidget = dockwidget
        self._signal_connection_states: Dict[str, bool] = {}
        self._layer_tree_view_signal_connected: bool = False

    @property
    def widgets(self) -> Dict[str, Dict[str, Any]]:
        """Access dockwidget's widgets dictionary."""
        return self.dockwidget.widgets

    @property
    def widgets_initialized(self) -> bool:
        """Check if widgets are initialized."""
        return getattr(self.dockwidget, 'widgets_initialized', False)

    def get_signal(self, obj: QObject, signal_name: str) -> Any:
        """
        Get PyQt signal object from widget.

        Args:
            obj: QObject containing the signal
            signal_name: Name of the signal attribute

        Returns:
            The signal object (QMetaMethod index)
        """
        return obj.metaObject().method(
            obj.metaObject().indexOfSignal(
                obj.metaObject().normalizedSignature(f"{signal_name}()")
            )
        )

    def manage_signal(
        self,
        widget_path: List[str],
        custom_action: Optional[str] = None,
        custom_signal_name: Optional[str] = None
    ) -> Optional[bool]:
        """
        Main signal management handler.

        Manages signal connection/disconnection with caching to prevent
        redundant operations.

        Args:
            widget_path: List of [category, widget_name] e.g., ["EXPLORING", "SINGLE_SELECTION_FEATURES"]
            custom_action: 'connect', 'disconnect', or None (toggle)
            custom_signal_name: Specific signal name to manage, or None for all signals

        Returns:
            Final connection state, or True if no signals to process

        Raises:
            SignalStateChangeError: If widget_path format is incorrect
        """
        if not isinstance(widget_path, list) or len(widget_path) != 2:
            raise SignalStateChangeError(None, widget_path, 'Incorrect input parameters')

        widget_object = self.widgets[widget_path[0]][widget_path[1]]
        state = None

        # Get signals to process: (signal_name, handler_func)
        signals_to_process = [
            (s[0], s[-1]) for s in widget_object["SIGNALS"]
            if s[-1] is not None and (custom_signal_name is None or s[0] == custom_signal_name)
        ]

        logger.debug(
            f"manageSignal: {widget_path} | action={custom_action} | "
            f"signal={custom_signal_name} | signals_to_process={len(signals_to_process)}"
        )

        for signal_name, func in signals_to_process:
            state_key = f"{widget_path[0]}.{widget_path[1]}.{signal_name}"
            cached = self._signal_connection_states.get(state_key)

            logger.debug(
                f"  Signal '{signal_name}' | state_key={state_key} | "
                f"cached={cached} | action={custom_action}"
            )

            # Skip if already in desired state
            if (custom_action == 'connect' and cached is True) or \
               (custom_action == 'disconnect' and cached is False):
                state = cached
                logger.debug("  -> SKIP (already in desired state)")
                continue

            # Change state and update cache
            state = self.change_signal_state(widget_path, signal_name, func, custom_action)
            self._signal_connection_states[state_key] = state
            logger.debug(f"  -> Changed state to {state}")

        return True if state is None and widget_object["SIGNALS"] else state

    def change_signal_state(
        self,
        widget_path: List[str],
        signal_name: str,
        func: Callable,
        custom_action: Optional[str] = None
    ) -> bool:
        """
        Change signal connection state.

        Low-level method that actually connects/disconnects signals.

        Args:
            widget_path: List of [category, widget_name]
            signal_name: Name of the signal to modify
            func: Handler function to connect/disconnect
            custom_action: 'connect', 'disconnect', or None (toggle)

        Returns:
            New connection state (True = connected, False = disconnected)

        Raises:
            SignalStateChangeError: If widget_path format is incorrect or signal not found
        """
        if not isinstance(widget_path, list) or len(widget_path) != 2:
            raise SignalStateChangeError(None, widget_path)

        widget = self.widgets[widget_path[0]][widget_path[1]]["WIDGET"]

        if not hasattr(widget, signal_name):
            raise SignalStateChangeError(None, widget_path)

        is_ltv = widget_path == ["QGIS", "LAYER_TREE_VIEW"]

        # Get current state
        if is_ltv:
            state = self._layer_tree_view_signal_connected
        else:
            state = widget.isSignalConnected(self.get_signal(widget, signal_name))

        signal = getattr(widget, signal_name)
        should_connect = (custom_action == 'connect' and not state) or (custom_action is None and not state)
        should_disconnect = (custom_action == 'disconnect' and state) or (custom_action is None and state)

        # Perform connection/disconnection
        try:
            if should_disconnect:
                signal.disconnect(func)
                if is_ltv:
                    self._layer_tree_view_signal_connected = False
            elif should_connect:
                signal.connect(func)
                if is_ltv:
                    self._layer_tree_view_signal_connected = True
        except TypeError:
            # Signal was not connected or already in desired state
            pass

        # Return current state
        if is_ltv:
            return self._layer_tree_view_signal_connected
        else:
            return widget.isSignalConnected(self.get_signal(widget, signal_name))

    def connect_widgets_signals(self) -> None:
        """
        Connect all widget signals.

        Iterates through all widget categories (except QGIS) and connects
        their signals via manage_signal.
        """
        for grp in [g for g in self.widgets if g != 'QGIS']:
            for w in self.widgets[grp]:
                try:
                    self.manage_signal([grp, w], 'connect')
                except Exception:
                    # Signal may already be connected - expected
                    pass

    def disconnect_widgets_signals(self) -> None:
        """
        Disconnect all widget signals.

        Safely iterates through all widget categories (except QGIS) and
        disconnects their signals.
        """
        if not self.widgets:
            return

        for grp in [g for g in self.widgets if g != 'QGIS']:
            for w in self.widgets[grp]:
                try:
                    self.manage_signal([grp, w], 'disconnect')
                except Exception:
                    # Signal may already be disconnected - expected
                    pass

    def disconnect_layer_signals(self) -> List[List[str]]:
        """
        Disconnect all layer-related widget signals before updating.

        FIX 2026-01-15 (BUGFIX-COMBOBOX-20260115): CURRENT_LAYER signal NOT disconnected.
        Reason: User can change layer during update. Lock _updating_current_layer prevents reentrancy.

        Returns:
            List of widget paths that were disconnected (for reconnection later)
        """
        exploring = [
            "SINGLE_SELECTION_FEATURES", "SINGLE_SELECTION_EXPRESSION",
            "MULTIPLE_SELECTION_FEATURES", "MULTIPLE_SELECTION_EXPRESSION",
            "CUSTOM_SELECTION_EXPRESSION", "IDENTIFY", "ZOOM",
            "IS_SELECTING", "IS_TRACKING", "IS_LINKING", "RESET_ALL_LAYER_PROPERTIES"
        ]
        # FIX 2026-01-15: CURRENT_LAYER removed - must stay connected for user interaction
        filtering = [
            "HAS_LAYERS_TO_FILTER", "LAYERS_TO_FILTER", "HAS_COMBINE_OPERATOR",
            "SOURCE_LAYER_COMBINE_OPERATOR", "OTHER_LAYERS_COMBINE_OPERATOR",
            "HAS_GEOMETRIC_PREDICATES", "GEOMETRIC_PREDICATES", "HAS_BUFFER_VALUE",
            "BUFFER_VALUE", "BUFFER_VALUE_PROPERTY", "HAS_BUFFER_TYPE", "BUFFER_TYPE"
        ]
        widgets_to_stop = [["EXPLORING", w] for w in exploring] + [["FILTERING", w] for w in filtering]

        for wp in widgets_to_stop:
            self.manage_signal(wp, 'disconnect')

        # Clear expression widgets
        for expr_key in ["SINGLE_SELECTION_EXPRESSION", "MULTIPLE_SELECTION_EXPRESSION", "CUSTOM_SELECTION_EXPRESSION"]:
            try:
                widget = self.widgets.get("EXPLORING", {}).get(expr_key, {}).get("WIDGET")
                if widget and hasattr(widget, 'setExpression'):
                    widget.setExpression("")
            except Exception:
                # Widget may not be ready - expected during initialization
                pass

        # Disconnect LAYER_TREE_VIEW if linked
        project_props = getattr(self.dockwidget, 'project_props', {})
        if project_props.get("OPTIONS", {}).get("LAYERS", {}).get("LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"):
            self.manage_signal(["QGIS", "LAYER_TREE_VIEW"], 'disconnect')

        return widgets_to_stop

    def force_reconnect_action_signals(self) -> None:
        """
        Force reconnect ACTION button signals bypassing cache.

        FIX 2026-01-17 v4: Uses DIRECT method references instead of stored lambdas.
        Stored lambdas in widgets['ACTION'][x]['SIGNALS'] may become stale references
        when widgets dict is recreated. By using direct method wrappers, we ensure
        the connection is always to the current dockwidget instance.
        """
        # Map button names to their task names and widgets
        action_buttons = {
            'FILTER': ('filter', getattr(self.dockwidget, 'pushButton_action_filter', None)),
            'UNFILTER': ('unfilter', getattr(self.dockwidget, 'pushButton_action_unfilter', None)),
            'UNDO_FILTER': ('undo', getattr(self.dockwidget, 'pushButton_action_undo_filter', None)),
            'REDO_FILTER': ('redo', getattr(self.dockwidget, 'pushButton_action_redo_filter', None)),
            'EXPORT': ('export', getattr(self.dockwidget, 'pushButton_action_export', None)),
        }

        connected_count = 0
        for btn_name, (task_name, widget) in action_buttons.items():
            if not widget:
                continue

            key = f"ACTION.{btn_name}.clicked"
            self._signal_connection_states.pop(key, None)

            try:
                # Disconnect ALL receivers to ensure clean state
                try:
                    widget.clicked.disconnect()
                except TypeError:
                    pass  # No receivers connected, which is fine

                # Connect using a closure that captures task_name
                def make_handler(task):
                    """Factory function to create handler with properly captured task name."""
                    def handler(state=False):
                        self.dockwidget.launchTaskEvent(state, task)
                    return handler

                handler = make_handler(task_name)
                widget.clicked.connect(handler)
                self._signal_connection_states[key] = True
                connected_count += 1
            except Exception as e:
                logger.warning(f"force_reconnect_action_signals: Failed to connect {btn_name}: {e}")

        logger.debug(f"force_reconnect_action_signals: {connected_count}/5 signals connected")

    def force_reconnect_exporting_signals(self) -> None:
        """
        Force reconnect EXPORTING signals for file/folder selection buttons.

        FIX 2026-01-22: Connects pushButton_checkable_exporting_output_folder and
        pushButton_checkable_exporting_zip clicked signals to their respective
        dialog handlers.
        """
        if 'EXPORTING' not in self.widgets:
            logger.warning("force_reconnect_exporting_signals: EXPORTING category not in widgets")
            return

        # Map widget names to their handlers
        exporting_buttons = {
            'HAS_OUTPUT_FOLDER_TO_EXPORT': (
                'dialog_export_output_path',
                getattr(self.dockwidget, 'pushButton_checkable_exporting_output_folder', None)
            ),
            'HAS_ZIP_TO_EXPORT': (
                'dialog_export_output_pathzip',
                getattr(self.dockwidget, 'pushButton_checkable_exporting_zip', None)
            ),
        }

        connected_count = 0
        for btn_name, (handler_name, widget) in exporting_buttons.items():
            if not widget:
                logger.debug(f"force_reconnect_exporting_signals: {btn_name} widget not found")
                continue

            # Get handler method
            handler_method = getattr(self.dockwidget, handler_name, None)
            if not handler_method:
                logger.warning(f"force_reconnect_exporting_signals: Handler {handler_name} not found")
                continue

            # Clear cache
            key = f"EXPORTING.{btn_name}.clicked"
            self._signal_connection_states.pop(key, None)

            try:
                # Disconnect all existing receivers
                try:
                    widget.clicked.disconnect()
                except TypeError:
                    pass  # No receivers connected

                # Create handler with proper closure
                def make_handler(handler_func, prop_name):
                    """Factory to create handler with proper closure."""
                    def handler(checked):
                        logger.debug(f"EXPORTING handler triggered: {prop_name}, checked={checked}")
                        handler_func()
                    return handler

                property_name = 'has_output_folder_to_export' if btn_name == 'HAS_OUTPUT_FOLDER_TO_EXPORT' else 'has_zip_to_export'
                handler = make_handler(handler_method, property_name)
                widget.clicked.connect(handler)
                self._signal_connection_states[key] = True
                connected_count += 1
                logger.debug(f"force_reconnect_exporting_signals: Connected {btn_name}.clicked")
            except Exception as e:
                logger.warning(f"force_reconnect_exporting_signals: Failed to connect {btn_name}: {e}")

        logger.debug(f"force_reconnect_exporting_signals: {connected_count}/2 signals connected")

    def force_reconnect_exploring_signals(self) -> None:
        """
        Force reconnect EXPLORING signals bypassing cache.

        REGRESSION FIX 2026-01-13: IS_SELECTING, IS_TRACKING, IS_LINKING use 'toggled' not 'clicked'
        FIX 2026-01-15: IDENTIFY and ZOOM removed - connected directly in _connect_exploring_buttons_directly
        """
        if 'EXPLORING' not in self.widgets:
            return

        ws = {
            'SINGLE_SELECTION_FEATURES': ['featureChanged'],
            'SINGLE_SELECTION_EXPRESSION': ['fieldChanged'],
            'MULTIPLE_SELECTION_FEATURES': ['updatingCheckedItemList', 'filteringCheckedItemList'],
            'MULTIPLE_SELECTION_EXPRESSION': ['fieldChanged'],
            'CUSTOM_SELECTION_EXPRESSION': ['fieldChanged'],
            'IS_SELECTING': ['toggled'],
            'IS_TRACKING': ['toggled'],
            'IS_LINKING': ['toggled'],
            'RESET_ALL_LAYER_PROPERTIES': ['clicked']
        }

        for w, signals in ws.items():
            if w not in self.widgets['EXPLORING']:
                continue

            for s_tuple in self.widgets['EXPLORING'][w].get("SIGNALS", []):
                if not s_tuple[-1] or s_tuple[0] not in signals:
                    continue

                key = f"EXPLORING.{w}.{s_tuple[0]}"
                self._signal_connection_states.pop(key, None)

                try:
                    self._signal_connection_states[key] = self.change_signal_state(
                        ['EXPLORING', w], s_tuple[0], s_tuple[-1], 'connect'
                    )
                except Exception:
                    # Signal connection may fail if widget deleted
                    pass

        # FIX 2026-01-14: Connect exploring buttons DIRECTLY
        self._connect_exploring_buttons_directly()

        # FIX 2026-01-15: Also reconnect expression widget signals
        self._setup_expression_widget_direct_connections()

    def _connect_exploring_buttons_directly(self) -> None:
        """
        Connect ALL exploring buttons directly (IS_SELECTING, IS_TRACKING, IS_LINKING, IDENTIFY, ZOOM, RESET).

        FIX 2026-01-15 v3: Bypasses the manageSignal/custom_functions mechanism and connects
        button signals directly to their handlers.
        """
        logger.info("_connect_exploring_buttons_directly CALLED")

        # Check if buttons exist
        if not hasattr(self.dockwidget, 'pushButton_exploring_identify'):
            logger.error("pushButton_exploring_identify does NOT exist!")
            return

        # Connect IDENTIFY button
        try:
            self.dockwidget.pushButton_exploring_identify.clicked.disconnect()
        except (TypeError, RuntimeError):
            pass
        self.dockwidget.pushButton_exploring_identify.clicked.connect(
            self.dockwidget.exploring_identify_clicked
        )
        logger.debug("Connected pushButton_exploring_identify.clicked DIRECTLY")

        # Connect ZOOM button
        try:
            self.dockwidget.pushButton_exploring_zoom.clicked.disconnect()
        except (TypeError, RuntimeError):
            pass
        self.dockwidget.pushButton_exploring_zoom.clicked.connect(
            self.dockwidget.exploring_zoom_clicked
        )
        logger.debug("Connected pushButton_exploring_zoom.clicked DIRECTLY")

        # Connect RESET button
        try:
            self.dockwidget.pushButton_exploring_reset_layer_properties.clicked.disconnect()
        except (TypeError, RuntimeError):
            pass
        self.dockwidget.pushButton_exploring_reset_layer_properties.clicked.connect(
            lambda: self.dockwidget.resetLayerVariableEvent()
        )
        logger.debug("Connected pushButton_exploring_reset_layer_properties.clicked DIRECTLY")

        # Connect IS_SELECTING toggle
        self._connect_is_selecting_toggle()

        # Connect IS_TRACKING toggle
        self._connect_is_tracking_toggle()

        # Connect IS_LINKING toggle
        self._connect_is_linking_toggle()

    def _connect_is_selecting_toggle(self) -> None:
        """Connect IS_SELECTING button with bidirectional sync."""
        btn = self.dockwidget.pushButton_checkable_exploring_selecting

        try:
            btn.toggled.disconnect()
        except (TypeError, RuntimeError):
            pass

        # Sync initial state from button to PROJECT_LAYERS
        current_layer = getattr(self.dockwidget, 'current_layer', None)
        project_layers = getattr(self.dockwidget, 'PROJECT_LAYERS', {})

        if current_layer and self.widgets_initialized:
            layer_id = current_layer.id()
            if layer_id in project_layers:
                current_button_state = btn.isChecked()
                stored_state = project_layers[layer_id]["exploring"].get("is_selecting", False)

                if current_button_state != stored_state:
                    logger.warning(f"IS_SELECTING state mismatch! Button={current_button_state}, Stored={stored_state}")  # nosec B608
                    project_layers[layer_id]["exploring"]["is_selecting"] = current_button_state

        def _on_selecting_toggled(checked):
            """Handle IS_SELECTING toggle."""
            if not self.dockwidget._is_layer_valid():
                return

            layer_id = self.dockwidget.current_layer.id()
            if layer_id in self.dockwidget.PROJECT_LAYERS:
                self.dockwidget.PROJECT_LAYERS[layer_id]["exploring"]["is_selecting"] = checked
                logger.info(f"IS_SELECTING state updated: {checked}")  # nosec B608

            if checked:
                logger.info("IS_SELECTING ON: Calling exploring_select_features()")
                self.dockwidget._ensure_selection_changed_connected()
                self.dockwidget.exploring_select_features()
            else:
                logger.info("IS_SELECTING OFF: Calling exploring_deselect_features()")
                self.dockwidget.exploring_deselect_features()

        btn.toggled.connect(_on_selecting_toggled)

    def _connect_is_tracking_toggle(self) -> None:
        """Connect IS_TRACKING button for auto-zoom."""
        btn = self.dockwidget.pushButton_checkable_exploring_tracking

        try:
            btn.toggled.disconnect()
        except (TypeError, RuntimeError):
            pass

        # Sync initial state
        current_layer = getattr(self.dockwidget, 'current_layer', None)
        project_layers = getattr(self.dockwidget, 'PROJECT_LAYERS', {})

        if current_layer and self.widgets_initialized:
            layer_id = current_layer.id()
            if layer_id in project_layers:
                current_button_state = btn.isChecked()
                stored_state = project_layers[layer_id]["exploring"].get("is_tracking", False)

                if current_button_state != stored_state:
                    logger.warning(f"IS_TRACKING state mismatch! Button={current_button_state}, Stored={stored_state}")
                    project_layers[layer_id]["exploring"]["is_tracking"] = current_button_state

        def _on_tracking_toggled(checked):
            """Handle IS_TRACKING toggle."""
            if not self.dockwidget._is_layer_valid():
                return

            layer_id = self.dockwidget.current_layer.id()
            if layer_id in self.dockwidget.PROJECT_LAYERS:
                self.dockwidget.PROJECT_LAYERS[layer_id]["exploring"]["is_tracking"] = checked
                logger.info(f"IS_TRACKING state updated: {checked}")

            if checked:
                logger.info("IS_TRACKING ON: Triggering zoom")
                self.dockwidget.exploring_zoom_clicked()

        btn.toggled.connect(_on_tracking_toggled)

    def _connect_is_linking_toggle(self) -> None:
        """Connect IS_LINKING button for expression sync."""
        btn = self.dockwidget.pushButton_checkable_exploring_linking

        try:
            btn.toggled.disconnect()
        except (TypeError, RuntimeError):
            pass

        # Sync initial state
        current_layer = getattr(self.dockwidget, 'current_layer', None)
        project_layers = getattr(self.dockwidget, 'PROJECT_LAYERS', {})

        if current_layer and self.widgets_initialized:
            layer_id = current_layer.id()
            if layer_id in project_layers:
                current_button_state = btn.isChecked()
                stored_state = project_layers[layer_id]["exploring"].get("is_linking", False)

                if current_button_state != stored_state:
                    logger.warning(f"IS_LINKING state mismatch! Button={current_button_state}, Stored={stored_state}")
                    project_layers[layer_id]["exploring"]["is_linking"] = current_button_state

        def _on_linking_toggled(checked):
            """Handle IS_LINKING toggle."""
            if not self.dockwidget._is_layer_valid():
                return

            layer_id = self.dockwidget.current_layer.id()
            if layer_id in self.dockwidget.PROJECT_LAYERS:
                self.dockwidget.PROJECT_LAYERS[layer_id]["exploring"]["is_linking"] = checked
                logger.info(f"IS_LINKING state updated: {checked}")

            if checked:
                logger.info("IS_LINKING ON: Triggering sync_expressions")
                self.dockwidget.exploring_sync_expressions()

        btn.toggled.connect(_on_linking_toggled)

    def _setup_expression_widget_direct_connections(self) -> None:
        """
        Set up direct connections for expression widgets.

        FIX 2026-01-15: These must be connected whenever exploring signals are reconnected.
        """
        # Delegate to dockwidget method if it exists
        if hasattr(self.dockwidget, '_setup_expression_widget_direct_connections'):
            self.dockwidget._setup_expression_widget_direct_connections()

    def connect_groupbox_signals_directly(self) -> None:
        """
        Connect groupbox signals for exclusive behavior.

        FIX 2026-01-18: Ensure signals are always unblocked even if exception occurs.
        """
        gbs = [
            (self.dockwidget.mGroupBox_exploring_single_selection, 'single_selection'),
            (self.dockwidget.mGroupBox_exploring_multiple_selection, 'multiple_selection'),
            (self.dockwidget.mGroupBox_exploring_custom_selection, 'custom_selection')
        ]

        try:
            # Disconnect existing signals first
            for gb, _ in gbs:
                try:
                    gb.blockSignals(True)
                    try:
                        gb.toggled.disconnect()
                        gb.collapsedStateChanged.disconnect()
                    except TypeError:
                        # Signals not connected yet - expected on first setup
                        pass
                finally:
                    gb.blockSignals(False)

            # Connect new signals
            for gb, name in gbs:
                gb.toggled.connect(lambda c, n=name: self.dockwidget._on_groupbox_clicked(n, c))
                gb.collapsedStateChanged.connect(
                    lambda col, n=name: self.dockwidget._on_groupbox_collapse_changed(n, col)
                )

            logger.debug("connect_groupbox_signals_directly: Signals connected successfully")

        except Exception as e:
            logger.warning(f"connect_groupbox_signals_directly error: {e}")
            # Ensure all groupboxes have signals unblocked
            for gb, _ in gbs:
                try:
                    gb.blockSignals(False)
                except (RuntimeError, AttributeError):
                    pass

    def connect_initial_widget_signals(self) -> None:
        """
        Connect critical widget signals after configuration.

        FIX 2026-01-14: These signals must be connected at startup:
        - FILTERING.CURRENT_LAYER.layerChanged: Updates exploring widgets
        - ACTION buttons: FILTER, UNFILTER, UNDO_FILTER, REDO_FILTER, EXPORT

        NOTE: QGIS.LAYER_TREE_VIEW.currentLayerChanged is managed by
        filtering_auto_current_layer_changed() based on AUTO_CURRENT_LAYER state.
        """
        if not self.widgets_initialized:
            return

        try:
            # FIX 2026-01-14: Force connection by clearing cache first
            cache_key = "FILTERING.CURRENT_LAYER.layerChanged"
            if cache_key in self._signal_connection_states:
                logger.debug(f"Clearing stale cache for {cache_key}")
                del self._signal_connection_states[cache_key]

            # Connect comboBox_filtering_current_layer.layerChanged signal
            self.manage_signal(["FILTERING", "CURRENT_LAYER"], 'connect', 'layerChanged')
            logger.debug("Connected FILTERING.CURRENT_LAYER.layerChanged signal")
        except Exception as e:
            logger.warning(f"Could not connect CURRENT_LAYER signal: {e}")

        # FIX 2026-01-16: Connect ACTION button signals at startup
        try:
            logger.debug("Connecting ACTION button signals at startup...")
            self.force_reconnect_action_signals()
            logger.debug("ACTION button signals connected at startup")
        except Exception as e:
            logger.warning(f"Could not connect ACTION signals at startup: {e}")

        # FIX 2026-01-22: Connect EXPORTING button signals at startup
        try:
            logger.debug("Connecting EXPORTING button signals at startup...")
            self.force_reconnect_exporting_signals()
            logger.debug("EXPORTING button signals connected at startup")
        except Exception as e:
            logger.warning(f"Could not connect EXPORTING signals at startup: {e}")

        # FIX 2026-01-14: Connect LAYER_TREE_VIEW if AUTO_CURRENT_LAYER enabled
        try:
            project_props = getattr(self.dockwidget, 'project_props', {})
            auto_current_layer_enabled = project_props.get("OPTIONS", {}).get("LAYERS", {}).get(
                "LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG", False
            )

            if auto_current_layer_enabled:
                # Clear cache for LAYER_TREE_VIEW
                cache_key = "QGIS.LAYER_TREE_VIEW.currentLayerChanged"
                if cache_key in self._signal_connection_states:
                    del self._signal_connection_states[cache_key]

                self.manage_signal(["QGIS", "LAYER_TREE_VIEW"], 'connect', 'currentLayerChanged')
                logger.debug("Connected QGIS.LAYER_TREE_VIEW.currentLayerChanged signal")
            else:
                logger.debug("QGIS.LAYER_TREE_VIEW signal not connected (AUTO_CURRENT_LAYER disabled)")
        except Exception as e:
            logger.warning(f"Could not check/connect LAYER_TREE_VIEW signal: {e}")

    def clear_cache(self, key: Optional[str] = None) -> None:
        """
        Clear signal connection state cache.

        Args:
            key: Specific cache key to clear, or None to clear all
        """
        if key:
            self._signal_connection_states.pop(key, None)
        else:
            self._signal_connection_states.clear()

    def get_cache_state(self, key: str) -> Optional[bool]:
        """
        Get cached signal connection state.

        Args:
            key: Cache key in format "CATEGORY.WIDGET.signal_name"

        Returns:
            Cached state (True/False) or None if not cached
        """
        return self._signal_connection_states.get(key)

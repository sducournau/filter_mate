# -*- coding: utf-8 -*-
"""
FilterMateDockWidget - Main UI component for FilterMate QGIS plugin.

This module is progressively migrating to MVC architecture:
- UI Controllers: ui/controllers/
- Services: core/services/
- Domain: core/domain/

See docs/architecture.md for migration guide.
"""

from .config.config import ENV_VARS
import os
import json
import re
import sip
import weakref

# Import logging for error handling
from .infrastructure.logging import get_app_logger
logger = get_app_logger()

# v4.0 Sprint 6: Widget configuration management
# v5.0 Phase 2: Add DockwidgetSignalManager for signal management extraction
from .ui.managers import ConfigurationManager, DockwidgetSignalManager
from qgis.PyQt import QtGui, QtWidgets, QtCore
from qgis.PyQt.QtCore import (
    Qt,
    QCoreApplication,
    QMetaMethod,
    QObject,
    pyqtSignal,
    QTimer
)
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsExpression,
    QgsFeatureRequest,
    QgsLayerItem,
    QgsProject,
    QgsProperty,
    QgsPropertyDefinition,
    QgsRectangle,
    QgsVectorLayer
)

# Compatibility layer for proxy model classes (moved from qgis.core to qgis.gui in QGIS 3.30+)
try: from qgis.gui import QgsMapLayerProxyModel
except ImportError:
    try: from qgis.core import QgsMapLayerProxyModel
    except ImportError:
        # Fallback with proper flag values (from QGIS 3.x API)
        class QgsMapLayerProxyModel:
            NoFilter = 0
            RasterLayer = 1
            NoGeometry = 2
            PointLayer = 4
            LineLayer = 8
            PolygonLayer = 16
            HasGeometry = PointLayer | LineLayer | PolygonLayer  # 28
            VectorLayer = NoGeometry | HasGeometry  # 30
            PluginLayer = 32
            WritableLayer = 64
            MeshLayer = 128
            VectorTileLayer = 256
            PointCloudLayer = 512
            AnnotationLayer = 1024
            TiledSceneLayer = 2048
            All = -1

try: from qgis.gui import QgsFieldProxyModel
except ImportError:
    try: from qgis.core import QgsFieldProxyModel
    except ImportError:
        class QgsFieldProxyModel: AllTypes = 0
from qgis.utils import iface

import webbrowser
from .ui.widgets import QgsCheckableComboBoxFeaturesListPickerWidget
from .ui.widgets.json_view.model import JsonModel
from .ui.widgets.json_view.view import JsonView

# Object safety and layer utilities (migrated to infrastructure)
from .infrastructure.utils import is_layer_valid as is_valid_layer
from .infrastructure.utils import (
    get_best_display_field,
    is_layer_source_available,
    safe_disconnect
)
from .core.domain.exceptions import SignalStateChangeError
from .ui.styles import StyleLoader, QGISThemeWatcher
from .infrastructure.feedback import show_info, show_warning, show_error, show_success

# Feedback level control
try:
    from .config.feedback_config import should_show_message
except ImportError:
    def should_show_message(category): return True

# Config helpers (migrated to config/)
from .config.config import get_optimization_thresholds

from .infrastructure.cache import ExploringFeaturesCache
from .filter_mate_dockwidget_base import Ui_FilterMateDockWidgetBase

# Import async expression evaluation for large layers (v2.5.10)
# EPIC-1: Migrated to core/tasks/
try:
    from .core.tasks import get_expression_manager
    ASYNC_EXPRESSION_AVAILABLE = True
except ImportError:
    ASYNC_EXPRESSION_AVAILABLE = False; get_expression_manager = None

# Icon utilities for dark mode (migrated to ui/)
try: from .ui.icons import IconThemeManager, get_themed_icon; ICON_THEME_AVAILABLE = True
except ImportError: ICON_THEME_AVAILABLE = False

# UI configuration system
try: from .ui import widget_utils as ui_utils; UI_CONFIG_AVAILABLE = True
except ImportError: UI_CONFIG_AVAILABLE = False

# MVC Controllers
try:
    from .ui.controllers.integration import ControllerIntegration
    from .adapters.app_bridge import get_filter_service, is_initialized as is_hexagonal_initialized
    CONTROLLERS_AVAILABLE = True
except ImportError as e:
    CONTROLLERS_AVAILABLE = False
    get_filter_service = None
    is_hexagonal_initialized = lambda: False
    logger.debug(f"Controllers import failed: {e}")
except Exception as e:
    CONTROLLERS_AVAILABLE = False
    get_filter_service = None
    is_hexagonal_initialized = lambda: False
    logger.debug(f"Unexpected error importing controllers: {e}")

# Layout Managers
try: from .ui.layout import SplitterManager, DimensionsManager, SpacingManager, ActionBarManager; LAYOUT_MANAGERS_AVAILABLE = True
except ImportError: LAYOUT_MANAGERS_AVAILABLE = False; SplitterManager = DimensionsManager = SpacingManager = ActionBarManager = None

# Style Managers
try: from .ui.styles import ThemeManager, IconManager, ButtonStyler; STYLE_MANAGERS_AVAILABLE = True
except ImportError: STYLE_MANAGERS_AVAILABLE = False; ThemeManager = IconManager = ButtonStyler = None


class ClickableLabel(QtWidgets.QLabel):
    """QLabel that properly handles mouse clicks for menus."""

    clicked = pyqtSignal(object)  # Emits the mouse event

    def __init__(self, parent=None):
        super().__init__(parent)
        self._click_handler = None
        # Enable mouse tracking to ensure events are received
        self.setMouseTracking(True)

    def set_click_handler(self, handler):
        """Set the click handler function."""
        self._click_handler = handler

    def mousePressEvent(self, event):
        """Handle mouse press events."""
        if self._click_handler:
            # Call the handler with the event
            try:
                self._click_handler(event)
            except Exception as e:
                logger.debug(f"Error in click handler: {e}")

        # Always emit the signal
        self.clicked.emit(event)

        # Accept the event to prevent propagation issues
        event.accept()

    def mouseReleaseEvent(self, event):
        """Handle mouse release - some widgets need this."""
        event.accept()


class FilterMateDockWidget(QtWidgets.QDockWidget, Ui_FilterMateDockWidgetBase):
    """Main dockwidget UI component for FilterMate QGIS plugin.

    Provides the user interface for:
    - Exploring: Feature selection, identification, zooming
    - Filtering: Spatial predicates, buffer operations, layer targeting
    - Exporting: Multi-format export with style support
    - Configuration: Plugin settings and optimization options

    Architecture:
        Progressively migrating to MVC pattern:
        - Controllers: ui/controllers/ (ExploringController, FilteringController, etc.)
        - Services: core/services/
        - Domain: core/domain/

    Attributes:
        PROJECT_LAYERS: Dict mapping layer IDs to layer properties.
        current_layer: Currently selected QgsVectorLayer.
        CONFIG_DATA: Plugin configuration dictionary.
        widgets: Nested dict of UI widget references organized by tab.

    Signals:
        closingPlugin: Emitted when plugin is closing.
        launchingTask: Emitted to request task execution (filter/export/etc.).
        currentLayerChanged: Emitted when current layer changes.
        projectLayersReady: Emitted after PROJECT_LAYERS is populated.
    """

    closingPlugin = pyqtSignal()
    launchingTask = pyqtSignal(str)
    currentLayerChanged = pyqtSignal()
    widgetsInitialized = pyqtSignal()
    projectLayersReady = pyqtSignal()  # Emitted after PROJECT_LAYERS populated

    gettingProjectLayers = pyqtSignal()

    settingLayerVariable = pyqtSignal(QgsVectorLayer, list)
    resettingLayerVariable = pyqtSignal(QgsVectorLayer, list)
    resettingLayerVariableOnError = pyqtSignal(QgsVectorLayer, list)

    settingProjectVariables = pyqtSignal()

    # Static cache for geometry icons to avoid repeated calculations
    _icon_cache = {}

    # Static cache for signal lookup to avoid repeated metaObject iteration
    _signal_cache = {}

    def __init__(self, project_layers, plugin_dir, config_data, project, parent=None):
        """v4.0 Sprint 16: Initialize dockwidget with state, managers, controllers, optimizations."""
        super(FilterMateDockWidget, self).__init__(parent)
        self.exception, self.iface = None, iface
        self.plugin_dir, self.CONFIG_DATA, self.PROJECT_LAYERS, self.PROJECT = plugin_dir, config_data, project_layers, project
        self.current_layer, self.current_layer_selection_connection = None, None
        self._updating_layers = self._updating_current_layer = self._updating_groupbox = self._signals_connected = False
        self._pending_layers_update = self._plugin_busy = self._syncing_from_qgis = False
        self._filtering_in_progress, self._filter_completed_time, self._saved_layer_id_before_filter = False, 0, None
        self._layer_tree_view_signal_connected, self._signal_connection_states, self._theme_watcher = False, {}, None
        # FIX 2026-01-19: Flag to prevent feedback loop when widget updates QGIS selection
        self._updating_qgis_selection_from_widget = False
        self._configuring_groupbox = False  # FIX 2026-01-19: Prevent nested groupbox config
        # FIX 2026-01-19 v3: Counter for skipping selectionChanged signals (2 = removeSelection + select)
        self._skip_selection_changed_count = 0
        self._expression_debounce_timer = QTimer()
        self._expression_debounce_timer.setSingleShot(True); self._expression_debounce_timer.setInterval(450)
        self._expression_debounce_timer.timeout.connect(self._execute_debounced_expression_change)
        self._pending_expression_change = self._last_expression_change_source = None
        self._expression_cache, self._expression_cache_max_age, self._expression_cache_max_size = {}, 60.0, 100
        thresholds = get_optimization_thresholds(ENV_VARS)
        self._async_expression_threshold = thresholds['async_expression_threshold']
        self._expression_manager = get_expression_manager() if ASYNC_EXPRESSION_AVAILABLE else None
        self._pending_async_evaluation, self._expression_loading, self._configuration_manager = None, False, None
        # FIX 2026-01-19: Track layer connections for QgsFeaturePickerWidget crash prevention
        # When a layer is deleted, its QgsFeaturePickerWidget must be cleared BEFORE
        # the internal QTimer triggers scheduledReload, which would cause access violation
        self._feature_picker_layer_connection = None  # Stores (layer, connection) tuple
        # v5.0 Phase 2: Initialize signal manager for progressive migration
        self._signal_manager = DockwidgetSignalManager(self)
        self._initialize_layer_state()

    def _safe_get_layer_props(self, layer):
        """v4.0 Sprint 16: Get layer properties from PROJECT_LAYERS with validation."""
        if layer is None or not isinstance(layer, QgsVectorLayer): return None
        layer_id = layer.id()
        if layer_id not in self.PROJECT_LAYERS:
            logger.warning(f"Layer {layer.name()} (ID: {layer_id}) not found in PROJECT_LAYERS"); return None
        return self.PROJECT_LAYERS[layer_id]

    @property
    def _backend_ctrl(self):
        """Sprint 18: Helper property for BackendController access."""
        return self._controller_integration._backend_controller if self._controller_integration and self._controller_integration._backend_controller else None

    @property
    def _favorites_ctrl(self):
        """Sprint 18: Helper property for FavoritesController access."""
        return self._controller_integration._favorites_controller if self._controller_integration and self._controller_integration._favorites_controller else None

    @property
    def favorites_controller(self):
        """FIX 2026-01-19: Public alias for FavoritesController access (used by filter_mate_app)."""
        return self._favorites_ctrl

    @property
    def _exploring_ctrl(self):
        """Sprint 18: Helper property for ExploringController access."""
        return self._controller_integration.exploring_controller if self._controller_integration and self._controller_integration.exploring_controller else None

    @property
    def _layer_sync_ctrl(self):
        """Sprint 18: Helper property for LayerSyncController access."""
        return self._controller_integration.layer_sync_controller if self._controller_integration and self._controller_integration.layer_sync_controller else None

    @property
    def _property_ctrl(self):
        """Sprint 18: Helper property for PropertyController access."""
        return self._controller_integration.property_controller if self._controller_integration and self._controller_integration.property_controller else None

    @property
    def _raster_exploring_ctrl(self):
        """Phase 0: Helper property for RasterExploringController access."""
        return self._controller_integration.raster_exploring_controller if self._controller_integration and self._controller_integration.raster_exploring_controller else None

    @property
    def signal_manager(self):
        """v5.0 Phase 2: Access to DockwidgetSignalManager for signal management.

        Progressive migration: methods can use either:
        - self.manageSignal() (legacy, will be deprecated)
        - self.signal_manager.manage_signal() (new, preferred)
        """
        return self._signal_manager

    def _is_ui_ready(self) -> bool:
        """Sprint 18: Check if UI is ready for operations."""
        return self.widgets_initialized and self.has_loaded_layers

    def _is_layer_valid(self) -> bool:
        """Sprint 18: Check if current_layer is valid and usable."""
        if not self.widgets_initialized or not self.current_layer:
            return False
        if self._is_layer_truly_deleted(self.current_layer):
            self.current_layer = None
            return False
        return True

    def _connect_selection_signal(self, layer=None) -> bool:
        """
        Centralized selectionChanged signal connection.

        FIX 2026-02-10 (C1): Single entry point for connecting selectionChanged.
        Uses safe_disconnect first to prevent signal stacking, then connects.

        Args:
            layer: The layer to connect. If None, uses self.current_layer.

        Returns:
            True if connected successfully, False otherwise.
        """
        target_layer = layer or self.current_layer
        if not target_layer or not target_layer.isValid():
            return False
        try:
            # Always disconnect first to prevent stacking
            safe_disconnect(target_layer.selectionChanged, self.on_layer_selection_changed)
            target_layer.selectionChanged.connect(self.on_layer_selection_changed)
            self.current_layer_selection_connection = True
            logger.debug(f"_connect_selection_signal: Connected for layer '{target_layer.name()}'")
            return True
        except (TypeError, RuntimeError) as e:
            logger.error(f"_connect_selection_signal failed: {e}")
            self.current_layer_selection_connection = False
            return False

    def _disconnect_selection_signal(self) -> bool:
        """
        Centralized selectionChanged signal disconnection.

        FIX 2026-02-10 (C1): Single entry point for disconnecting selectionChanged.
        Uses safe_disconnect for idempotent disconnection.

        Returns:
            True if disconnected (or was already disconnected), False on error.
        """
        if self.current_layer is None:
            self.current_layer_selection_connection = None
            return True
        try:
            safe_disconnect(self.current_layer.selectionChanged, self.on_layer_selection_changed)
            self.current_layer_selection_connection = None
            logger.debug(f"_disconnect_selection_signal: Disconnected for layer '{self.current_layer.name()}'")
            return True
        except (TypeError, RuntimeError) as e:
            logger.warning(f"_disconnect_selection_signal failed: {e}")
            self.current_layer_selection_connection = None
            return True

    def _ensure_layer_signals_connected(self, layer) -> bool:
        """
        FIX 2026-01-15 (FIX-003): Ensure layer signals are connected.

        Delegates to _connect_selection_signal for centralized management.

        Returns: True if connected successfully
        """
        return self._connect_selection_signal(layer)

    def _connect_feature_picker_layer_deletion(self, layer):
        """
        FIX 2026-01-19: Connect willBeDeleted signal to clear QgsFeaturePickerWidget immediately.

        CRITICAL: QgsFeaturePickerWidget has an internal QTimer that triggers scheduledReload.
        If the layer is deleted while this timer is pending, it causes a Windows fatal exception
        (access violation) when QgsVectorLayerFeatureSource tries to access the deleted layer.

        Stack trace of the crash:
        - QgsFeaturePickerModelBase::scheduledReload
        - QgsVectorLayerFeatureSource::QgsVectorLayerFeatureSource
        - QgsExpressionContextUtils::layerScope
        - QgsMapLayer::customProperty (CRASH - layer deleted)

        Solution: Connect to layer.willBeDeleted signal to clear the widget BEFORE deletion.

        Args:
            layer: QgsVectorLayer being set on the FeaturePickerWidget
        """
        # Disconnect previous connection if any
        self._disconnect_feature_picker_layer_deletion()

        if not layer or not layer.isValid():
            return

        try:
            # Connect to willBeDeleted signal with direct connection for immediate execution
            layer.willBeDeleted.connect(self._on_feature_picker_layer_deleted)
            self._feature_picker_layer_connection = layer
            logger.debug(f"FIX-2026-01-19: Connected willBeDeleted for FeaturePickerWidget layer '{layer.name()}'")
        except Exception as e:
            logger.warning(f"Failed to connect willBeDeleted for FeaturePickerWidget: {e}")
            self._feature_picker_layer_connection = None

    def _disconnect_feature_picker_layer_deletion(self):
        """
        FIX 2026-01-19: Disconnect willBeDeleted signal from previous layer.
        """
        if self._feature_picker_layer_connection is not None:
            try:
                layer = self._feature_picker_layer_connection
                # Check if layer is still valid before disconnecting
                if layer and not sip.isdeleted(layer) and layer.isValid():
                    layer.willBeDeleted.disconnect(self._on_feature_picker_layer_deleted)
                    logger.debug("FIX-2026-01-19: Disconnected willBeDeleted for FeaturePickerWidget")
            except (TypeError, RuntimeError) as e:
                # Already disconnected or layer destroyed - ignore
                logger.debug(f"willBeDeleted already disconnected or layer gone: {e}")
            finally:
                self._feature_picker_layer_connection = None

    def _on_feature_picker_layer_deleted(self):
        """
        FIX 2026-01-19: Called when the FeaturePickerWidget's layer is about to be deleted.

        CRITICAL: This MUST clear the widget IMMEDIATELY (synchronously) before the layer
        is actually destroyed, otherwise the internal timer will cause access violation.
        """
        logger.info("FIX-2026-01-19: 🛡️ Layer deletion detected - clearing FeaturePickerWidget to prevent crash")
        try:
            if hasattr(self, 'mFeaturePickerWidget_exploring_single_selection'):
                # Set to None IMMEDIATELY - do NOT defer this!
                self.mFeaturePickerWidget_exploring_single_selection.setLayer(None)
                logger.debug("FIX-2026-01-19: FeaturePickerWidget cleared successfully before layer deletion")
        except Exception as e:
            logger.warning(f"FIX-2026-01-19: Error clearing FeaturePickerWidget on layer deletion: {e}")
        finally:
            # Clear the connection reference (layer is being deleted anyway)
            self._feature_picker_layer_connection = None

    def _initialize_layer_state(self):
        """v4.0 Sprint 15: Initialize layers, managers, controllers, and UI."""
        self.init_layer, self.has_loaded_layers = None, False
        if self.PROJECT:
            vector_layers = [l for l in self.PROJECT.mapLayers().values() if isinstance(l, QgsVectorLayer)]
            if vector_layers:
                self.init_layer, self.has_loaded_layers = self.iface.activeLayer() or vector_layers[0], True
        self.widgets, self.widgets_initialized, self.current_exploring_groupbox, self.tabTools_current_index = None, False, None, 0
        self.backend_indicator_label, self.plugin_title_label, self.frame_header = None, None, None
        self._exploring_cache = ExploringFeaturesCache(max_layers=50, max_age_seconds=300.0)

        # Layout/Style managers
        self._splitter_manager = self._dimensions_manager = self._spacing_manager = self._action_bar_manager = None
        if LAYOUT_MANAGERS_AVAILABLE:
            for name, cls in [('_splitter_manager', SplitterManager), ('_dimensions_manager', DimensionsManager),
                              ('_spacing_manager', SpacingManager), ('_action_bar_manager', ActionBarManager)]:
                try: setattr(self, name, cls(self) if cls else None)
                except Exception as e: logger.debug(f"Layout manager {name} init skipped: {e}")
        self._theme_manager = self._icon_manager = self._button_styler = None
        if STYLE_MANAGERS_AVAILABLE:
            try: self._theme_manager, self._icon_manager, self._button_styler = ThemeManager(self), IconManager(self), ButtonStyler(self)
            except Exception as e: logger.warning(f"Style managers init failed: {e}")

        # Controllers - v4.0 Sprint 16: MVC Controllers via ControllerIntegration
        logger.debug("_initialize_layer_state: Initializing controllers")
        logger.debug(f"  CONTROLLERS_AVAILABLE = {CONTROLLERS_AVAILABLE}")

        self._controller_integration = None
        if CONTROLLERS_AVAILABLE:
            try:
                logger.debug("Creating ControllerIntegration instance...")
                logger.debug(f"  is_hexagonal_initialized() = {is_hexagonal_initialized()}")

                # Get filter service if hexagonal architecture is initialized
                filter_service = None
                if is_hexagonal_initialized() and get_filter_service:
                    try:
                        filter_service = get_filter_service()
                        logger.debug(f"  filter_service retrieved: {type(filter_service).__name__}")
                    except Exception as e:
                        logger.warning(f"  Failed to get filter_service: {e}")

                # Create controller integration (will be setup later in manage_interactions)
                self._controller_integration = ControllerIntegration(
                    dockwidget=self,
                    filter_service=filter_service,
                    enabled=True
                )
                logger.info("✓ ControllerIntegration instance created (setup deferred to manage_interactions)")

            except Exception as e:
                logger.error(f"Failed to initialize ControllerIntegration: {e}", exc_info=True)
                self._controller_integration = None
        else:
            logger.warning("CONTROLLERS_AVAILABLE is False - controllers will not be initialized")
            logger.debug(f"  ControllerIntegration importable: {'ControllerIntegration' in globals()}")

        self._last_single_selection_fid = self._last_single_selection_layer_id = None
        self._last_multiple_selection_fids = self._last_multiple_selection_layer_id = None
        self.predicates = self.project_props = self.layer_properties_tuples_dict = self.export_properties_tuples_dict = None
        self.buffer_property_has_been_init = False
        self.json_template_project_exporting = '{"has_layers_to_export":false,"layers_to_export":[],"has_projection_to_export":false,"projection_to_export":"","has_styles_to_export":false,"styles_to_export":"","has_datatype_to_export":false,"datatype_to_export":"","datatype_to_export":"","has_output_folder_to_export":false,"output_folder_to_export":"","has_zip_to_export":false,"zip_to_export":"","batch_output_folder":false,"batch_zip":false }'
        self.pending_config_changes, self.config_changes_pending = [], False
        if ICON_THEME_AVAILABLE:
            try: IconThemeManager.set_theme(StyleLoader.detect_qgis_theme())
            except Exception as e: logger.debug(f"IconThemeManager init (non-critical): {e}")
        self.setupUi(self)

        # FIX 2026-01-21: Prevent style propagation to child dialogs
        # Set Qt attribute to prevent FilterMate styles from affecting QGIS dialogs
        # opened as children (e.g., QgsExpressionBuilderDialog)
        self.setAttribute(Qt.WA_StyledBackground, False)

        # FIX 2026-01-21: The transparent palette issue has been fixed at source.
        # The palette with alpha=0 colors was removed from filter_mate_dockwidget_base.ui/.py
        # No need to reset palette here anymore - dockwidget now inherits QGIS default palette.

        self.setupUiCustom()
        self.manage_ui_style()
        try:
            self.manage_interactions()
        except Exception as e:
            logger.error(f"Error in manage_interactions: {e}", exc_info=True)
            from qgis.utils import iface
            iface.messageBar().pushCritical("FilterMate", self.tr("Initialization error: {}").format(str(e)))

    def getSignal(self, oObject: QObject, strSignalName: str):
        """v4.0 S16: Get signal from QObject by name with caching."""
        class_name, cache_key = oObject.metaObject().className(), f"{oObject.metaObject().className()}.{strSignalName}"
        if cache_key in FilterMateDockWidget._signal_cache: return FilterMateDockWidget._signal_cache[cache_key]
        oMetaObj = oObject.metaObject()
        for i in range(oMetaObj.methodCount()):
            oMetaMethod = oMetaObj.method(i)
            if oMetaMethod.isValid() and oMetaMethod.methodType() == QMetaMethod.Signal and oMetaMethod.name() == strSignalName:
                FilterMateDockWidget._signal_cache[cache_key] = oMetaMethod; return oMetaMethod
        FilterMateDockWidget._signal_cache[cache_key] = None; return None

    def manageSignal(self, widget_path, custom_action=None, custom_signal_name=None):
        """v4.0 S16: Manage signal connection/disconnection.

        DEPRECATED v5.0: Use self.signal_manager.manage_signal() instead.
        This method delegates to DockwidgetSignalManager and syncs caches.
        """
        if not isinstance(widget_path, list) or len(widget_path) != 2:
            raise SignalStateChangeError(None, widget_path, 'Incorrect input parameters')
        widget_object, state = self.widgets[widget_path[0]][widget_path[1]], None
        signals_to_process = [(s[0], s[-1]) for s in widget_object["SIGNALS"]
                              if s[-1] is not None and (custom_signal_name is None or s[0] == custom_signal_name)]
        logger.debug(f"manageSignal: {widget_path} | action={custom_action} | signal={custom_signal_name} | signals_to_process={len(signals_to_process)}")
        for signal_name, func in signals_to_process:
            state_key, cached = f"{widget_path[0]}.{widget_path[1]}.{signal_name}", self._signal_connection_states.get(f"{widget_path[0]}.{widget_path[1]}.{signal_name}")
            logger.debug(f"  Signal '{signal_name}' | state_key={state_key} | cached={cached} | action={custom_action}")
            if (custom_action == 'connect' and cached is True) or (custom_action == 'disconnect' and cached is False):
                state = cached
                logger.debug("  -> SKIP (already in desired state)")
                continue
            state = self.changeSignalState(widget_path, signal_name, func, custom_action)
            self._signal_connection_states[state_key] = state
            # Sync cache with signal manager
            self._signal_manager._signal_connection_states[state_key] = state
            logger.debug(f"  -> Changed state to {state}")
        return True if state is None and widget_object["SIGNALS"] else state

    def changeSignalState(self, widget_path, signal_name, func, custom_action=None):
        """
        v4.0 S16: Change signal connection state.
        v4.0.6 FIX: Explicit flag update for LAYER_TREE_VIEW instead of relying on boolean logic.
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
            state = widget.isSignalConnected(self.getSignal(widget, signal_name))

        signal = getattr(widget, signal_name)
        should_connect = (custom_action == 'connect' and not state) or (custom_action is None and not state)
        should_disconnect = (custom_action == 'disconnect' and state) or (custom_action is None and state)

        # Perform connection/disconnection
        try:
            if should_disconnect:
                signal.disconnect(func)
                # EXPLICIT: Update flag immediately after disconnect
                if is_ltv:
                    self._layer_tree_view_signal_connected = False
            elif should_connect:
                signal.connect(func)
                # EXPLICIT: Update flag immediately after connect
                if is_ltv:
                    self._layer_tree_view_signal_connected = True
        except TypeError:
            # Signal was not connected or already in desired state
            pass

        # Return current state
        if is_ltv:
            return self._layer_tree_view_signal_connected
        else:
            return widget.isSignalConnected(self.getSignal(widget, signal_name))

    def reset_multiple_checkable_combobox(self) -> None:
        """Reset and recreate the multiple selection checkable combobox widget.

        Destroys the existing widget and creates a fresh instance. Used when
        the current layer changes to ensure the feature list is properly refreshed.

        Note:
            Handles RuntimeError gracefully if widget is already deleted.
            Automatically reconnects signals to exploring_features_changed.
        """
        try:
            layout = self.horizontalLayout_exploring_multiple_feature_picker
            if layout.count() > 0 and (item := layout.itemAt(0)) and item.widget():
                layout.removeWidget(item.widget()); item.widget().deleteLater()
            if hasattr(self, 'checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection') and self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection:
                try: self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection.reset(); self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection.close(); self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection.deleteLater()
                except (RuntimeError, AttributeError):  # Widget may already be deleted - expected during cleanup
                    pass
            # Recreate the widget
            self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection = QgsCheckableComboBoxFeaturesListPickerWidget(self.CONFIG_DATA, self)
            if self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection:
                layout.insertWidget(0, self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection, 1); layout.update()
                self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"] = {"TYPE": "CustomCheckableFeatureComboBox", "WIDGET": self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection,
                    "SIGNALS": [("updatingCheckedItemList", self.exploring_features_changed), ("filteringCheckedItemList", self.exploring_source_params_changed)]}
        except Exception as e: logger.warning(f"reset_multiple_checkable_combobox failed: {e}")

    def _fix_toolbox_icons(self):
        """v4.0 S18: Fix toolBox_tabTools icons with absolute paths."""
        for idx, icon_file in {0: "filter_multi.png", 1: "save.png", 2: "parameters.png"}.items():
            p = os.path.join(self.plugin_dir, "icons", icon_file)
            if os.path.exists(p): self.toolBox_tabTools.setItemIcon(idx, get_themed_icon(p) if ICON_THEME_AVAILABLE else QtGui.QIcon(p))

    def setupUiCustom(self) -> None:
        """Initialize custom UI components and configuration.

        Sets up components not defined in Qt Designer:
        - Custom checkable combobox widgets for layers and features
        - Splitter layout and dynamic dimensions
        - Tab icons with theme support
        - ConfigurationManager initialization
        - MVC controller integration

        Note:
            Must be called after setupUi() from Qt Designer generated code.
            Creates widgets before configure_widgets() can reference them.
        """
        # CRITICAL: Create all custom widgets FIRST (before configure_widgets() references them)
        self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection = QgsCheckableComboBoxFeaturesListPickerWidget(self.CONFIG_DATA, self)
        # FIX 2026-01-18 v14: Set dockwidget reference for sync protection checks
        self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection.setDockwidgetRef(self)
        # Don't override the widget's calculated minimum height - it knows its own size needs
        self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection.show()
        logger.debug(f"Created multiple selection widget: {self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection}")

        # Create custom combobox widgets early so configure_widgets() can reference them
        from .ui.widgets.custom_widgets import QgsCheckableComboBoxLayer
        self.checkableComboBoxLayer_filtering_layers_to_filter = QgsCheckableComboBoxLayer(self.dockWidgetContents)
        # Height managed by QSS (20px standard)
        self.checkableComboBoxLayer_filtering_layers_to_filter.show()
        logger.debug(f"Created filtering layers widget: {self.checkableComboBoxLayer_filtering_layers_to_filter}")

        self.checkableComboBoxLayer_exporting_layers = QgsCheckableComboBoxLayer(self.dockWidgetContents)
        # Height managed by QSS (20px standard)
        self.checkableComboBoxLayer_exporting_layers.show()
        logger.debug(f"Created exporting layers widget: {self.checkableComboBoxLayer_exporting_layers}")

        # Create centroids checkbox BEFORE configure_widgets() to ensure it's in the registry
        from qgis.PyQt import QtWidgets
        self.checkBox_filtering_use_centroids_distant_layers = QtWidgets.QCheckBox(self.dockWidgetContents)
        self.checkBox_filtering_use_centroids_distant_layers.setObjectName("checkBox_filtering_use_centroids_distant_layers")
        logger.debug(f"Created centroids distant layers checkbox: {self.checkBox_filtering_use_centroids_distant_layers}")

        # Initialize ConfigurationManager BEFORE tab widget setup (needed for custom widget creation)
        from .ui.managers.configuration_manager import ConfigurationManager
        if self._configuration_manager is None:
            self._configuration_manager = ConfigurationManager(self)

        if self._splitter_manager:
            self._splitter_manager.setup()
        else:
            self._setup_main_splitter()
        self.apply_dynamic_dimensions()
        self._fix_toolbox_icons()
        self._setup_backend_indicator()
        self._setup_action_bar_layout()
        self._setup_exploring_tab_widgets()
        self._setup_dual_mode_exploring()
        self._setup_filtering_tab_widgets()
        self._setup_exporting_tab_widgets()
        if 'CURRENT_PROJECT' in self.CONFIG_DATA:
            self.project_props = self.CONFIG_DATA["CURRENT_PROJECT"]
        self.manage_configuration_model()
        self.dockwidget_widgets_configuration()
        self._load_all_pushbutton_icons()
        self._setup_truncation_tooltips()

    def _load_all_pushbutton_icons(self):
        """v4.0 S16: Load icons from config.

        v4.0.3: Fixed icon sizes extraction to support both int and dict formats.
        """
        try:
            pb_cfg = self.CONFIG_DATA.get("APP", {}).get("DOCKWIDGET", {}).get("PushButton", {})
            icons, sizes = pb_cfg.get("ICONS", {}), pb_cfg.get("ICONS_SIZES", {})

            # Extract sizes - support both int direct and dict with "value" key
            sz_act_raw = sizes.get("ACTION", 24)
            sz_act = sz_act_raw.get("value", 24) if isinstance(sz_act_raw, dict) else sz_act_raw

            sz_oth_raw = sizes.get("OTHERS", 20)
            sz_oth = sz_oth_raw.get("value", 20) if isinstance(sz_oth_raw, dict) else sz_oth_raw

            if not icons:
                logger.warning("_load_all_pushbutton_icons: No icons found in CONFIG_DATA")
                logger.warning(f"CONFIG_DATA has APP: {bool(self.CONFIG_DATA.get('APP'))}")
                logger.warning(f"PushButton config exists: {bool(pb_cfg)}")
                return

            loaded_count = 0
            for grp in ["ACTION", "EXPLORING", "FILTERING", "EXPORTING"]:
                sz = sz_act if grp == "ACTION" else sz_oth
                icons_grp = icons.get(grp, {})
                logger.info(f"Group {grp}: {len(icons_grp)} icons configured")
                for name, ico_file in icons_grp.items():
                    attr = self._get_widget_attr_name(grp, name)
                    if not attr:
                        logger.debug(f"_load_all_pushbutton_icons: No mapping for {grp}.{name}")
                        continue
                    if not hasattr(self, attr):
                        logger.warning(f"_load_all_pushbutton_icons: Widget {attr} not found for {grp}.{name}")
                        continue
                    w, p = getattr(self, attr), os.path.join(self.plugin_dir, "icons", ico_file)
                    if not os.path.exists(p):
                        logger.warning(f"_load_all_pushbutton_icons: Icon file not found: {p}")
                        continue
                    icon = get_themed_icon(p) if ICON_THEME_AVAILABLE else QtGui.QIcon(p)
                    w.setIcon(icon)
                    w.setIconSize(QtCore.QSize(sz, sz))
                    loaded_count += 1
                    logger.info(f"✓ {grp}.{name}: {ico_file}")

            logger.info(f"_load_all_pushbutton_icons: Loaded {loaded_count} icons TOTAL")
        except Exception as e:
            logger.error(f"_load_all_pushbutton_icons failed: {e}")
            import traceback
            logger.debug(traceback.format_exc())

    def _get_widget_attr_name(self, widget_group, widget_name):
        """v3.1 Sprint 14: Map config names to widget attribute names."""
        widget_map = {
            ("ACTION", "FILTER"): "pushButton_action_filter",
            ("ACTION", "UNDO_FILTER"): "pushButton_action_undo_filter",
            ("ACTION", "REDO_FILTER"): "pushButton_action_redo_filter",
            ("ACTION", "UNFILTER"): "pushButton_action_unfilter",
            ("ACTION", "EXPORT"): "pushButton_action_export",
            ("ACTION", "ABOUT"): "pushButton_action_about",
            ("EXPLORING", "IDENTIFY"): "pushButton_exploring_identify",
            ("EXPLORING", "ZOOM"): "pushButton_exploring_zoom",
            ("EXPLORING", "IS_SELECTING"): "pushButton_checkable_exploring_selecting",
            ("EXPLORING", "IS_TRACKING"): "pushButton_checkable_exploring_tracking",
            ("EXPLORING", "IS_LINKING"): "pushButton_checkable_exploring_linking_widgets",
            ("EXPLORING", "RESET_ALL_LAYER_PROPERTIES"): "pushButton_exploring_reset_layer_properties",
            ("FILTERING", "AUTO_CURRENT_LAYER"): "pushButton_checkable_filtering_auto_current_layer",
            ("FILTERING", "HAS_LAYERS_TO_FILTER"): "pushButton_checkable_filtering_layers_to_filter",
            ("FILTERING", "HAS_COMBINE_OPERATOR"): "pushButton_checkable_filtering_current_layer_combine_operator",
            ("FILTERING", "HAS_GEOMETRIC_PREDICATES"): "pushButton_checkable_filtering_geometric_predicates",
            ("FILTERING", "HAS_BUFFER_VALUE"): "pushButton_checkable_filtering_buffer_value",
            ("FILTERING", "HAS_BUFFER_TYPE"): "pushButton_checkable_filtering_buffer_type",
            ("EXPORTING", "HAS_LAYERS_TO_EXPORT"): "pushButton_checkable_exporting_layers",
            ("EXPORTING", "HAS_PROJECTION_TO_EXPORT"): "pushButton_checkable_exporting_projection",
            ("EXPORTING", "HAS_STYLES_TO_EXPORT"): "pushButton_checkable_exporting_styles",
            ("EXPORTING", "HAS_DATATYPE_TO_EXPORT"): "pushButton_checkable_exporting_datatype",
            ("EXPORTING", "HAS_OUTPUT_FOLDER_TO_EXPORT"): "pushButton_checkable_exporting_output_folder",
            ("EXPORTING", "HAS_ZIP_TO_EXPORT"): "pushButton_checkable_exporting_zip"}
        return widget_map.get((widget_group, widget_name), "")

    def _setup_main_splitter(self):
        """v4.0 S16: Setup splitter."""
        from .ui.config import UIConfig
        try:
            self.main_splitter, cfg = self.splitter_main, UIConfig.get_config('splitter')
            hw, hm = cfg.get('handle_width', 6), cfg.get('handle_margin', 40)
            self.main_splitter.setChildrenCollapsible(cfg.get('collapsible', False))
            self.main_splitter.setHandleWidth(hw)
            self.main_splitter.setOpaqueResize(cfg.get('opaque_resize', True))
            self.main_splitter.setStyleSheet(f"QSplitter::handle:vertical{{background-color:#d0d0d0;height:{hw - 2}px;margin:2px {hm}px;border-radius:{(hw - 2) // 2}px;}}QSplitter::handle:vertical:hover{{background-color:#3498db;}}")
            self._apply_splitter_frame_policies()
            self.main_splitter.setStretchFactor(0, cfg.get('exploring_stretch', 2))
            self.main_splitter.setStretchFactor(1, cfg.get('toolset_stretch', 5))
            self._set_initial_splitter_sizes()
        except Exception: self.main_splitter = None

    def _apply_splitter_frame_policies(self):
        """v4.0 S16: Apply frame size policies and minimum heights."""
        from .ui.config import UIConfig
        from qgis.PyQt.QtWidgets import QSizePolicy as SP
        pm = {'Fixed': SP.Fixed, 'Minimum': SP.Minimum, 'Maximum': SP.Maximum, 'Preferred': SP.Preferred, 'Expanding': SP.Expanding, 'MinimumExpanding': SP.MinimumExpanding, 'Ignored': SP.Ignored}
        splitter_cfg = UIConfig.get_config('splitter') or {}
        for fn, defs in [('frame_exploring', ('Preferred', 'Minimum')), ('frame_toolset', ('Preferred', 'Expanding'))]:
            if hasattr(self, fn):
                cfg = UIConfig.get_config(fn) or {}
                frame = getattr(self, fn)
                frame.setSizePolicy(pm.get(cfg.get('size_policy_h', defs[0]), SP.Preferred), pm.get(cfg.get('size_policy_v', defs[1]), SP.Preferred))
                # Apply minimum heights from splitter config to prevent truncation
                min_key = 'min_exploring_height' if fn == 'frame_exploring' else 'min_toolset_height'
                min_height = splitter_cfg.get(min_key, cfg.get('min_height', 120 if fn == 'frame_exploring' else 200))
                frame.setMinimumHeight(min_height)

    def _set_initial_splitter_sizes(self):
        """v4.0 S16: Set splitter ratios."""
        from .ui.config import UIConfig
        cfg = UIConfig.get_config('splitter')
        tot = self.main_splitter.height() if self.main_splitter.height() >= 100 else 600
        self.main_splitter.setSizes([int(tot * cfg.get('initial_exploring_ratio', 0.50)), int(tot * cfg.get('initial_toolset_ratio', 0.50))])

    def apply_dynamic_dimensions(self):
        """
        Apply dynamic dimensions to widgets based on active UI profile (compact/normal).

        Orchestrates the application of dimensions by calling specialized methods.
        Called from setupUiCustom() during initialization.

        v4.0.6 FIX: Added proper error handling and logging for manager failures.
        """
        if self._dimensions_manager is not None:
            try:
                success = self._dimensions_manager.apply()
                if not success:
                    logger.warning("DimensionsManager.apply() returned False - UI may be misconfigured")
                    iface.messageBar().pushWarning("FilterMate", self.tr("UI configuration incomplete - check logs"))
                return
            except Exception as e:
                logger.error(f"DimensionsManager.apply() FAILED: {e}", exc_info=True)
                iface.messageBar().pushWarning("FilterMate", self.tr("UI dimension error: {}").format(str(e)))
                # Fall through to fallback methods

        try:
            self._apply_dockwidget_dimensions()
            self._apply_widget_dimensions()
            self._apply_frame_dimensions()
            self._harmonize_checkable_pushbuttons()

            if self._spacing_manager is not None:
                try:
                    success = self._spacing_manager.apply()
                    if not success:
                        logger.warning("SpacingManager.apply() returned False - using fallback")
                        self._apply_layout_spacing()
                        self._harmonize_spacers()
                        self._adjust_row_spacing()
                except Exception as e:
                    logger.error(f"SpacingManager.apply() FAILED: {e}", exc_info=True)
                    # Fallback to manual methods
                    self._apply_layout_spacing()
                    self._harmonize_spacers()
                    self._adjust_row_spacing()
            else:
                self._apply_layout_spacing()
                self._harmonize_spacers()
                self._adjust_row_spacing()

            self._apply_qgis_widget_dimensions()
            self._align_key_layouts()
            logger.info("Successfully applied dynamic dimensions to all widgets")
        except Exception as e:
            logger.error(f"Error applying dynamic dimensions: {e}", exc_info=True)
            import traceback
            traceback.print_exc()

    def _apply_dockwidget_dimensions(self):
        """
        Apply minimum size to the dockwidget based on active UI profile (compact/normal).

        This ensures the dockwidget can be resized smaller in compact mode,
        allowing better screen space management.
        """
        from .ui.config import UIConfig
        from qgis.PyQt.QtCore import QSize
        min_w, min_h = UIConfig.get_config('dockwidget', 'min_width'), UIConfig.get_config('dockwidget', 'min_height')
        pref_w, pref_h = UIConfig.get_config('dockwidget', 'preferred_width'), UIConfig.get_config('dockwidget', 'preferred_height')
        if min_w and min_h:
            self.setMinimumSize(QSize(min_w, min_h))
            logger.debug(f"Applied dockwidget minimum size: {min_w}x{min_h}px")
        if pref_w and pref_h and (self.size().width() > pref_w or self.size().height() > pref_h):
            self.resize(pref_w, pref_h)
            logger.debug(f"Resized dockwidget to preferred size: {pref_w}x{pref_h}px")

        # Apply minimum width to groupboxes to prevent overlap when splitter is resized
        self._apply_groupbox_minimum_widths()

    def _apply_widget_dimensions(self):
        """
        [DEPRECATED v4.0.3] Widget dimensions now managed by QSS.

        All widget heights (ComboBox, LineEdit, SpinBox, GroupBox) are defined in
        resources/styles/default.qss with standardized 20px height.

        This function is kept for backward compatibility but does nothing.
        QSS rules override any Python-side dimension settings.

        TODO v5.0: Remove this function entirely.
        """
        # Widget dimensions managed by QSS - no Python intervention needed
        logger.debug("Widget dimensions managed by QSS (20px standard)")

    def _apply_frame_dimensions(self):
        """
        Apply dimensions and size policies to frames and widget key containers.

        This method configures:
        - Widget key containers (sidebar buttons area)
        - Main frames (exploring, toolset)
        - Sub-frames (filtering)

        Size policies work in conjunction with the splitter configuration
        to ensure proper resize behavior.
        """
        from .ui.config import UIConfig
        from qgis.PyQt.QtWidgets import QSizePolicy
        policy_map = {'Fixed': QSizePolicy.Fixed, 'Minimum': QSizePolicy.Minimum,
                      'Maximum': QSizePolicy.Maximum, 'Preferred': QSizePolicy.Preferred,
                      'Expanding': QSizePolicy.Expanding, 'MinimumExpanding': QSizePolicy.MinimumExpanding,
                      'Ignored': QSizePolicy.Ignored}
        wk_min = UIConfig.get_config('widget_keys', 'min_width')
        wk_max = UIConfig.get_config('widget_keys', 'max_width')
        wk_cfg = UIConfig.get_config('widget_keys') or {}
        wk_pad = wk_cfg.get('padding', 2)
        for wn in ['widget_exploring_keys', 'widget_filtering_keys', 'widget_exporting_keys']:
            if hasattr(self, wn):
                w = getattr(self, wn)
                w.setMinimumWidth(wk_min)
                w.setMaximumWidth(wk_max)
                if w.layout():
                    w.layout().setContentsMargins(wk_pad, wk_pad, wk_pad, wk_pad)
                    w.layout().setSpacing(0)
        exp_cfg = UIConfig.get_config('frame_exploring') or {}
        exp_min = exp_cfg.get('min_height', 120)
        exp_max = exp_cfg.get('max_height', 350)
        exp_v_policy = exp_cfg.get('size_policy_v', 'Minimum')
        if hasattr(self, 'frame_exploring'):
            self.frame_exploring.setMinimumHeight(exp_min)
            self.frame_exploring.setMaximumHeight(exp_max)
            self.frame_exploring.setSizePolicy(policy_map.get(exp_cfg.get('size_policy_h', 'Preferred'), QSizePolicy.Preferred),
                                               policy_map.get(exp_v_policy, QSizePolicy.Minimum))
        ts_cfg = UIConfig.get_config('frame_toolset') or {}
        ts_min = ts_cfg.get('min_height', 200)
        ts_v_policy = ts_cfg.get('size_policy_v', 'Expanding')
        if hasattr(self, 'frame_toolset'):
            self.frame_toolset.setMinimumHeight(ts_min)
            self.frame_toolset.setMaximumHeight(ts_cfg.get('max_height', 16777215))
            self.frame_toolset.setSizePolicy(policy_map.get(ts_cfg.get('size_policy_h', 'Preferred'), QSizePolicy.Preferred),
                                             policy_map.get(ts_v_policy, QSizePolicy.Expanding))
        flt_cfg = UIConfig.get_config('frame_filtering') or {}
        if hasattr(self, 'frame_filtering'):
            self.frame_filtering.setMinimumHeight(flt_cfg.get('min_height', 180))
        logger.debug(f"Applied frame dimensions: exploring={exp_min}-{exp_max}px ({exp_v_policy}), toolset={ts_min}px+ ({ts_v_policy}), widget_keys={wk_min}-{wk_max}px")

    def _harmonize_checkable_pushbuttons(self):
        """
        Harmonize dimensions of all checkable pushbuttons across tabs.

        Applies consistent sizing to exploring, filtering, and exporting pushbuttons
        based on the active UI profile (compact/normal/hidpi) using key_button dimensions
        from UIConfig.
        """
        if self._controller_integration and self._controller_integration.delegate_harmonize_checkable_pushbuttons():
            return
        # Fallback: Apply pushbutton dimensions directly
        try:
            from qgis.PyQt.QtWidgets import QPushButton, QSizePolicy
            from qgis.PyQt.QtCore import QSize
            from .ui.config import UIConfig, DisplayProfile
            key_cfg = UIConfig.get_config('key_button') or {}
            profile = UIConfig.get_profile()
            if profile == DisplayProfile.COMPACT:
                min_size, max_size, icon_size = 26, 32, 16
                mode_name = 'compact'
            elif profile == DisplayProfile.HIDPI:
                min_size, max_size, icon_size = 36, 44, 24
                mode_name = 'hidpi'
            else:
                min_size, max_size, icon_size = key_cfg.get('min_size', 30), key_cfg.get('max_size', 36), key_cfg.get('icon_size', 18)
                mode_name = 'normal'
            buttons = ['pushButton_exploring_identify', 'pushButton_exploring_zoom', 'pushButton_checkable_exploring_selecting',
                       'pushButton_checkable_exploring_tracking', 'pushButton_checkable_exploring_linking_widgets',
                       'pushButton_exploring_reset_layer_properties', 'pushButton_checkable_filtering_auto_current_layer',
                       'pushButton_checkable_filtering_layers_to_filter', 'pushButton_checkable_filtering_current_layer_combine_operator',
                       'pushButton_checkable_filtering_geometric_predicates', 'pushButton_checkable_filtering_buffer_value',
                       'pushButton_checkable_filtering_buffer_type', 'pushButton_checkable_exporting_layers',
                       'pushButton_checkable_exporting_projection', 'pushButton_checkable_exporting_styles',
                       'pushButton_checkable_exporting_datatype', 'pushButton_checkable_exporting_output_folder',
                       'pushButton_checkable_exporting_zip']
            checkable_buttons = []
            for name in buttons:
                if hasattr(self, name):
                    btn = getattr(self, name)
                    if isinstance(btn, QPushButton):
                        btn.setMinimumSize(min_size, min_size)
                        btn.setMaximumSize(max_size, max_size)
                        btn.setIconSize(QSize(icon_size, icon_size))
                        btn.setFlat(True)
                        btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                        checkable_buttons.append(name)
            logger.debug(f"Harmonized {len(checkable_buttons)} key pushbuttons in {mode_name} mode: {min_size}-{max_size}px (icon: {icon_size}px)")
        except Exception as e:
            logger.warning(f"Could not harmonize checkable pushbuttons: {e}")

    def _apply_layout_spacing(self):
        """v3.1 Sprint 14: Apply layout spacing with fallback."""
        if self._controller_integration and self._controller_integration.delegate_apply_layout_spacing():
            return
        # Fallback: Apply spacing directly
        try:
            from .ui.config import UIConfig
            layout_spacing = UIConfig.get_config('layout', 'spacing_frame') or 8
            content_spacing = UIConfig.get_config('layout', 'spacing_content') or 6
            main_margins = UIConfig.get_config('layout', 'margins_main') or 2
            key_cfg = UIConfig.get_config('key_button') or {}
            button_spacing = key_cfg.get('spacing', 2)
            # Apply reduced margins to main layouts (verticalLayout_8, verticalLayout_main)
            for name in ['verticalLayout_8', 'verticalLayout_main']:
                if hasattr(self, name):
                    getattr(self, name).setContentsMargins(main_margins, 0, main_margins, 0)
                    getattr(self, name).setSpacing(0)
            # Apply zero margins to exploring content layouts
            for name in ['verticalLayout_main_content', 'gridLayout_main_header', 'gridLayout_main_actions']:
                if hasattr(self, name):
                    getattr(self, name).setContentsMargins(0, 0, 0, 0)
                    getattr(self, name).setSpacing(2)
            # Configure column stretch for proper groupbox display
            if hasattr(self, 'gridLayout_main_actions'):
                self.gridLayout_main_actions.setColumnStretch(0, 0)  # Keys: fixed
                self.gridLayout_main_actions.setColumnStretch(1, 1)  # Content: expand
            # Apply minimal margins to groupbox content layouts
            for name in ['verticalLayout_exploring_tabs_content']:
                if hasattr(self, name):
                    getattr(self, name).setContentsMargins(0, 0, 0, 0)
                    getattr(self, name).setSpacing(2)
            # Apply spacing to exploring layouts
            for name in ['verticalLayout_exploring_single_selection', 'verticalLayout_exploring_multiple_selection', 'verticalLayout_exploring_custom_selection']:
                if hasattr(self, name): getattr(self, name).setSpacing(layout_spacing)
            # Apply button spacing to key layouts
            for name in ['verticalLayout_filtering_keys', 'verticalLayout_exporting_keys', 'verticalLayout_exploring_content']:
                if hasattr(self, name): getattr(self, name).setSpacing(button_spacing)
            # Apply content spacing
            for name in ['verticalLayout_filtering_values', 'verticalLayout_exporting_values']:
                if hasattr(self, name): getattr(self, name).setSpacing(content_spacing)
            logger.debug(f"Applied harmonized layout spacing: {layout_spacing}px, main margins: {main_margins}px")
        except Exception as e:
            logger.debug(f"Could not apply layout spacing: {e}")

    def _harmonize_spacers(self):
        """
        Harmonize vertical spacers across all key widget sections.

        Applies consistent spacer dimensions to exploring/filtering/exporting key widgets
        based on section-specific sizes from UI config.
        """
        try:
            from qgis.PyQt.QtWidgets import QSpacerItem; from .ui.elements import get_spacer_size; from .ui.config import UIConfig, DisplayProfile
            is_compact = UIConfig._active_profile == DisplayProfile.COMPACT
            mode_name = 'compact' if is_compact else 'normal'
            spacer_sizes = {}
            for section, widget_name in [('exploring', 'widget_exploring_keys'), ('filtering', 'widget_filtering_keys'), ('exporting', 'widget_exporting_keys')]:
                target_h = get_spacer_size(f'verticalSpacer_{section}_keys_field_top' if section != 'exploring' else 'verticalSpacer_exploring_tab_top', is_compact)
                spacer_sizes[section] = target_h
                spacer_count = 0
                if hasattr(self, widget_name) and (layout := getattr(self, widget_name).layout()):
                    for i in range(layout.count()):
                        if (item := layout.itemAt(i)) and hasattr(item, 'layout') and item.layout():
                            for j in range(item.layout().count()):
                                if (nested := item.layout().itemAt(j)) and isinstance(nested, QSpacerItem):
                                    nested.changeSize(20, target_h, nested.sizePolicy().horizontalPolicy(), nested.sizePolicy().verticalPolicy())
                                    spacer_count += 1
                if spacer_count > 0:
                    logger.debug(f"Harmonized {spacer_count} spacers in {section} to {target_h}px")
            logger.debug(f"Applied spacer dimensions ({mode_name} mode): {spacer_sizes}")
        except Exception as e:
            logger.warning(f"Could not harmonize spacers: {e}")

    def _apply_qgis_widget_dimensions(self):
        """
        [PARTIALLY DEPRECATED v4.0.3] QGIS widget dimensions now managed by QSS.

        Only QgsPropertyOverrideButton still needs Python sizing (22px fixed).
        All other QGIS widgets inherit 20px height from QSS rules.

        TODO v5.0: Extract QgsPropertyOverrideButton sizing to separate function.
        """
        try:
            from qgis.PyQt.QtWidgets import QSizePolicy
            from qgis.gui import QgsPropertyOverrideButton
            # QGIS widgets heights managed by QSS (20px standard)
            # Only PropertyOverrideButton needs manual sizing
            for w in self.findChildren(QgsPropertyOverrideButton):
                w.setFixedSize(22, 22)
                w.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            logger.debug("QGIS widget dimensions managed by QSS (20px), PropertyOverrideButton=22px")
        except Exception as e:
            logger.debug(f"Could not apply dimensions to PropertyOverrideButton: {e}")

    def _apply_groupbox_minimum_widths(self):
        """
        v4.0.2: Apply minimum width to groupboxes to prevent widget overlap.

        When the QSplitter is resized to be narrow, widgets inside groupboxes
        can overlap. This method sets a minimum width on all groupboxes based
        on the active UI profile to ensure proper layout behavior.
        """
        try:
            from qgis.PyQt.QtWidgets import QGroupBox
            from .ui.config import UIConfig

            groupbox_min_width = UIConfig.get_config('groupbox', 'min_width')
            if not groupbox_min_width:
                return

            # Apply to all QGroupBox widgets
            for gb in self.findChildren(QGroupBox):
                gb.setMinimumWidth(groupbox_min_width)

            logger.debug(f"Applied groupbox minimum width: {groupbox_min_width}px to prevent overlap")
        except Exception as e:
            logger.debug(f"Could not apply groupbox minimum widths: {e}")

    def _align_key_layouts(self):
        """
        Align key layouts (exploring/filtering/exporting) for visual consistency.

        Sets consistent spacing, margins, and alignment for all key widget layouts
        and their parent containers. Harmonizes vertical bars of pushbuttons.
        """
        if self._controller_integration and self._controller_integration.delegate_align_key_layouts():
            return
        # Fallback: Apply alignment directly
        try:
            from .ui.config import UIConfig
            margins = UIConfig.get_config('layout', 'margins_frame') or {'left': 4, 'top': 4, 'right': 4, 'bottom': 6}
            left, top, right, bottom = margins.get('left', 4), margins.get('top', 4), margins.get('right', 4), margins.get('bottom', 6)
            key_cfg = UIConfig.get_config('key_button') or {}
            button_spacing = key_cfg.get('spacing', 2)
            widget_keys_config = UIConfig.get_config('widget_keys') or {}
            widget_keys_padding = widget_keys_config.get('padding', 1)
            # Align horizontal layouts with zero margins for visual consistency
            for name in ['horizontalLayout_filtering_content', 'horizontalLayout_exporting_content']:
                if hasattr(self, name):
                    layout = getattr(self, name)
                    layout.setContentsMargins(0, 0, 0, 0)
            # Apply margins to groupbox layouts
            for name in ['gridLayout_exploring_single_content', 'gridLayout_exploring_multiple_content', 'verticalLayout_exploring_custom_container']:
                if hasattr(self, name):
                    getattr(self, name).setContentsMargins(left, top, right, bottom)
            # Apply margins to value layouts
            for name in ['verticalLayout_filtering_values', 'verticalLayout_exporting_values']:
                if hasattr(self, name):
                    getattr(self, name).setContentsMargins(left, top, right, bottom)
            logger.debug(f"Aligned key layouts with {button_spacing}px spacing, {widget_keys_padding}px padding")
        except Exception as e:
            logger.warning(f"Could not align key layouts: {e}")

    def _adjust_row_spacing(self):
        """
        Adjust row spacing for filtering/exporting alignment.

        Ensures consistent vertical spacing between widgets in filtering and exporting tabs.
        """
        try:
            from qgis.PyQt.QtWidgets import QSpacerItem; from .ui.elements import get_spacer_size; from .ui.config import UIConfig, DisplayProfile
            is_compact = UIConfig._active_profile == DisplayProfile.COMPACT
            layout_spacing = UIConfig.get_config('layout', 'spacing_frame') or 4
            for name, layout_attr in [('filtering', 'verticalLayout_filtering_values'), ('exporting', 'verticalLayout_exporting_values')]:
                target = get_spacer_size(f'verticalSpacer_{name}_keys_field_top', is_compact)
                if hasattr(self, layout_attr) and (layout := getattr(self, layout_attr)):
                    for i in range(layout.count()):
                        if (item := layout.itemAt(i)) and isinstance(item, QSpacerItem): item.changeSize(item.sizeHint().width(), target, item.sizePolicy().horizontalPolicy(), item.sizePolicy().verticalPolicy())
                    layout.setSpacing(layout_spacing)
            logger.debug(f"Adjusted row spacing: filtering/exporting aligned with {layout_spacing}px spacing")
        except Exception as e:
            logger.warning(f"Could not adjust row spacing: {e}")

    def _setup_backend_indicator(self):
        """v4.0 S16: Create header with indicators."""
        self.frame_header = QtWidgets.QFrame(self.dockWidgetContents)
        self.frame_header.setObjectName("frame_header"); self.frame_header.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.frame_header.setFixedHeight(13)  # Compact layout, closer to frame_exploring
        hl = QtWidgets.QHBoxLayout(self.frame_header)
        hl.setContentsMargins(2, 0, 2, 0); hl.setSpacing(3)  # Slight spacing increase for better visual
        hl.addSpacerItem(QtWidgets.QSpacerItem(40, 6, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))
        self.plugin_title_label = None
        # Softer "mousse" style with rounded corners
        bb = "color:white;font-size:8pt;font-weight:500;padding:2px 8px;border-radius:10px;border:none;"
        # Softer colors with better hover transitions
        self.favorites_indicator_label = self._create_indicator_label("label_favorites_indicator", "★", bb + "background-color:#f5b041;", bb + "background-color:#f39c12;", "★ Favorites\nClick to manage", self._on_favorite_indicator_clicked, 32)
        hl.addWidget(self.favorites_indicator_label)
        self.backend_indicator_label = self._create_indicator_label("label_backend_indicator", "OGR" if self.has_loaded_layers else "...", bb + "background-color:#5dade2;", bb + "background-color:#3498db;", "Click to change backend", self._on_backend_indicator_clicked, 38)
        hl.addWidget(self.backend_indicator_label)
        self.forced_backends = {}
        if hasattr(self, 'verticalLayout_8'): self.verticalLayout_8.insertWidget(0, self.frame_header)

    def _create_indicator_label(self, name, text, style, hover_style, tooltip, click_handler, min_width):
        """v4.0 S16: Create indicator label with soft "mousse" style."""
        lbl = ClickableLabel(self.frame_header)
        lbl.setObjectName(name); lbl.setText(text); lbl.setStyleSheet(f"QLabel#{name}{{{style}}}QLabel#{name}:hover{{{hover_style}}}")
        lbl.setAlignment(Qt.AlignCenter); lbl.setMinimumWidth(min_width); lbl.setFixedHeight(18)  # Fixed height for proper text display with padding
        lbl.setCursor(Qt.PointingHandCursor); lbl.setToolTip(tooltip)
        # CRITICAL: Enable the widget to receive mouse events
        lbl.setEnabled(True)
        lbl.setAttribute(Qt.WA_Hover, True)  # Enable hover events
        lbl.set_click_handler(click_handler)
        logger.debug(f"Created indicator {name}: enabled={lbl.isEnabled()}, visible={lbl.isVisible()}, handler={click_handler is not None}")
        return lbl

    def _on_backend_indicator_clicked(self, event):
        """v4.0 Sprint 19: → BackendController."""
        logger.debug("_on_backend_indicator_clicked called")

        if self._controller_integration and self._controller_integration.backend_controller:
            # Use QTimer to defer menu display after mouse event completes
            # This prevents issues with QMenu.exec_() during mousePressEvent
            from qgis.PyQt.QtCore import QTimer
            QTimer.singleShot(0, self._controller_integration.delegate_handle_backend_click)
        else:
            logger.warning("Backend controller unavailable")

    def _on_favorite_indicator_clicked(self, event):
        """v4.0 S16: → FavoritesController."""
        logger.debug("_on_favorite_indicator_clicked called")
        logger.debug(f"_favorites_ctrl = {self._favorites_ctrl}")

        if self._favorites_ctrl:
            # Use QTimer to defer menu display after mouse event completes
            # This prevents issues with QMenu.exec_() during mousePressEvent
            from qgis.PyQt.QtCore import QTimer
            QTimer.singleShot(0, self._favorites_ctrl.handle_indicator_clicked)
        else:
            logger.warning("Favorites controller unavailable")

    def _add_current_to_favorites(self):
        """v4.0 S16: → FavoritesController."""
        if self._favorites_ctrl:
            self._favorites_ctrl.add_current_to_favorites()

    def _apply_favorite(self, favorite_id: str):
        """v4.0 S16: → FavoritesController."""
        if self._favorites_ctrl:
            self._favorites_ctrl.apply_favorite(favorite_id)

    def _show_favorites_manager_dialog(self):
        """v4.0 S16: → FavoritesController."""
        if not (self._controller_integration and self._controller_integration.delegate_favorites_show_manager_dialog()):
            show_warning("FilterMate", self.tr("Favorites manager not available"))

    def _export_favorites(self):
        """v4.0 S16: → FavoritesController."""
        if self._favorites_ctrl:
            self._favorites_ctrl.export_favorites()

    def _import_favorites(self):
        """v4.0 S16: → FavoritesController."""
        if self._favorites_ctrl:
            result = self._favorites_ctrl.import_favorites()
            if result: self._update_favorite_indicator()

    def _update_favorite_indicator(self):
        """v4.0 S16: Update favorites badge."""
        if not hasattr(self, 'favorites_indicator_label') or not self.favorites_indicator_label: return
        fm, cnt = getattr(self, '_favorites_manager', None), getattr(getattr(self, '_favorites_manager', None), 'count', 0)
        if cnt > 0:
            self.favorites_indicator_label.setText(f"★ {cnt}")
            self.favorites_indicator_label.setToolTip(self.tr("★ {0} Favorites saved\nClick to apply or manage").format(cnt))
            self.favorites_indicator_label.setStyleSheet("QLabel#label_favorites_indicator{color:white;font-size:8pt;font-weight:500;padding:2px 8px;border-radius:10px;border:none;background-color:#f39c12;}QLabel#label_favorites_indicator:hover{background-color:#d68910;}")
        else:
            self.favorites_indicator_label.setText("★")
            self.favorites_indicator_label.setToolTip(self.tr("★ No favorites saved\nClick to add current filter"))
            self.favorites_indicator_label.setStyleSheet("QLabel#label_favorites_indicator{color:#95a5a6;font-size:8pt;font-weight:500;padding:2px 8px;border-radius:10px;border:none;background-color:#ecf0f1;}QLabel#label_favorites_indicator:hover{background-color:#d5dbdb;}")
        self.favorites_indicator_label.adjustSize()

    def _get_available_backends_for_layer(self, layer):
        """Sprint 18: → BackendController via _backend_ctrl property."""
        return self._backend_ctrl.get_available_backends_for_layer(layer) if self._backend_ctrl else [('ogr', 'OGR', '📁')]

    def _detect_current_backend(self, layer):
        """Sprint 18: → BackendController via _backend_ctrl property."""
        return self._backend_ctrl.get_current_backend(layer) if self._backend_ctrl else 'ogr'

    def _set_forced_backend(self, layer_id, backend_type):
        """Sprint 18: → BackendController via _backend_ctrl property."""
        if self._backend_ctrl: self._backend_ctrl.set_forced_backend(layer_id, backend_type)

    def _force_backend_for_all_layers(self, backend_type):
        """Sprint 18: → BackendController via _backend_ctrl property."""
        if self._backend_ctrl:
            count = self._backend_ctrl.force_backend_for_all_layers(backend_type)
            show_success("FilterMate", self.tr("Forced {0} backend for {1} layer(s)").format(backend_type.upper(), count))
        else:
            show_warning("FilterMate", self.tr("Backend controller not available"))

    def get_forced_backend_for_layer(self, layer_id):
        """Sprint 18: → BackendController via _backend_ctrl property."""
        return self._backend_ctrl.forced_backends.get(layer_id) if self._backend_ctrl else None

    def _get_optimal_backend_for_layer(self, layer):
        """Sprint 18: → BackendController via _backend_ctrl property."""
        return self._backend_ctrl._get_optimal_backend_for_layer(layer) if self._backend_ctrl else 'ogr'

    # ========================================
    # POSTGRESQL MAINTENANCE METHODS
    # ========================================

    def _get_pg_session_context(self):
        """Sprint 18: → BackendController via _backend_ctrl property."""
        return self._backend_ctrl.get_pg_session_context() if self._backend_ctrl else (None, None, None, None)

    def _toggle_pg_auto_cleanup(self):
        """Sprint 18: → BackendController via _backend_ctrl property."""
        if self._backend_ctrl:
            enabled = self._backend_ctrl.toggle_pg_auto_cleanup()
            msg = self.tr("PostgreSQL auto-cleanup enabled") if enabled else self.tr("PostgreSQL auto-cleanup disabled")
            (show_success if enabled else show_info)("FilterMate", msg)

    def _cleanup_postgresql_session_views(self):
        """Sprint 18: → BackendController via _backend_ctrl property."""
        if self._backend_ctrl:
            success = self._backend_ctrl.cleanup_postgresql_session_views()
            (show_success if success else show_warning)("FilterMate", self.tr("PostgreSQL session views cleaned up") if success else self.tr("No views to clean or cleanup failed"))
        else:
            show_warning("FilterMate", self.tr("Backend controller not available"))

    def _cleanup_postgresql_schema_if_empty(self):
        """Sprint 18: → BackendController via _backend_ctrl property."""
        from qgis.PyQt.QtWidgets import QMessageBox
        if self._backend_ctrl:
            info = self._backend_ctrl.get_postgresql_session_info()

            if not info.get('connection_available'):
                show_warning("FilterMate", self.tr("No PostgreSQL connection available"))
                return

            # Check for other sessions' views
            other_count = info.get('total_views_count', 0) - info.get('our_views_count', 0)
            if other_count > 0:
                msg = self.tr("Schema has {0} view(s) from other sessions.\nDrop anyway?").format(other_count)
                if QMessageBox.question(self, self.tr("Other Sessions Active"), msg,
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                    show_info("FilterMate", self.tr("Schema cleanup cancelled"))
                    return

            success = self._backend_ctrl.cleanup_postgresql_schema_if_empty(force=True)
            if success:
                show_success("FilterMate", self.tr("Schema '{0}' dropped successfully").format(info.get('schema')))
            else:
                show_warning("FilterMate", self.tr("Schema cleanup failed"))
        else:
            show_warning("FilterMate", self.tr("Backend controller not available"))

    def _show_postgresql_session_info(self):
        """Sprint 18: → BackendController via _backend_ctrl property."""
        from qgis.PyQt.QtWidgets import QMessageBox
        if self._backend_ctrl:
            info = self._backend_ctrl.get_postgresql_session_info()

            session_id = info.get('session_id') or 'Not set'
            html = (
                f"<b>Session ID:</b> {session_id}<br>"
                f"<b>Schema:</b> {info.get('schema')}<br>"
                f"<b>Auto-cleanup:</b> {'Yes' if info.get('auto_cleanup') else 'No'}<br>"
                f"<b>Connection:</b> {'Available' if info.get('connection_available') else 'Not available'}<br>"
            )
            if info.get('connection_available'):
                html += (
                    f"<b>Schema exists:</b> {'Yes' if info.get('schema_exists') else 'No'}<br>"
                    f"<b>Your views:</b> {info.get('our_views_count', 0)}<br>"
                    f"<b>Total views:</b> {info.get('total_views_count', 0)}<br>"
                )
            if 'error' in info:
                html += f"<b>Error:</b> {info['error']}<br>"

            QMessageBox.information(self, self.tr("PostgreSQL Session Info"), html)
        else:
            show_warning("FilterMate", self.tr("Backend controller not available"))

    # ========================================
    # OPTIMIZATION SETTINGS METHODS
    # ========================================

    def _toggle_optimization_enabled(self):
        """v4.0 S16: → BackendController."""
        if self._backend_ctrl:
            enabled = self._backend_ctrl.toggle_optimization_enabled()
            (show_success if enabled else show_info)("FilterMate", self.tr("Auto-optimization {0}").format(self.tr("enabled") if enabled else self.tr("disabled")))

    def _toggle_centroid_auto(self):
        """v4.0 S16: → BackendController."""
        if self._backend_ctrl:
            enabled = self._backend_ctrl.toggle_centroid_auto()
            (show_success if enabled else show_info)("FilterMate", self.tr("Auto-centroid {0}").format(self.tr("enabled") if enabled else self.tr("disabled")))

    def _toggle_optimization_ask_before(self):
        """v4.0 S16: Toggle confirmation."""
        self._optimization_ask_before = not getattr(self, '_optimization_ask_before', True)
        (show_success if self._optimization_ask_before else show_info)("FilterMate", self.tr("Confirmation {0}").format(self.tr("enabled") if self._optimization_ask_before else self.tr("disabled")))

    def _analyze_layer_optimizations(self):
        """v4.0 S16: Analyze layer optimizations."""
        if not self.current_layer: show_warning("FilterMate", self.tr("No layer selected. Please select a layer first.")); return
        try:
            from .core.services.auto_optimizer import LayerAnalyzer, AutoOptimizer, AUTO_OPTIMIZER_AVAILABLE
            if not AUTO_OPTIMIZER_AVAILABLE: show_warning("FilterMate", self.tr("Auto-optimizer module not available")); return
            layer_analysis = LayerAnalyzer().analyze_layer(self.current_layer)
            if not layer_analysis: show_info("FilterMate", self.tr("Could not analyze layer '{0}'").format(self.current_layer.name())); return
            has_buf = getattr(self, 'mQgsDoubleSpinBox_filtering_buffer_value', None) and self.mQgsDoubleSpinBox_filtering_buffer_value.value() != 0.0
            has_buf_type = getattr(self, 'checkBox_filtering_buffer_type', None) and self.checkBox_filtering_buffer_type.isChecked()
            recommendations = AutoOptimizer().get_recommendations(layer_analysis, user_centroid_enabled=self._is_centroid_already_enabled(self.current_layer), has_buffer=has_buf, has_buffer_type=has_buf_type, is_source_layer=True)
            if not recommendations: show_success("FilterMate", self.tr("Layer '{0}' is already optimally configured.\nType: {1}\nFeatures: {2:,}").format(self.current_layer.name(), layer_analysis.location_type.value, layer_analysis.feature_count)); return
            from .ui.dialogs.optimization_dialog import RecommendationDialog as OptimizationRecommendationDialog
            dialog = OptimizationRecommendationDialog(layer_name=self.current_layer.name(), recommendations=[r.to_dict() for r in recommendations],
                feature_count=layer_analysis.feature_count, location_type=layer_analysis.location_type.value, parent=self)
            if dialog.exec_():
                self._apply_optimization_selections(dialog.get_selected_optimizations(), self.current_layer)
        except ImportError as e:
            show_warning("FilterMate", self.tr("Auto-optimizer not available: {0}").format(str(e)))
        except Exception as e:
            show_warning("FilterMate", self.tr("Error analyzing layer: {0}").format(str(e)[:50]))

    def _apply_optimization_selections(self, selected, layer):
        """v3.1 Sprint 15: Apply selected optimization overrides."""
        applied = []
        overrides = [('use_centroid_distant', '_layer_centroid_overrides', "Use Centroids"),
                     ('simplify_before_buffer', '_layer_simplify_buffer_overrides', "Simplify before buffer"),
                     ('reduce_buffer_segments', '_layer_reduced_segments_overrides', "Reduce buffer segments (3)")]
        for key, attr, label in overrides:
            if selected.get(key, False):
                if not hasattr(self, attr): setattr(self, attr, {})
                getattr(self, attr)[layer.id()] = True
                if key == 'reduce_buffer_segments':
                    self.mQgsSpinBox_filtering_buffer_segments.setValue(3)
                applied.append(label)
        if applied:
            show_success("FilterMate", self.tr("Applied to '{0}':\n{1}").format(layer.name(), "\n".join(f"• {a}" for a in applied)))
        else:
            show_info("FilterMate", self.tr("No optimizations selected to apply."))

    def _show_optimization_settings_dialog(self):
        """v3.1 Sprint 15: Show optimization settings dialog."""
        try:
            from .ui.dialogs.optimization_dialog import OptimizationDialog as BackendOptimizationDialog
            dialog = BackendOptimizationDialog(self)
            if dialog.exec_():
                self._apply_optimization_dialog_settings(dialog.get_settings())
        except ImportError:
            try:
                from .ui.dialogs.optimization_dialog import OptimizationDialog as OptimizationSettingsDialog
                dialog = OptimizationSettingsDialog(self)
                if dialog.exec_():
                    s = dialog.get_settings()
                    self._optimization_enabled = s.get('enabled', True)
                    self._centroid_auto_enabled = s.get('auto_centroid_for_distant', True)
                    self._optimization_ask_before = s.get('ask_before_apply', True)
                    if not hasattr(self, '_optimization_thresholds'): self._optimization_thresholds = {}
                    self._optimization_thresholds['centroid_distant'] = s.get('centroid_threshold_distant', get_optimization_thresholds(ENV_VARS)['centroid_optimization_threshold'])
                    show_success("FilterMate", self.tr("Optimization settings saved"))
            except ImportError as e:
                show_warning("FilterMate", self.tr("Dialog not available: {0}").format(str(e)))
        except Exception as e:
            show_warning("FilterMate", self.tr("Error: {0}").format(str(e)[:50]))

    def _apply_optimization_dialog_settings(self, all_settings):
        """v3.1 Sprint 15: Apply settings from optimization dialog."""
        global_s = all_settings.get('global', {})
        self._optimization_enabled = global_s.get('auto_optimization_enabled', True)
        self._centroid_auto_enabled = global_s.get('auto_centroid', {}).get('enabled', True)
        self._optimization_ask_before = global_s.get('ask_before_apply', True)
        if not hasattr(self, '_optimization_thresholds'): self._optimization_thresholds = {}
        self._optimization_thresholds['centroid_distant'] = global_s.get('auto_centroid', {}).get('distant_threshold', 5000)
        self._backend_optimization_settings = all_settings
        show_success("FilterMate", self.tr("Backend optimization settings saved"))

    def _show_backend_optimization_dialog(self):
        """Show backend optimization dialog."""
        try:
            from .ui.dialogs.optimization_dialog import OptimizationDialog as BackendOptimizationDialog
            dialog = BackendOptimizationDialog(self)
            if not dialog.exec_(): return
            all_settings, global_s = dialog.get_settings(), dialog.get_settings().get('global', {})
            self._backend_optimization_settings = all_settings
            self._optimization_enabled = global_s.get('auto_optimization_enabled', True)
            self._centroid_auto_enabled = global_s.get('auto_centroid', {}).get('enabled', True)
            self._optimization_ask_before = global_s.get('ask_before_apply', True)
            pg_mv = all_settings.get('postgresql', {}).get('materialized_views', {}); self._pg_auto_cleanup_enabled = pg_mv.get('auto_cleanup', True)
            if not hasattr(self, '_optimization_thresholds'): self._optimization_thresholds = {}
            self._optimization_thresholds.update({'centroid_distant': global_s.get('auto_centroid', {}).get('distant_threshold', 5000), 'mv_threshold': pg_mv.get('threshold', 10000)})
            show_success("FilterMate", self.tr("Backend optimizations configured"))
        except ImportError as e: show_warning("FilterMate", self.tr("Dialog not available: {0}").format(str(e)))
        except Exception as e: show_warning("FilterMate", self.tr("Error: {0}").format(str(e)[:50]))

    def get_backend_optimization_setting(self, backend: str, setting_path: str, default=None):
        """Get backend optimization setting by path."""
        current = getattr(self, '_backend_optimization_settings', {}).get(backend, {})
        for part in setting_path.split('.'): current = current.get(part, default) if isinstance(current, dict) else default
        return current

    def _is_centroid_already_enabled(self, layer) -> bool:
        """Check if centroid optimization is already enabled."""
        lid = layer.id() if layer else None
        if hasattr(self, '_layer_centroid_overrides') and lid and self._layer_centroid_overrides.get(lid, False): return True
        return (hasattr(self, 'checkBox_filtering_use_centroids_distant_layers') and self.checkBox_filtering_use_centroids_distant_layers.isChecked()) or \
               (hasattr(self, 'checkBox_filtering_use_centroids_source_layer') and self.checkBox_filtering_use_centroids_source_layer.isChecked())

    def should_use_centroid_for_layer(self, layer) -> bool:
        """Check if centroid optimization should be used for a layer."""
        if hasattr(self, '_layer_centroid_overrides') and (override := self._layer_centroid_overrides.get(layer.id() if layer else None)) is not None: return override
        if not getattr(self, '_optimization_enabled', True) or not getattr(self, '_centroid_auto_enabled', True): return False
        try:
            from .core.services.auto_optimizer import LayerAnalyzer, LayerLocationType, AUTO_OPTIMIZER_AVAILABLE
            if not AUTO_OPTIMIZER_AVAILABLE or not (analysis := LayerAnalyzer().analyze_layer(layer)): return False
            threshold = getattr(self, '_optimization_thresholds', {}).get('centroid_distant', get_optimization_thresholds(ENV_VARS).get('centroid_optimization_threshold', 1000))
            return analysis.location_type in (LayerLocationType.REMOTE_SERVICE, LayerLocationType.REMOTE_DATABASE) and analysis.feature_count >= threshold
        except (ImportError, AttributeError, TypeError) as e:
            logger.debug(f"_should_use_centroid_for_layer: {e}")
            return False

    def get_optimization_state(self) -> dict:
        """Get current optimization state for storage/restore."""
        return {'enabled': getattr(self, '_optimization_enabled', True), 'centroid_auto': getattr(self, '_centroid_auto_enabled', True),
                'ask_before': getattr(self, '_optimization_ask_before', True), 'thresholds': getattr(self, '_optimization_thresholds', {}),
                'layer_overrides': getattr(self, '_layer_centroid_overrides', {})}

    def restore_optimization_state(self, state: dict):
        """Restore optimization state from saved settings."""
        self._optimization_enabled = state.get('enabled', True); self._centroid_auto_enabled = state.get('centroid_auto', True)
        self._optimization_ask_before = state.get('ask_before', True); self._optimization_thresholds = state.get('thresholds', {})
        self._layer_centroid_overrides = state.get('layer_overrides', {})

    def auto_select_optimal_backends(self):
        """Delegate to BackendController."""
        if self._controller_integration and self._controller_integration.backend_controller:
            try:
                count = self._controller_integration.backend_controller.auto_select_optimal_backends()
                (show_success if count > 0 else show_info)("FilterMate", self.tr("Optimized {0} layer(s)").format(count) if count > 0 else self.tr("All layers using auto-selection"))
                if self.current_layer:
                    _, _, layer_props = self._validate_and_prepare_layer(self.current_layer)
                    self._synchronize_layer_widgets(self.current_layer, layer_props)
            except Exception as e:
                logger.warning(f"auto_select_optimal_backends failed: {e}")
                show_warning("FilterMate", self.tr("Backend optimization unavailable"))

    def _setup_action_bar_layout(self):
        """v4.0 S16: → ActionBarManager."""
        if not hasattr(self, 'frame_actions'): return
        (self._action_bar_manager.setup() if self._action_bar_manager else self.frame_actions.show())

    def _get_action_bar_position(self):
        """v4.0 S16: → ActionBarManager."""
        return self._action_bar_manager.get_position() if self._action_bar_manager else 'top'

    def _get_action_bar_vertical_alignment(self):
        """v4.0 S16: → ActionBarManager."""
        return self._action_bar_manager._read_alignment_from_config() if self._action_bar_manager else 'top'

    def _apply_action_bar_position(self, position):
        """v4.0 S16: → ActionBarManager."""
        if self._action_bar_manager: self._action_bar_manager.set_position(position); self._action_bar_manager.apply_position()

    # ActionBar wrapper methods removed - use self._action_bar_manager directly
    # Removed: _adjust_header_for_side_position, _restore_header_from_wrapper, _clear_action_bar_layout,
    # _create_horizontal_action_layout, _create_vertical_action_layout, _apply_action_bar_size_constraints,
    # _reposition_action_bar_in_main_layout, _create_horizontal_wrapper_for_side_action_bar,
    # _restore_side_action_bar_layout, _restore_original_layout (~30 lines)

    def _setup_exploring_tab_widgets(self):
        """v4.0 Sprint 16: Delegate to ConfigurationManager."""
        if self._configuration_manager:
            self._configuration_manager.setup_exploring_tab_widgets()

    def _setup_dual_mode_exploring(self):
        """Phase 0: Create QStackedWidget for Vector/Raster dual mode in Exploring panel.

        Wraps existing vector groupboxes in page 0, creates raster placeholder in page 1.
        Adds DualModeToggle to the top of frame_exploring (above scrollArea).
        Wires auto-detection: selecting a raster layer in QGIS switches to raster mode.
        """
        try:
            from .ui.widgets.dual_mode_toggle import DualModeToggle, DualMode

            # -- 1. Create the stacked widget --
            self._stacked_exploring = QtWidgets.QStackedWidget()
            self._stacked_exploring.setObjectName("stacked_exploring")

            # -- 2. Page 0: Vector (move existing groupboxes) --
            page_vector = QtWidgets.QWidget()
            page_vector.setObjectName("page_exploring_vector")
            layout_vector = QtWidgets.QVBoxLayout(page_vector)
            layout_vector.setContentsMargins(0, 0, 0, 0)
            layout_vector.setSpacing(2)

            # Collect all items from the existing verticalLayout_exploring_tabs_content
            vector_widgets = []
            while self.verticalLayout_exploring_tabs_content.count():
                item = self.verticalLayout_exploring_tabs_content.takeAt(0)
                if item.widget():
                    vector_widgets.append(item.widget())
                elif item.spacerItem():
                    vector_widgets.append(item.spacerItem())

            for w in vector_widgets:
                if isinstance(w, QtWidgets.QWidget):
                    layout_vector.addWidget(w)
                else:
                    # Spacer items
                    layout_vector.addSpacerItem(w)

            layout_vector.addStretch()
            self._stacked_exploring.addWidget(page_vector)

            # -- 3. Page 1: Raster (placeholder) --
            page_raster = QtWidgets.QWidget()
            page_raster.setObjectName("page_exploring_raster")
            layout_raster = QtWidgets.QVBoxLayout(page_raster)
            layout_raster.setContentsMargins(4, 4, 4, 4)
            layout_raster.setSpacing(4)

            lbl_placeholder = QtWidgets.QLabel(self.tr("Raster Exploring"))
            lbl_placeholder.setAlignment(Qt.AlignCenter)
            lbl_placeholder.setStyleSheet(
                "color: palette(mid); font-style: italic; padding: 20px;"
            )
            layout_raster.addWidget(lbl_placeholder)
            layout_raster.addStretch()
            self._stacked_exploring.addWidget(page_raster)

            # -- 4. Insert stacked widget into the existing layout --
            self.verticalLayout_exploring_tabs_content.addWidget(self._stacked_exploring)

            # -- 5. Create toggle and insert at top of frame_exploring --
            self._dual_mode_toggle = DualModeToggle(self)
            self.verticalLayout_main_content.insertWidget(0, self._dual_mode_toggle)

            # -- 6. Wire toggle -> stacked widget --
            self._dual_mode_toggle.modeChanged.connect(self._stacked_exploring.setCurrentIndex)

            # -- 7. Wire QGIS layer tree auto-detection --
            try:
                from qgis.utils import iface as qgis_iface
                if qgis_iface and hasattr(qgis_iface, 'layerTreeView'):
                    tree_view = qgis_iface.layerTreeView()
                    if tree_view:
                        tree_view.currentLayerChanged.connect(self._on_dual_mode_layer_changed)
                        logger.debug("DualMode: connected layerTreeView.currentLayerChanged")
            except Exception as e:
                logger.debug(f"DualMode: could not connect layerTreeView signal: {e}")

            # Default to vector
            self._stacked_exploring.setCurrentIndex(DualMode.VECTOR)
            logger.info("DualMode: dual mode exploring setup complete (Phase 0)")

        except Exception as e:
            logger.error(f"_setup_dual_mode_exploring failed: {e}", exc_info=True)

    def _on_dual_mode_layer_changed(self, layer):
        """Auto-switch dual mode based on active layer type in QGIS layer tree."""
        if layer is None:
            return
        try:
            from qgis.core import QgsRasterLayer
            from .ui.widgets.dual_mode_toggle import DualMode
            if isinstance(layer, QgsRasterLayer):
                self._dual_mode_toggle.setMode(DualMode.RASTER)
                if self._raster_exploring_ctrl:
                    self._raster_exploring_ctrl.set_raster_layer(layer)
            elif isinstance(layer, QgsVectorLayer):
                self._dual_mode_toggle.setMode(DualMode.VECTOR)
            # Other layer types (mesh, point cloud): keep current mode
        except Exception as e:
            logger.debug(f"_on_dual_mode_layer_changed: {e}")

    def _schedule_expression_change(self, groupbox: str, expression: str):
        """v4.0 Sprint 16: Schedule debounced expression change."""
        self._pending_expression_change = (groupbox, expression); self._set_expression_loading_state(True, groupbox); self._expression_debounce_timer.start()

    def _setup_expression_widget_direct_connections(self):
        """
        FIX 2026-01-15: Setup direct signal connections for all QgsFieldExpressionWidget widgets.

        Migrated from before_migration. This method establishes direct connections between
        fieldChanged signals and the display expression update for associated FeaturePicker widgets.

        We bypass the manageSignal/isSignalConnected system because isSignalConnected()
        is unreliable for tracking specific handler connections.

        PERFORMANCE: Uses debounced handlers to prevent excessive recomputation
        when the user types quickly or makes rapid changes to complex expressions.
        """
        logger.debug("🔧 _setup_expression_widget_direct_connections CALLED")

        # Check if widgets exist
        if not hasattr(self, 'mFieldExpressionWidget_exploring_single_selection'):
            logger.error("❌ mFieldExpressionWidget_exploring_single_selection does NOT exist!")
            return

        # SINGLE SELECTION: mFieldExpressionWidget -> mFeaturePickerWidget
        def on_single_field_changed(field_name):
            logger.debug(f"🔄 Single field changed: {field_name}")
            self._refresh_feature_pickers_for_field_change("single_selection", field_name)
            self._schedule_expression_change("single_selection", field_name)

        try:
            self.mFieldExpressionWidget_exploring_single_selection.fieldChanged.disconnect()
        except (TypeError, RuntimeError):
            pass
        self.mFieldExpressionWidget_exploring_single_selection.fieldChanged.connect(on_single_field_changed)
        logger.debug("✓ Connected mFieldExpressionWidget_exploring_single_selection.fieldChanged DIRECTLY")

        # MULTIPLE SELECTION: mFieldExpressionWidget -> checkableComboBoxFeaturesListPickerWidget
        def on_multiple_field_changed(field_name):
            logger.info(f"🔄 Multiple field changed: {field_name}")
            self._refresh_feature_pickers_for_field_change("multiple_selection", field_name)
            self._schedule_expression_change("multiple_selection", field_name)

        try:
            self.mFieldExpressionWidget_exploring_multiple_selection.fieldChanged.disconnect()
        except (TypeError, RuntimeError):
            pass
        self.mFieldExpressionWidget_exploring_multiple_selection.fieldChanged.connect(on_multiple_field_changed)
        logger.debug("✓ Connected mFieldExpressionWidget_exploring_multiple_selection.fieldChanged DIRECTLY")

        # CUSTOM SELECTION: mFieldExpressionWidget (no FeaturePicker to update, but may have other uses)
        def on_custom_field_changed(field_name):
            logger.info(f"🔄 Custom field changed: {field_name}")
            self._refresh_feature_pickers_for_field_change("custom_selection", field_name)
            self._schedule_expression_change("custom_selection", field_name)

        try:
            self.mFieldExpressionWidget_exploring_custom_selection.fieldChanged.disconnect()
        except (TypeError, RuntimeError):
            pass
        self.mFieldExpressionWidget_exploring_custom_selection.fieldChanged.connect(on_custom_field_changed)
        logger.debug("✓ Connected mFieldExpressionWidget_exploring_custom_selection.fieldChanged DIRECTLY")

    def _on_expression_field_changed(self, groupbox: str, field_or_expression: str):
        """
        v4.5: Handler for fieldChanged signal from QgsFieldExpressionWidget.

        This method provides a fallback when ExploringController is not available.
        It schedules a debounced expression change to avoid rapid-fire updates.

        FIX 2026-01-15: Refresh feature pickers when field changes.

        Args:
            groupbox: 'single_selection', 'multiple_selection', or 'custom_selection'
            field_or_expression: The field name or expression from the widget

        Signal Flow:
            Widget.fieldChanged → _on_expression_field_changed() →
            _schedule_expression_change() → debounce timer →
            _execute_debounced_expression_change() → layer_property_changed()
        """
        # FIX 2026-01-16: Controller delegation removed (method does not exist)
        # Directly use debounced expression change system
        logger.debug(f"_on_expression_field_changed: {groupbox} -> '{field_or_expression}'")

        # FIX 2026-01-15: Update feature pickers immediately when field changes
        self._refresh_feature_pickers_for_field_change(groupbox, field_or_expression)

        self._schedule_expression_change(groupbox, field_or_expression)

    def _execute_debounced_expression_change(self):
        """v4.0 Sprint 16: Execute pending expression change after debounce."""
        if self._pending_expression_change is None:
            self._set_expression_loading_state(False); return
        groupbox, expression = self._pending_expression_change; self._pending_expression_change = None
        try:
            self.layer_property_changed(f"{groupbox}_expression", expression, {"ON_CHANGE": lambda x: self._execute_expression_params_change(groupbox)})
        except Exception as e:
            logger.debug(f"Ignored in deferred expression change for {groupbox}: {e}")
            self._set_expression_loading_state(False)

    def _refresh_feature_pickers_for_field_change(self, groupbox: str, field_or_expression: str):
        """
        FIX 2026-01-15 v4: Refresh feature pickers when field changes.

        When the user changes the field in a QgsFieldExpressionWidget, we need to:
        1. Update the display expression for the corresponding feature picker
        2. Force the picker to rebuild its features list with the new expression
        3. Update PROJECT_LAYERS to persist the expression change

        CRITICAL: For QgsFeaturePickerWidget, setDisplayExpression() alone doesn't work.
        We must call setLayer() again to force the widget to rebuild its feature list.

        For QgsCheckableComboBoxFeaturesListPickerWidget, we need to call setLayer()
        with layer_props to trigger a full rebuild with the new expression.

        FIX v4: Ensure expression is ALWAYS saved to PROJECT_LAYERS, even if key doesn't exist.
        Also properly update layer_props before calling setLayer().

        FIX 2026-01-16: Use _is_layer_valid() to safely check layer validity and prevent
        RuntimeError when C++ object has been deleted.

        Args:
            groupbox: 'single_selection', 'multiple_selection', or 'custom_selection'
            field_or_expression: The new field name or expression
        """
        if not self._is_layer_valid():
            return

        try:
            layer_id = self.current_layer.id()
            if layer_id not in self.PROJECT_LAYERS:
                return

            layer_props = self.PROJECT_LAYERS[layer_id]

            # FIX v4: ALWAYS update PROJECT_LAYERS with new expression (create if missing)
            expression_key = f"{groupbox}_expression"
            if "exploring" not in layer_props:
                layer_props["exploring"] = {}
            layer_props["exploring"][expression_key] = field_or_expression
            logger.info(f"  → Updated PROJECT_LAYERS[exploring][{expression_key}] = {field_or_expression}")

            # Update single selection picker (QgsFeaturePickerWidget)
            if groupbox == "single_selection":
                picker = self.widgets.get("EXPLORING", {}).get("SINGLE_SELECTION_FEATURES", {}).get("WIDGET")
                if picker:
                    logger.info(f"🔄 Refreshing SINGLE picker with field: {field_or_expression}")

                    # Save current feature ID to restore after refresh
                    current_feature = picker.feature()
                    current_fid = current_feature.id() if (current_feature and current_feature.isValid()) else None

                    # FIX 2026-01-15 v7: For QgsFeaturePickerWidget, we need to:
                    # 1. Disconnect signal to prevent spurious emissions during refresh
                    # 2. Clear filter to reset widget state
                    # 3. Set layer to reload features
                    # 4. Set display expression AFTER setLayer
                    # 5. Force widget to rebuild its internal model
                    # 6. Reconnect signal
                    try:
                        picker.featureChanged.disconnect(self.exploring_features_changed)
                    except (TypeError, RuntimeError):
                        pass

                    # Clear any existing filter and reset
                    if hasattr(picker, 'setFilterExpression'):
                        picker.setFilterExpression(None)

                    # Set layer to reload the feature model
                    picker.setLayer(self.current_layer)

                    # Set display expression - this controls how features are displayed in dropdown
                    picker.setDisplayExpression(field_or_expression)

                    # Enable geometry fetching and browser buttons
                    picker.setFetchGeometry(True)
                    picker.setShowBrowserButtons(True)
                    picker.setAllowNull(True)

                    # Force model to reload by clearing filter expression
                    if hasattr(picker, 'setFilterExpression'):
                        picker.setFilterExpression("")

                    # Reconnect signal
                    picker.featureChanged.connect(self.exploring_features_changed)

                    # Force visual update
                    picker.update()
                    picker.repaint()

                    # Try to restore the same feature
                    if current_fid is not None:
                        try:
                            picker.setFeature(current_fid)
                            logger.debug(f"  → Restored feature {current_fid}")
                        except (RuntimeError, AttributeError, ValueError):
                            pass  # Feature may not exist anymore

                    logger.info("  ✓ Single picker refreshed with new expression")

            # Update multiple selection picker (QgsCheckableComboBoxFeaturesListPickerWidget)
            elif groupbox == "multiple_selection":
                picker = self.widgets.get("EXPLORING", {}).get("MULTIPLE_SELECTION_FEATURES", {}).get("WIDGET")
                if picker:
                    logger.info(f"🔄 Refreshing MULTIPLE picker with field: {field_or_expression}")

                    # FIX v3: Save currently checked items BEFORE refresh
                    saved_checked_fids = None
                    if hasattr(picker, 'list_widgets') and layer_id in picker.list_widgets:
                        try:
                            list_widget = picker.list_widgets[layer_id]
                            saved_checked_fids = list_widget.getSelectedFeaturesList()
                            logger.debug(f"  → Saved {len(saved_checked_fids) if saved_checked_fids else 0} checked items")
                        except Exception as e:
                            logger.debug(f"  → Could not save checked items: {e}")

                    # FIX 2026-01-18 v16: Don't call setDisplayExpression before setLayer
                    # setLayer() will handle the display expression update internally.
                    # Calling setDisplayExpression first causes double-clear and list disappears.
                    # Update layer_props with new expression BEFORE calling setLayer
                    if "exploring" not in layer_props:
                        layer_props["exploring"] = {}
                    layer_props["exploring"]["multiple_selection_expression"] = field_or_expression

                    # FIX v3: For multiple picker, setLayer() with layer_props triggers full rebuild
                    # This is more reliable than just setDisplayExpression()
                    try:
                        # CRITICAL: Don't skip task if list is currently empty
                        # The widget's internal logic will force populate if needed
                        current_count = 0
                        if hasattr(picker, 'list_widgets') and layer_id in picker.list_widgets:
                            current_count = picker.list_widgets[layer_id].count()

                        # Only skip task if list already has items (performance optimization)
                        skip = (current_count > 0)
                        picker.setLayer(self.current_layer, layer_props, skip_task=skip, preserve_checked=True)
                        logger.debug(f"  → Called setLayer (skip_task={skip}, current_count={current_count})")
                    except Exception as e:
                        logger.warning(f"  → setLayer failed: {e}")
                        # Fallback to direct expression update
                        if hasattr(picker, 'setDisplayExpression'):
                            picker.setDisplayExpression(field_or_expression, preserve_checked=True)

                    # FIX v3: Try to restore checked items AFTER refresh
                    if saved_checked_fids and hasattr(picker, 'list_widgets') and layer_id in picker.list_widgets:
                        try:
                            list_widget = picker.list_widgets[layer_id]
                            list_widget.setSelectedFeaturesList(saved_checked_fids)
                            logger.debug(f"  → Restored {len(saved_checked_fids)} checked items")
                        except Exception as e:
                            logger.debug(f"  → Could not restore checked items: {e}")

                    # Force visual update
                    if hasattr(picker, 'list_widgets') and layer_id in picker.list_widgets:
                        picker.list_widgets[layer_id].viewport().update()
                    picker.update()
                    picker.repaint()

                    logger.info("  ✓ Multiple picker refreshed")

            # FIX 2026-01-18: Trigger is_linking synchronization when user changes field
            # This ensures that when IS_LINKING is checked, the other picker gets the same field
            is_linking = layer_props.get("exploring", {}).get("is_linking", False)
            if is_linking and groupbox in ("single_selection", "multiple_selection"):
                logger.info(f"🔗 IS_LINKING is active, triggering bidirectional sync from {groupbox}")
                # Call exploring_link_widgets with change_source to trigger the sync
                self.exploring_link_widgets(change_source=groupbox)

        except Exception as e:
            logger.warning(f"_refresh_feature_pickers_for_field_change error: {e}")

    def _execute_expression_params_change(self, groupbox: str):
        """v4.0 Sprint 16: Execute expression params change with caching."""
        try:
            if groupbox in ("single_selection", "multiple_selection"): self._last_expression_change_source = groupbox
            if groupbox == "single_selection":
                try: self.mFeaturePickerWidget_exploring_single_selection.update()
                except Exception:  # Widget may not be ready - expected during initialization
                    pass
            elif groupbox == "multiple_selection":
                try:
                    w = self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection
                    if w and hasattr(w, 'list_widgets') and self.current_layer and self.current_layer.id() in w.list_widgets:
                        w.list_widgets[self.current_layer.id()].viewport().update()
                except Exception:  # Widget may not be ready - expected during initialization
                    pass
            self.exploring_source_params_changed(groupbox_override=groupbox, change_source=groupbox)
        finally:
            self._set_expression_loading_state(False, groupbox)

    def _set_expression_loading_state(self, loading: bool, groupbox: str = None):
        """v4.0 Sprint 16: Update loading state for expression widgets."""
        self._expression_loading = loading
        try:
            cursor, widgets = (Qt.WaitCursor if loading else Qt.PointingHandCursor), []
            if groupbox in ("single_selection", None): widgets.extend([self.mFieldExpressionWidget_exploring_single_selection, self.mFeaturePickerWidget_exploring_single_selection])
            if groupbox in ("multiple_selection", None): widgets.extend([self.mFieldExpressionWidget_exploring_multiple_selection, self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection])
            if groupbox in ("custom_selection", None): widgets.append(self.mFieldExpressionWidget_exploring_custom_selection)
            for w in widgets:
                if w and hasattr(w, 'setCursor'): w.setCursor(cursor)
        except Exception:  # Cursor change is cosmetic - non-critical
            pass

    def _get_cached_expression_result(self, layer_id: str, expression: str):
        """v4.0 Sprint 16: Get cached expression result (includes subsetString for multi-step filtering)."""
        import time
        layer = QgsProject.instance().mapLayer(layer_id)
        cache_key = (layer_id, expression, layer.subsetString() if layer else "")
        if cache_key not in self._expression_cache: return None
        features, timestamp = self._expression_cache[cache_key]
        if time.time() - timestamp > self._expression_cache_max_age:
            del self._expression_cache[cache_key]; return None
        return features

    def _set_cached_expression_result(self, layer_id: str, expression: str, features):
        """v4.0 Sprint 16: Cache expression result with LRU eviction."""
        import time
        if len(self._expression_cache) >= self._expression_cache_max_size:
            oldest_key = min(self._expression_cache.keys(), key=lambda k: self._expression_cache[k][1])
            del self._expression_cache[oldest_key]
        layer = QgsProject.instance().mapLayer(layer_id)
        cache_key = (layer_id, expression, layer.subsetString() if layer else "")
        self._expression_cache[cache_key] = (features, time.time())

    def invalidate_expression_cache(self, layer_id: str = None):
        """v4.0 Sprint 16: Invalidate expression cache (layer_id=None clears all)."""
        if layer_id is None:
            self._expression_cache.clear(); logger.debug("Cleared entire expression cache")
        else:
            keys = [k for k in self._expression_cache.keys() if k[0] == layer_id]
            for k in keys: del self._expression_cache[k]
            if keys: logger.debug(f"Cleared {len(keys)} cache entries for layer {layer_id}")

    def _setup_filtering_tab_widgets(self):
        """v4.0 Sprint 16: Delegate to ConfigurationManager."""
        if self._configuration_manager:
            self._configuration_manager.setup_filtering_tab_widgets()

    def _setup_exporting_tab_widgets(self):
        """v4.0 Sprint 16: Delegate to ConfigurationManager."""
        if self._configuration_manager:
            self._configuration_manager.setup_exporting_tab_widgets()

    def _index_to_combine_operator(self, index):
        """v4.0 Sprint 5: Delegates to FilteringController."""
        if self._controller_integration is not None:
            return self._controller_integration.delegate_filtering_index_to_combine_operator(index)
        return {0: 'AND', 1: 'AND NOT', 2: 'OR'}.get(index, 'AND')

    def _combine_operator_to_index(self, operator):
        """v4.0 Sprint 5: Delegates to FilteringController."""
        if self._controller_integration is not None:
            return self._controller_integration.delegate_filtering_combine_operator_to_index(operator)
        if not operator:
            return 0
        op = operator.upper().strip()
        return {'AND': 0, 'AND NOT': 1, 'OR': 2, 'ET': 0, 'ET NON': 1, 'OU': 2}.get(op, 0)

    def dockwidget_widgets_configuration(self):
        """Configure widgets via ConfigurationManager and setup controllers."""
        if self._configuration_manager is None: self._configuration_manager = ConfigurationManager(self)
        self.layer_properties_tuples_dict = self._configuration_manager.get_layer_properties_tuples_dict()
        self.export_properties_tuples_dict = self._configuration_manager.get_export_properties_tuples_dict()
        self.widgets = self._configuration_manager.configure_widgets(); self.widgets_initialized = True
        logger.info(f"✅ Widgets configured: FILTERING keys = {list(self.widgets.get('FILTERING', {}).keys())}")

        # Enable all filtering checkable buttons that were disabled in UI
        # pushButton_checkable_filtering_buffer_value is disabled by default in .ui file
        self._enable_filtering_checkable_buttons()

        # FIX 2026-01-14: Connect initial widget signals after configuration
        # CRITICAL: comboBox_filtering_current_layer.layerChanged must be connected
        # to update exploring widgets when the current layer changes
        self._connect_initial_widget_signals()

        # v4.0 Sprint 16: Setup controller integration (Strangler Fig pattern)
        if self._controller_integration:
            try:
                logger.info("Setting up controller integration...")
                setup_success = self._controller_integration.setup()

                if setup_success:
                    # Validate all controllers are properly initialized
                    validation = self._controller_integration.validate_controllers()

                    if validation['all_valid']:
                        logger.info(f"✓ Controller integration validated: {validation['registry_count']} controllers operational")
                        logger.debug(f"  Controllers: {', '.join(validation['controllers'].keys())}")
                        logger.debug(f"  Signal connections: {validation['connections_count']}")
                    else:
                        logger.warning("⚠️ Controller validation detected issues:")
                        logger.warning(self._controller_integration.get_controller_status())

                    # Sync initial state from dockwidget to controllers
                    self._controller_integration.sync_from_dockwidget()
                    logger.debug("  Initial state synchronized to controllers")

                    # Log delegation readiness
                    logger.debug("✓ Strangler Fig pattern active: filter operations will try hexagonal path first")
                else:
                    logger.warning("⚠️ Controller integration setup returned False - using legacy code paths")

            except Exception as e:
                logger.error(f"❌ Controller integration setup failed: {e}", exc_info=True)
                logger.warning("  Falling back to legacy code paths")
        else:
            logger.warning("⚠️ _controller_integration is None - using legacy code paths only")

        # FIX 2026-02-10 (C1): Centralized selectionChanged connection
        if self.current_layer and not self.current_layer_selection_connection:
            self._connect_selection_signal()
        self.widgetsInitialized.emit(); self._setup_keyboard_shortcuts()
        if self._pending_layers_update:
            self._pending_layers_update = False; pl, pr, weak_self = self.PROJECT_LAYERS, self.PROJECT, weakref.ref(self)
            QTimer.singleShot(100, lambda: weak_self() and weak_self().get_project_layers_from_app(pl, pr))

    def _connect_initial_widget_signals(self):
        """
        FIX 2026-01-14: Connect critical widget signals after configuration.

        CRITICAL: These signals must be connected at startup for proper widget synchronization:
        - FILTERING.CURRENT_LAYER.layerChanged: Updates exploring widgets when current layer changes
        - ACTION buttons: FILTER, UNFILTER, UNDO_FILTER, REDO_FILTER, EXPORT

        NOTE: QGIS.LAYER_TREE_VIEW.currentLayerChanged is NOT connected here.
        It is managed by filtering_auto_current_layer_changed() based on AUTO_CURRENT_LAYER state.

        Signal goes through manageSignal which connects to current_layer_changed(layer, manual_change=True).
        This triggers the full update chain:
        - _synchronize_layer_widgets → _sync_layers_to_filter_combobox (layers_to_filter list)
        - _reload_exploration_widgets (exploring widgets)
        - exploring_groupbox_init (groupbox state)
        """
        if not self.widgets_initialized:
            return

        try:
            # FIX 2026-01-14: Force connection by clearing cache first
            # The signal cache can become stale and block reconnection
            cache_key = "FILTERING.CURRENT_LAYER.layerChanged"
            if cache_key in self._signal_connection_states:
                logger.debug(f"Clearing stale cache for {cache_key} (was: {self._signal_connection_states[cache_key]})")
                del self._signal_connection_states[cache_key]

            # Connect comboBox_filtering_current_layer.layerChanged signal
            # This is CRITICAL for exploring widgets to update when current layer changes
            self.manageSignal(["FILTERING", "CURRENT_LAYER"], 'connect', 'layerChanged')
            logger.debug("✓ Connected FILTERING.CURRENT_LAYER.layerChanged signal via manageSignal")
        except Exception as e:
            logger.warning(f"Could not connect CURRENT_LAYER signal: {e}")

        # FIX 2026-01-16: CRITICAL - Connect ACTION button signals at startup
        # These must be connected ALWAYS, not just when layers are loaded
        try:
            logger.debug("🔌 Connecting ACTION button signals at startup...")
            self.force_reconnect_action_signals()
            logger.debug("✓ ACTION button signals connected at startup")
        except Exception as e:
            logger.warning(f"Could not connect ACTION signals at startup: {e}")

        # FIX 2026-01-22: CRITICAL - Connect EXPORTING button signals at startup
        # pushButton_checkable_exporting_output_folder and pushButton_checkable_exporting_zip
        # must have their clicked signals connected to open file dialogs
        try:
            logger.debug("🔌 Connecting EXPORTING button signals at startup...")
            self.force_reconnect_exporting_signals()
            logger.debug("✓ EXPORTING button signals connected at startup")
        except Exception as e:
            logger.warning(f"Could not connect EXPORTING signals at startup: {e}")

        # FIX 2026-01-14: Connect LAYER_TREE_VIEW only if AUTO_CURRENT_LAYER is enabled
        # This is also handled by filtering_auto_current_layer_changed() but we need to
        # restore the state at startup based on saved project settings
        try:
            auto_current_layer_enabled = self.project_props.get("OPTIONS", {}).get("LAYERS", {}).get("LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG", False)
            if auto_current_layer_enabled:
                # Clear cache for LAYER_TREE_VIEW as well
                cache_key = "QGIS.LAYER_TREE_VIEW.currentLayerChanged"
                if cache_key in self._signal_connection_states:
                    del self._signal_connection_states[cache_key]

                self.manageSignal(["QGIS", "LAYER_TREE_VIEW"], 'connect', 'currentLayerChanged')
                logger.debug("✓ Connected QGIS.LAYER_TREE_VIEW.currentLayerChanged signal (AUTO_CURRENT_LAYER enabled)")
            else:
                logger.debug("QGIS.LAYER_TREE_VIEW signal not connected (AUTO_CURRENT_LAYER disabled)")
        except Exception as e:
            logger.warning(f"Could not check/connect LAYER_TREE_VIEW signal: {e}")

    def _on_combo_layer_changed(self, layer):
        """
        FIX 2026-01-14: Direct handler for comboBox layer change.
        Ensures exploring widgets are ALWAYS updated when combo changes.
        """
        if not layer:
            return
        logger.info(f"=== _on_combo_layer_changed === layer: {layer.name()}")

        # Force update exploring widgets even if current_layer_changed validation fails
        if self.widgets_initialized and layer.id() in self.PROJECT_LAYERS:
            layer_props = self.PROJECT_LAYERS[layer.id()]
            self._force_update_exploring_widgets(layer, layer_props)

    def _force_update_exploring_widgets(self, layer, layer_props):
        """
        FIX 2026-01-14: Force update all exploring widgets with new layer.
        Called directly when combo changes to ensure widgets are updated.

        FIX 2026-01-15 v7: Added signal disconnect/reconnect pattern to prevent
        spurious signal emissions during widget updates.
        """
        if not self.widgets_initialized or not layer:
            return

        logger.info(f"=== _force_update_exploring_widgets === layer: {layer.name()}")

        try:
            # FIX 2026-01-15 v7: Disconnect signals BEFORE updating widgets
            # Pattern from before_migration _reload_exploration_widgets
            self.manageSignal(["EXPLORING", "SINGLE_SELECTION_FEATURES"], 'disconnect')
            self.manageSignal(["EXPLORING", "MULTIPLE_SELECTION_FEATURES"], 'disconnect')
            self.manageSignal(["EXPLORING", "SINGLE_SELECTION_EXPRESSION"], 'disconnect')
            self.manageSignal(["EXPLORING", "MULTIPLE_SELECTION_EXPRESSION"], 'disconnect')
            self.manageSignal(["EXPLORING", "CUSTOM_SELECTION_EXPRESSION"], 'disconnect')

            # Get expressions from layer_props
            exploring = layer_props.get("exploring", {})
            single_expr = exploring.get("single_selection_expression", "")
            multiple_expr = exploring.get("multiple_selection_expression", "")
            custom_expr = exploring.get("custom_selection_expression", "")

            # v4.0 SMART FIELD SELECTION: Upgrade PK-only expressions to better fields
            # Get primary key to detect default (unset) expressions
            primary_key = layer_props.get("infos", {}).get("primary_key_name", "")
            logger.debug(f"Expressions: single={single_expr}, multiple={multiple_expr}, pk={primary_key}")

            # Check if expressions are just the primary key (default) - upgrade if better field exists
            should_upgrade_single = (single_expr == primary_key or not single_expr)
            should_upgrade_multiple = (multiple_expr == primary_key or not multiple_expr)
            should_upgrade_custom = (custom_expr == primary_key or not custom_expr)

            if should_upgrade_single or should_upgrade_multiple or should_upgrade_custom:
                from .infrastructure.utils import get_best_display_field
                best_field = get_best_display_field(layer)

                # Fallback if no descriptive field found
                if not best_field or best_field == primary_key:
                    fields = layer.fields()
                    for field in fields:
                        if field.name() != primary_key:
                            best_field = field.name()
                            break
                    if not best_field:
                        best_field = fields[0].name() if fields.count() > 0 else (primary_key or "$id")

                # Only upgrade if different from PK
                if best_field and best_field != primary_key:
                    if should_upgrade_single:
                        single_expr = best_field
                        exploring["single_selection_expression"] = best_field
                        logger.info(f"✨ Upgraded single_selection from PK to '{best_field}'")
                    if should_upgrade_multiple:
                        multiple_expr = best_field
                        exploring["multiple_selection_expression"] = best_field
                        logger.info(f"✨ Upgraded multiple_selection from PK to '{best_field}'")
                    if should_upgrade_custom:
                        custom_expr = best_field
                        exploring["custom_selection_expression"] = best_field
                        logger.info(f"✨ Upgraded custom_selection from PK to '{best_field}'")

            # Update single selection widget (QgsFeaturePickerWidget)
            if "SINGLE_SELECTION_FEATURES" in self.widgets.get("EXPLORING", {}):
                widget = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
                if widget:
                    logger.debug(f"  Updating SINGLE_SELECTION_FEATURES with layer {layer.name()}")  # nosec B608 - false positive: logger statement, no SQL execution
                    widget.setLayer(None)  # Force refresh
                    widget.setLayer(layer)
                    # FIX 2026-01-19: Connect willBeDeleted to prevent crash on layer deletion
                    self._connect_feature_picker_layer_deletion(layer)
                    if single_expr:
                        widget.setDisplayExpression(single_expr)
                    widget.setFetchGeometry(True)
                    widget.setShowBrowserButtons(True)
                    widget.setAllowNull(True)

            # Update multiple selection widget (CheckableFeatureComboBox)
            if "MULTIPLE_SELECTION_FEATURES" in self.widgets.get("EXPLORING", {}):
                widget = self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"]
                if widget and hasattr(widget, 'setLayer'):
                    logger.debug(f"  Updating MULTIPLE_SELECTION_FEATURES with layer {layer.name()}")  # nosec B608 - false positive: logger statement, no SQL execution
                    # FIX 2026-01-18 v8: Use preserve_checked=True to not lose selected items during refresh
                    widget.setLayer(layer, layer_props, skip_task=True, preserve_checked=True)
                    # FIX 2026-01-18: Always call setDisplayExpression to populate the list
                    # Even with empty expression, setDisplayExpression handles fallback to identifier field
                    # FIX 2026-01-18 v8: Use preserve_checked=True to not lose selected items
                    if hasattr(widget, 'setDisplayExpression'):
                        widget.setDisplayExpression(multiple_expr if multiple_expr else "", preserve_checked=True)

            # Update expression widgets (QgsFieldExpressionWidget)
            # FIX 2026-01-16: Use setField() for simple field names, setExpression() for complex expressions
            # Same pattern as _reload_exploration_widgets in exploring_controller.py
            from qgis.core import QgsExpression
            expr_mappings = [
                ("SINGLE_SELECTION_EXPRESSION", single_expr),
                ("MULTIPLE_SELECTION_EXPRESSION", multiple_expr),
                ("CUSTOM_SELECTION_EXPRESSION", custom_expr)
            ]
            for expr_key, expr_value in expr_mappings:
                if expr_key in self.widgets.get("EXPLORING", {}):
                    widget = self.widgets["EXPLORING"][expr_key]["WIDGET"]
                    if widget and hasattr(widget, 'setLayer'):
                        logger.debug(f"  Updating {expr_key} with layer {layer.name()}, expression='{expr_value}'")
                        widget.setLayer(layer)
                        if expr_value:
                            # Use setField for simple field names, setExpression for complex expressions
                            if QgsExpression(expr_value).isField():
                                widget.setField(expr_value)
                                logger.debug(f"    ✓ Set {expr_key} field to '{expr_value}'")
                            else:
                                widget.setExpression(expr_value)
                                logger.debug(f"    ✓ Set {expr_key} expression to '{expr_value}'")

            logger.info(f"✓ _force_update_exploring_widgets completed for layer {layer.name()}")

        except Exception as e:
            logger.warning(f"❌ _force_update_exploring_widgets failed: {e}")
            import traceback
            logger.debug(f"Traceback:\n{traceback.format_exc()}")

    def data_changed_configuration_model(self, input_data=None):
        """
        WRAPPER: Delegates to ConfigController.

        Track configuration changes without applying immediately.
        v4.0 Sprint 11: Migrated to ConfigController.
        """
        if self._controller_integration:
            self._controller_integration.delegate_config_data_changed(input_data)
            # Enable OK/Cancel buttons when changes are pending
            if hasattr(self, 'buttonBox') and self._controller_integration.delegate_config_has_pending_changes():
                self.buttonBox.setEnabled(True)

    # v4.0 Sprint 11: Config change helper methods removed - logic migrated to ConfigController
    # Removed: _apply_theme_change, _apply_ui_profile_change, _apply_action_bar_position_change,
    # _apply_export_style_change, _apply_export_format_change (~110 lines)

    def apply_pending_config_changes(self):
        """
        WRAPPER: Delegates to ConfigController.

        Apply all pending configuration changes when OK button is clicked.
        v4.0 Sprint 11: Migrated to ConfigController.
        """
        if self._controller_integration:
            if self._controller_integration.delegate_config_apply_pending_changes():
                # Disable OK/Cancel buttons after changes applied
                if hasattr(self, 'buttonBox'):
                    self.buttonBox.setEnabled(False)
                return

        # Clear local state as fallback
        self.pending_config_changes = []
        self.config_changes_pending = False

    def cancel_pending_config_changes(self):
        """Cancel pending configuration changes.

        v4.0.7 FIX: Refactored to disconnect signal before recreating model
        to prevent multiple signal connections.
        """
        if not self.config_changes_pending or not self.pending_config_changes: return
        try:
            # FIX #3: Disconnect signal before replacing model to prevent multiple connections
            self._disconnect_config_model_signal()

            with open(ENV_VARS.get('CONFIG_JSON_PATH', self.plugin_dir + '/config/config.json'), 'r') as f:
                self.CONFIG_DATA = json.load(f)
            self.config_model = JsonModel(data=self.CONFIG_DATA, editable_keys=False, editable_values=True, plugin_dir=self.plugin_dir)
            if hasattr(self, 'config_view') and self.config_view:
                self.config_view.setModel(self.config_model)
                self.config_view.model = self.config_model

            # Reconnect signal to new model
            self._connect_config_model_signal()

            self.pending_config_changes, self.config_changes_pending = [], False
            if hasattr(self, 'buttonBox'): self.buttonBox.setEnabled(False)
        except Exception as e: show_error("FilterMate", self.tr("Error cancelling changes: {0}").format(str(e)))

    def on_config_buttonbox_accepted(self):
        """v4.0 S18: → ConfigController."""
        logger.info("Configuration OK button clicked")
        if self._controller_integration and self._controller_integration.delegate_config_apply_pending_changes(): return
        self.apply_pending_config_changes()

    def on_config_buttonbox_rejected(self):
        """v4.0 S18: → ConfigController."""
        logger.info("Configuration Cancel button clicked")
        if self._controller_integration and self._controller_integration.delegate_config_cancel_pending_changes(): return
        self.cancel_pending_config_changes()

    def reload_configuration_model(self):
        """v4.0 S18: Reload config model and save."""
        if not self.widgets_initialized: return
        try:
            self.config_model = JsonModel(data=self.CONFIG_DATA, editable_keys=False, editable_values=True, plugin_dir=self.plugin_dir)
            if hasattr(self, 'config_view') and self.config_view: self.config_view.setModel(self.config_model); self.config_view.model = self.config_model
            with open(ENV_VARS.get('CONFIG_JSON_PATH', self.plugin_dir + '/config/config.json'), 'w') as f: f.write(json.dumps(self.CONFIG_DATA, indent=4))
        except Exception as e: logger.error(f"Error reloading configuration model: {e}")

    def save_configuration_model(self):
        """v4.0 S18: Save config to file."""
        if not self.widgets_initialized: return
        self.CONFIG_DATA = self.config_model.serialize()
        with open(ENV_VARS.get('CONFIG_JSON_PATH', self.plugin_dir + '/config/config.json'), 'w') as f: f.write(json.dumps(self.CONFIG_DATA, indent=4))

    def _disconnect_config_model_signal(self):
        """Disconnect itemChanged signal from config_model to prevent multiple connections.

        v4.0.7 FIX: Prevents signal accumulation when model is recreated.
        """
        try:
            if hasattr(self, 'config_model') and self.config_model is not None:
                try:
                    self.config_model.itemChanged.disconnect(self.data_changed_configuration_model)
                    logger.debug("Config model itemChanged signal disconnected")
                except (TypeError, RuntimeError):
                    # Signal was not connected or already disconnected
                    pass
        except Exception as e:
            logger.debug(f"Could not disconnect config_model signal: {e}")

    def _connect_config_model_signal(self):
        """Connect itemChanged signal to config_model.

        v4.0.7 FIX: Centralized connection method for consistency.
        """
        try:
            if hasattr(self, 'config_model') and self.config_model is not None:
                self.config_model.itemChanged.connect(self.data_changed_configuration_model)
                logger.debug("Config model itemChanged signal connected")
        except Exception as e:
            logger.error(f"Could not connect config_model signal: {e}")

    def manage_configuration_model(self):
        """Setup config model, view, and signals.

        v4.0.7 FIX: Uses centralized signal connection methods.
        v4.0.7 NEW: Uses SearchableJsonView with integrated search bar.
        """
        try:
            # Disconnect any existing signal first
            self._disconnect_config_model_signal()

            self.config_model = JsonModel(data=self.CONFIG_DATA, editable_keys=False, editable_values=True, plugin_dir=self.plugin_dir)

            # Use SearchableJsonView with integrated search bar
            try:
                from ui.widgets.json_view import SearchableJsonView
                self.config_view_container = SearchableJsonView(self.config_model, self.plugin_dir)
                self.config_view = self.config_view_container.json_view  # For backward compatibility
                self.CONFIGURATION.layout().insertWidget(0, self.config_view_container)
                self.config_view_container.setAnimated(True)
                self.config_view_container.setEnabled(True)
                self.config_view_container.show()
                logger.debug("Using SearchableJsonView with search bar")
            except ImportError:
                # Fallback to standard JsonView
                self.config_view = JsonView(self.config_model, self.plugin_dir)
                self.config_view_container = None
                self.CONFIGURATION.layout().insertWidget(0, self.config_view)
                self.config_view.setAnimated(True)
                self.config_view.setEnabled(True)
                self.config_view.show()
                logger.debug("Using standard JsonView (SearchableJsonView not available)")

            # Connect signal using centralized method
            self._connect_config_model_signal()
            self._setup_reload_button()

            if hasattr(self, 'buttonBox'):
                self.buttonBox.setEnabled(False)
                self.buttonBox.accepted.connect(self.on_config_buttonbox_accepted)
                self.buttonBox.rejected.connect(self.on_config_buttonbox_rejected)
        except Exception as e: logger.error(f"Error creating configuration model: {e}")

    def _setup_reload_button(self):
        """Setup Reload Plugin button in config panel."""
        try:
            self.pushButton_reload_plugin = QtWidgets.QPushButton("🔄 Reload Plugin"); self.pushButton_reload_plugin.setObjectName("pushButton_reload_plugin")
            self.pushButton_reload_plugin.setToolTip(QCoreApplication.translate("FilterMate", "Reload the plugin to apply layout changes (action bar position)"))
            self.pushButton_reload_plugin.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
            # Height managed by QSS
            self.pushButton_reload_plugin.clicked.connect(self._on_reload_button_clicked)
            if self.CONFIGURATION.layout(): self.CONFIGURATION.layout().insertWidget(self.CONFIGURATION.layout().count() - 1, self.pushButton_reload_plugin)
        except Exception as e: logger.error(f"Error setting up reload button: {e}")

    def _on_reload_button_clicked(self):
        """v4.0 S18: Reload plugin after saving config."""
        from qgis.PyQt.QtWidgets import QMessageBox
        if self.config_changes_pending and self.pending_config_changes: self.apply_pending_config_changes()
        self.save_configuration_model()
        if QMessageBox.question(self, self.tr("Reload Plugin"), self.tr("Do you want to reload FilterMate to apply all configuration changes?"),
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes:
            self.reload_plugin()

    def manage_output_name(self):
        """v4.0 S18: Set export output name."""
        self.current_project_title, self.current_project_path = self.PROJECT.fileName().split('.')[0], self.PROJECT.homePath()
        self.output_name = f"export_{self.current_project_title}" if self.current_project_title else 'export'

    def set_widget_icon(self, config_widget_path):
        """v4.0 Sprint 17: Set widget icon from config path."""
        if not self.widgets_initialized or len(config_widget_path) != 6: return
        cfg = self.CONFIG_DATA
        for p in config_widget_path[:4]: cfg = cfg[p]
        cfg = cfg[config_widget_path[4]][config_widget_path[5]]
        wgt = self.widgets[config_widget_path[4]][config_widget_path[5]]
        file_path = None
        if isinstance(cfg, dict):
            for key in ["ICON_ON_FALSE", "ICON_ON_TRUE"]:
                if key in cfg: wgt[key] = os.path.join(self.plugin_dir, "icons", cfg[key]); file_path = wgt[key]
        elif isinstance(cfg, str): wgt["ICON"] = file_path = os.path.join(self.plugin_dir, "icons", cfg)
        if file_path:
            icon = get_themed_icon(file_path) if ICON_THEME_AVAILABLE else QtGui.QIcon(file_path)
            wgt["WIDGET"].setIcon(icon)

    def switch_widget_icon(self, widget_path, state):
        """v4.0 Sprint 17: Switch widget icon based on state."""
        key = "ICON_ON_TRUE" if state else "ICON_ON_FALSE"
        icon_path = self.widgets[widget_path[0].upper()][widget_path[1].upper()][key]
        icon = get_themed_icon(icon_path) if ICON_THEME_AVAILABLE else QtGui.QIcon(icon_path)
        self.widgets[widget_path[0].upper()][widget_path[1].upper()]["WIDGET"].setIcon(icon)

    def icon_per_geometry_type(self, geometry_type):
        """v4.0 Sprint 17: Get cached icon for geometry type.

        Supports both legacy format ('GeometryType.Point') and
        short format ('Point') for backward compatibility.

        Args:
            geometry_type: Geometry type string (either format)

        Returns:
            QIcon: Icon for the geometry type

        v4.0.1: REGRESSION FIX - Added all geometry type format variations
        """
        if geometry_type in self._icon_cache: return self._icon_cache[geometry_type]

        # Support ALL format variations for maximum compatibility
        # Legacy format: 'GeometryType.Point', 'GeometryType.Line', 'GeometryType.Polygon'
        # Short format: 'Point', 'Line', 'Polygon'
        # New format: 'LineString' (from infrastructure/utils geometry_type_to_string)
        icon_map = {
            # Legacy format (from PROJECT_LAYERS infos - original v2.3.8)
            'GeometryType.Line': QgsLayerItem.iconLine,
            'GeometryType.Point': QgsLayerItem.iconPoint,
            'GeometryType.Polygon': QgsLayerItem.iconPolygon,
            'GeometryType.UnknownGeometry': QgsLayerItem.iconTable,
            'GeometryType.Null': QgsLayerItem.iconTable,
            'GeometryType.Unknown': QgsLayerItem.iconDefault,
            # Short format
            'Line': QgsLayerItem.iconLine,
            'Point': QgsLayerItem.iconPoint,
            'Polygon': QgsLayerItem.iconPolygon,
            'Unknown': QgsLayerItem.iconTable,
            'Null': QgsLayerItem.iconTable,
            'NoGeometry': QgsLayerItem.iconTable,
            # New format from infrastructure/utils geometry_type_to_string
            'LineString': QgsLayerItem.iconLine,
            'MultiPoint': QgsLayerItem.iconPoint,
            'MultiLineString': QgsLayerItem.iconLine,
            'MultiPolygon': QgsLayerItem.iconPolygon,
        }
        icon_func = icon_map.get(geometry_type, QgsLayerItem.iconDefault)
        icon = icon_func()

        # Cache AND return the icon!
        # Missing cache storage and return statement caused NULL icons in combobox
        self._icon_cache[geometry_type] = icon

        # DIAGNOSTIC: Verify icon is valid
        if icon.isNull():
            logger.warning(f"icon_per_geometry_type: Generated NULL icon for geometry_type='{geometry_type}'")
        else:
            logger.debug(f"icon_per_geometry_type: Valid icon for geometry_type='{geometry_type}', cached")

        return icon

    def filtering_populate_predicates_chekableCombobox(self):
        """v4.0 S18: Populate geometric predicates combobox."""
        try:
            predicates = self._controller_integration.delegate_filtering_get_available_predicates() if self._controller_integration else None
            self.predicates = predicates or ["Intersect", "Contain", "Disjoint", "Equal", "Touch", "Overlap", "Are within", "Cross"]
            logger.info(f"🔧 filtering_populate_predicates_chekableCombobox: predicates={self.predicates}")

            # Get widget from configuration
            if not hasattr(self, 'widgets') or self.widgets is None:
                logger.error("❌ self.widgets is None or not initialized!")
                # Fallback: access widget directly
                w = self.comboBox_filtering_geometric_predicates
            elif "FILTERING" not in self.widgets:
                logger.error("❌ 'FILTERING' not in self.widgets!")
                w = self.comboBox_filtering_geometric_predicates
            elif "GEOMETRIC_PREDICATES" not in self.widgets["FILTERING"]:
                logger.error("❌ 'GEOMETRIC_PREDICATES' not in self.widgets['FILTERING']!")
                w = self.comboBox_filtering_geometric_predicates
            else:
                w = self.widgets["FILTERING"]["GEOMETRIC_PREDICATES"]["WIDGET"]

            logger.info(f"🔧 Widget type: {type(w).__name__}, widget={w}")
            logger.info(f"🔧 Widget count before clear: {w.count()}")

            w.clear()
            logger.info(f"🔧 Widget count after clear: {w.count()}")

            # Add items one by one for better diagnostics
            for pred in self.predicates:
                w.addItem(pred)

            logger.info(f"✅ Widget count after addItems: {w.count()}")
            logger.info(f"✅ Widget items: {[w.itemText(i) for i in range(w.count())]}")

        except Exception as e:
            logger.error(f"❌ filtering_populate_predicates_chekableCombobox FAILED: {e}", exc_info=True)
            # Fallback: try direct widget access
            try:
                w = self.comboBox_filtering_geometric_predicates
                w.clear()
                w.addItems(["Intersect", "Contain", "Disjoint", "Equal", "Touch", "Overlap", "Are within", "Cross"])
                logger.info(f"✅ Fallback succeeded, widget count: {w.count()}")
            except Exception as e2:
                logger.error(f"❌ Fallback also failed: {e2}", exc_info=True)

    def filtering_populate_buffer_type_combobox(self):
        """v4.0 S18: Populate buffer type combobox."""
        buffer_types = self._controller_integration.delegate_filtering_get_available_buffer_types() if self._controller_integration else None
        w = self.widgets["FILTERING"]["BUFFER_TYPE"]["WIDGET"]; w.clear(); w.addItems(buffer_types or ["Round", "Flat", "Square"])
        if not w.currentText(): w.setCurrentIndex(0)

    def filtering_populate_layers_chekableCombobox(self, layer=None):
        """Populate layers-to-filter combobox.

        FIX 2026-01-16: Fallback to direct method if controller delegation fails.
        This ensures the list is always populated, even if PROJECT_LAYERS is incomplete.
        """
        logger.info(f"🔍 filtering_populate_layers_chekableCombobox called for layer: {layer.name() if layer else 'None'}")
        logger.info(f"🔍   widgets_initialized={self.widgets_initialized}, _controller_integration={self._controller_integration is not None}")
        logger.info(f"🔍   PROJECT_LAYERS count={len(self.PROJECT_LAYERS) if self.PROJECT_LAYERS else 0}")
        if self.PROJECT_LAYERS:
            logger.info(f"🔍   PROJECT_LAYERS keys={list(self.PROJECT_LAYERS.keys())[:5]}...")  # First 5

        success = False

        # Try controller delegation first (preferred method - handles PostgreSQL/remote layers)
        if self.widgets_initialized and self._controller_integration:
            result = self._controller_integration.delegate_populate_layers_checkable_combobox(layer)
            logger.info(f"🔍   Controller delegation returned: {result}")
            if result:
                success = True
                # Force visual refresh of the combobox
                if "FILTERING" in self.widgets and "LAYERS_TO_FILTER" in self.widgets["FILTERING"]:
                    widget = self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"]
                    if widget:
                        logger.info(f"🔍   Widget count after controller population: {widget.count()}")
                        widget.update()
                        widget.repaint()

        # FALLBACK: Use direct method if controller failed
        if not success:
            logger.warning("⚠️  Controller delegation failed or unavailable - using direct fallback method")
            try:
                self.manageSignal(["FILTERING", "LAYERS_TO_FILTER"], 'disconnect')
                target_layer = layer or self.current_layer
                if target_layer:
                    result = self._populate_filtering_layers_direct(target_layer)
                    logger.info(f"🔍   Direct fallback returned: {result}")
                    if "FILTERING" in self.widgets and "LAYERS_TO_FILTER" in self.widgets["FILTERING"]:
                        widget = self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"]
                        if widget:
                            logger.info(f"🔍   Widget count after direct population: {widget.count()}")
                else:
                    logger.warning("❌ No layer available for direct population")
                self.manageSignal(["FILTERING", "LAYERS_TO_FILTER"], 'connect', 'checkedItemsChanged')
            except Exception as e:
                logger.error(f"❌ Direct fallback failed: {e}", exc_info=True)

    def exporting_populate_combobox(self):
        """Populate export layers combobox.

        FIX 2026-01-16: Fallback to direct method if controller delegation fails.
        This ensures the list is always populated, even if PROJECT_LAYERS is incomplete.
        """
        logger.info("🔍 exporting_populate_combobox called")
        logger.info(f"🔍   _controller_integration={self._controller_integration is not None}")
        logger.info(f"🔍   PROJECT_LAYERS count={len(self.PROJECT_LAYERS) if self.PROJECT_LAYERS else 0}")

        success = False

        # Try controller delegation first (preferred method - handles PostgreSQL/remote layers)
        if self._controller_integration:
            result = self._controller_integration.delegate_populate_export_combobox()
            logger.info(f"🔍   Controller delegation returned: {result}")
            if result:
                success = True
                # Check widget count
                if "EXPORTING" in self.widgets and "LAYERS_TO_EXPORT" in self.widgets["EXPORTING"]:
                    widget = self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"]
                    if widget:
                        logger.info(f"🔍   Widget count after controller population: {widget.count()}")

        # FALLBACK: Use direct method if controller failed
        if not success:
            logger.warning("⚠️  Controller delegation failed or unavailable - using direct fallback method")
            try:
                self.manageSignal(["EXPORTING", "LAYERS_TO_EXPORT"], 'disconnect')
                result = self._populate_export_combobox_direct()
                logger.info(f"🔍   Direct fallback returned: {result}")
                if "EXPORTING" in self.widgets and "LAYERS_TO_EXPORT" in self.widgets["EXPORTING"]:
                    widget = self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"]
                    if widget:
                        logger.info(f"🔍   Widget count after direct population: {widget.count()}")
                self.manageSignal(["EXPORTING", "LAYERS_TO_EXPORT"], 'connect', 'checkedItemsChanged')
            except Exception as e:
                logger.error(f"❌ Direct fallback failed: {e}", exc_info=True)

    def _on_project_layers_ready(self):
        """v4.0.4: Callback when PROJECT_LAYERS is fully populated and ready.

        This method is called via projectLayersReady signal after add_layers task completes.
        It ensures comboboxes are populated only when PROJECT_LAYERS contains all layers.

        FIX v4.0.5: Set has_loaded_layers=True here since signal may fire before
        filter_mate_app.py sets it, causing populate_export_combobox() to skip.

        FIX v4.0.7: Use controller delegation methods for full logic (PostgreSQL/remote layers).
        REGRESSION FIX: Direct methods bypassed controller logic for missing layers.
        """
        logger.info(f"🔔 _on_project_layers_ready: PROJECT_LAYERS has {len(self.PROJECT_LAYERS) if self.PROJECT_LAYERS else 0} layers")
        logger.info(f"🔧 widgets_initialized={self.widgets_initialized}, _controller_integration={self._controller_integration is not None}")

        # Ensure flags are set
        self.has_loaded_layers = True

        # Check if we can use controller delegation (preferred method)
        can_use_controllers = (
            self.widgets_initialized and
            self._controller_integration is not None
        )
        logger.info(f"🔧 can_use_controllers={can_use_controllers}")

        # Use controller delegation for FULL logic (handles PostgreSQL/remote layers)
        if can_use_controllers:
            logger.info("✅ Using controller delegation (full logic)")

            # Populate export combobox via controller
            try:
                self.manageSignal(["EXPORTING", "LAYERS_TO_EXPORT"], 'disconnect')
                success = self._controller_integration.delegate_populate_export_combobox()
                self.manageSignal(["EXPORTING", "LAYERS_TO_EXPORT"], 'connect', 'checkedItemsChanged')
                if success:
                    logger.info("✅ Export combobox populated via controller")
                else:
                    logger.warning("⚠️ Controller populate_export_combobox returned False")

                # FIX 2026-01-22: Sync HAS_LAYERS_TO_EXPORT after loading project
                # If layers are already checked in the widget (from saved project state),
                # we need to update HAS_LAYERS_TO_EXPORT accordingly
                try:
                    layers_to_export = self.get_layers_to_export()
                    current_has_layers = self.project_props.get('EXPORTING', {}).get('HAS_LAYERS_TO_EXPORT', False)

                    if layers_to_export:
                        has_layers = len(layers_to_export) > 0

                        if has_layers != current_has_layers:
                            self.project_props['EXPORTING']['HAS_LAYERS_TO_EXPORT'] = has_layers
                            # Update button widget
                            has_layers_widget = self.widgets.get('EXPORTING', {}).get('HAS_LAYERS_TO_EXPORT', {}).get('WIDGET')
                            if has_layers_widget and hasattr(has_layers_widget, 'setChecked'):
                                has_layers_widget.blockSignals(True)
                                has_layers_widget.setChecked(has_layers)
                                has_layers_widget.blockSignals(False)
                            logger.info(f"✅ Synced HAS_LAYERS_TO_EXPORT = {has_layers} (found {len(layers_to_export)} checked layers)")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to sync HAS_LAYERS_TO_EXPORT: {e}")

            except Exception as e:
                logger.error(f"❌ Failed to populate export combobox via controller: {e}", exc_info=True)

            # Populate filtering layers combobox via controller
            try:
                layer = self.current_layer
                if layer:
                    self.manageSignal(["FILTERING", "LAYERS_TO_FILTER"], 'disconnect')
                    success = self._controller_integration.delegate_populate_layers_checkable_combobox(layer)
                    self.manageSignal(["FILTERING", "LAYERS_TO_FILTER"], 'connect', 'checkedItemsChanged')
                    if success:
                        logger.info("✅ Filtering layers combobox populated via controller")
                    else:
                        logger.warning("⚠️ Controller populate_layers_checkable_combobox returned False")
                else:
                    logger.warning("⚠️ No current layer - skipping filtering layers population")
            except Exception as e:
                logger.error(f"❌ Failed to populate filtering layers via controller: {e}", exc_info=True)
        else:
            # FALLBACK: Use direct methods (simplified logic, no PostgreSQL/remote handling)
            logger.warning("⚠️ Controllers not available - using fallback direct methods")

            try:
                success = self._populate_export_combobox_direct()
                if success:
                    logger.info("✅ Export combobox populated (fallback direct method)")
                else:
                    logger.warning("⚠️ Fallback direct method returned False")
            except Exception as e:
                logger.error(f"❌ Fallback direct method failed: {e}", exc_info=True)

            try:
                layer = self.current_layer
                if layer:
                    success = self._populate_filtering_layers_direct(layer)
                    if success:
                        logger.info("✅ Filtering layers populated (fallback direct method)")
                    else:
                        logger.warning("⚠️ Fallback direct method returned False")
            except Exception as e:
                logger.error(f"❌ Fallback filtering layers failed: {e}", exc_info=True)

    def _populate_export_combobox_direct(self) -> bool:
        """v4.0.6: Direct population of export combobox without controller dependency.

        This is a fallback method that populates the combobox directly,
        bypassing the controller integration which may not be initialized.

        Returns:
            True if population succeeded, False otherwise
        """
        try:
            from qgis.core import QgsVectorLayer, QgsProject
            from qgis.PyQt.QtCore import Qt

            # Check preconditions
            logger.info(f"🔍 _populate_export_combobox_direct START: widgets_initialized={self.widgets_initialized}")
            if not self.widgets_initialized:
                logger.warning("❌ _populate_export_combobox_direct: widgets not initialized")
                return False
            if not self.PROJECT_LAYERS:
                logger.warning("❌ _populate_export_combobox_direct: PROJECT_LAYERS empty")
                return False

            logger.info(f"🔍 _populate_export_combobox_direct: PROJECT_LAYERS has {len(self.PROJECT_LAYERS)} layers")

            # Get saved preferences
            layers_to_export = []
            datatype_to_export = ''
            if self.project_props.get('EXPORTING', {}).get('HAS_LAYERS_TO_EXPORT'):
                layers_to_export = self.project_props['EXPORTING'].get('LAYERS_TO_EXPORT', [])
            if self.project_props.get('EXPORTING', {}).get('HAS_DATATYPE_TO_EXPORT'):
                datatype_to_export = self.project_props['EXPORTING'].get('DATATYPE_TO_EXPORT', '')

            # Import validation
            try:
                from .infrastructure.utils.validation_utils import is_layer_source_available
            except ImportError:
                def is_layer_source_available(layer, require_psycopg2=False):
                    return layer.isValid()

            project = QgsProject.instance()

            # Clear and populate layers widget
            logger.info("🔍 _populate_export_combobox_direct: Accessing widget via self.widgets['EXPORTING']['LAYERS_TO_EXPORT']['WIDGET']")
            logger.info(f"🔍 _populate_export_combobox_direct: self.widgets keys = {list(self.widgets.keys()) if self.widgets else 'None'}")
            if self.widgets and "EXPORTING" in self.widgets:
                logger.info(f"🔍 _populate_export_combobox_direct: EXPORTING keys = {list(self.widgets['EXPORTING'].keys())}")

            layers_widget = self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"]
            logger.info(f"🔍 _populate_export_combobox_direct: layers_widget = {layers_widget}, type = {type(layers_widget).__name__}")
            layers_widget.clear()
            item_index = 0

            for key in list(self.PROJECT_LAYERS.keys()):
                if key not in self.PROJECT_LAYERS or "infos" not in self.PROJECT_LAYERS[key]:
                    continue

                layer_info = self.PROJECT_LAYERS[key]["infos"]
                required_keys = ["layer_id", "layer_name", "layer_crs_authid", "layer_geometry_type"]
                if any(k not in layer_info or layer_info[k] is None for k in required_keys):
                    continue

                layer_id = layer_info["layer_id"]
                layer_name = layer_info["layer_name"]
                layer_crs_authid = layer_info["layer_crs_authid"]
                geom_type = layer_info["layer_geometry_type"]
                layer_icon = self.icon_per_geometry_type(geom_type)

                # Validate layer
                layer_obj = project.mapLayer(layer_id)
                if layer_obj and isinstance(layer_obj, QgsVectorLayer) and is_layer_source_available(layer_obj, require_psycopg2=False):
                    display_name = f"{layer_name} [{layer_crs_authid}]"
                    item_data = {"layer_id": key, "layer_geometry_type": geom_type}
                    layers_widget.addItem(layer_icon, display_name, item_data)
                    item = layers_widget.model().item(item_index)
                    item.setCheckState(Qt.Checked if key in layers_to_export else Qt.Unchecked)
                    item_index += 1

            logger.info(f"✅ _populate_export_combobox_direct: Added {item_index} layers to combobox")

            # Populate datatype/format combobox
            try:
                from osgeo import ogr
                datatype_widget = self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"]
                datatype_widget.clear()
                ogr_driver_list = sorted([ogr.GetDriver(i).GetDescription() for i in range(ogr.GetDriverCount())])
                datatype_widget.addItems(ogr_driver_list)
                logger.info(f"_populate_export_combobox_direct: Added {len(ogr_driver_list)} export formats")

                if datatype_to_export:
                    idx = datatype_widget.findText(datatype_to_export)
                    datatype_widget.setCurrentIndex(idx if idx >= 0 else datatype_widget.findText('GPKG'))
                else:
                    datatype_widget.setCurrentIndex(datatype_widget.findText('GPKG'))
            except ImportError:
                logger.warning("_populate_export_combobox_direct: OGR not available")

            return item_index > 0

        except Exception as e:
            logger.error(f"_populate_export_combobox_direct failed: {e}", exc_info=True)
            return False

    def _populate_filtering_layers_direct(self, layer) -> bool:
        """v4.0.6: Direct population of filtering layers combobox without controller dependency.

        Args:
            layer: Source layer for which to populate target layers

        Returns:
            True if population succeeded, False otherwise
        """
        try:
            from qgis.core import QgsVectorLayer, QgsProject
            from qgis.PyQt.QtCore import Qt

            # Check preconditions
            logger.info(f"🔍 _populate_filtering_layers_direct START: layer={layer.name() if layer else 'None'}, widgets_initialized={self.widgets_initialized}")
            if not self.widgets_initialized:
                logger.warning("❌ _populate_filtering_layers_direct: widgets not initialized")
                return False
            if not self.PROJECT_LAYERS:
                logger.warning("❌ _populate_filtering_layers_direct: PROJECT_LAYERS empty")
                return False
            if not layer or not isinstance(layer, QgsVectorLayer):
                logger.warning("❌ _populate_filtering_layers_direct: invalid layer")
                return False
            if layer.id() not in self.PROJECT_LAYERS:
                logger.warning(f"❌ _populate_filtering_layers_direct: layer {layer.name()} not in PROJECT_LAYERS")
                return False

            logger.info(f"🔍 _populate_filtering_layers_direct: PROJECT_LAYERS has {len(self.PROJECT_LAYERS)} layers")

            # Import validation
            try:
                from .infrastructure.utils.validation_utils import is_layer_source_available
            except ImportError:
                def is_layer_source_available(layer, require_psycopg2=False):
                    return layer.isValid()

            layer_props = self.PROJECT_LAYERS[layer.id()]
            project = QgsProject.instance()

            # Get saved layers to filter
            has_layers = layer_props.get("filtering", {}).get("has_layers_to_filter", False)
            layers_to_filter = layer_props.get("filtering", {}).get("layers_to_filter", [])

            # Remove source layer from targets if present
            source_layer_id = layer.id()
            if source_layer_id in layers_to_filter:
                layers_to_filter = [lid for lid in layers_to_filter if lid != source_layer_id]

            # Clear and populate widget
            logger.info("🔍 _populate_filtering_layers_direct: Accessing widget via self.widgets['FILTERING']['LAYERS_TO_FILTER']['WIDGET']")
            logger.info(f"🔍 _populate_filtering_layers_direct: self.widgets keys = {list(self.widgets.keys()) if self.widgets else 'None'}")
            if self.widgets and "FILTERING" in self.widgets:
                logger.info(f"🔍 _populate_filtering_layers_direct: FILTERING keys = {list(self.widgets['FILTERING'].keys())}")

            layers_widget = self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"]
            logger.info(f"🔍 _populate_filtering_layers_direct: layers_widget = {layers_widget}, type = {type(layers_widget).__name__}")
            layers_widget.clear()
            item_index = 0

            for key in list(self.PROJECT_LAYERS.keys()):
                # Skip source layer
                if key == layer.id():
                    continue

                if key not in self.PROJECT_LAYERS or "infos" not in self.PROJECT_LAYERS[key]:
                    continue

                layer_info = self.PROJECT_LAYERS[key]["infos"]
                required_keys = ["layer_id", "layer_name", "layer_crs_authid", "layer_geometry_type"]
                if any(k not in layer_info or layer_info[k] is None for k in required_keys):
                    continue

                layer_id = layer_info["layer_id"]
                layer_name = layer_info["layer_name"]
                layer_crs = layer_info["layer_crs_authid"]
                geom_type = layer_info["layer_geometry_type"]
                layer_icon = self.icon_per_geometry_type(geom_type)

                # Validate layer
                layer_obj = project.mapLayer(layer_id)
                if not layer_obj or not isinstance(layer_obj, QgsVectorLayer):
                    continue
                # Skip non-spatial tables (tables without geometry)
                if not layer_obj.isSpatial():
                    continue
                if not is_layer_source_available(layer_obj, require_psycopg2=False):
                    continue

                # Add to combobox
                display_name = f"{layer_name} [{layer_crs}]"
                item_data = {"layer_id": key, "layer_geometry_type": geom_type}
                layers_widget.addItem(layer_icon, display_name, item_data)

                item = layers_widget.model().item(item_index)
                if has_layers and layer_id in layers_to_filter:
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)
                item_index += 1

            logger.info(f"✅ _populate_filtering_layers_direct: Added {item_index} layers (source '{layer.name()}' excluded)")
            return item_index > 0

        except Exception as e:
            logger.error(f"_populate_filtering_layers_direct failed: {e}", exc_info=True)
            return False

    def _apply_auto_configuration(self):
        """Apply auto-configuration from environment."""
        return ui_utils.auto_configure_from_environment(self.CONFIG_DATA) if UI_CONFIG_AVAILABLE else {}

    def _apply_stylesheet(self):
        """
        DISABLED 2026-01-21: Testing without stylesheet to isolate display issue.
        If expression builder displays correctly without this, the CSS is the problem.
        """
        logger.info("Stylesheet application DISABLED for testing")
        # StyleLoader.set_theme_from_config(self.dockWidgetContents, self.CONFIG_DATA)

    def _configure_pushbuttons(self, pushButton_config, icons_sizes, font):
        """Delegate to ConfigurationManager."""
        if self._configuration_manager: self._configuration_manager.configure_pushbuttons(pushButton_config, icons_sizes, font)

    def _configure_other_widgets(self, font):
        """Delegate to ConfigurationManager."""
        if self._configuration_manager: self._configuration_manager.configure_other_widgets(font)

    def _configure_key_widgets_sizes(self, icons_sizes):
        """Delegate to ConfigurationManager."""
        if self._configuration_manager: self._configuration_manager.configure_key_widgets_sizes(icons_sizes)

    def manage_ui_style(self):
        """Apply UI styling based on QGIS theme.

        Configures visual appearance including:
        - Stylesheet application via ThemeManager or legacy path
        - Icon theme setup (light/dark mode support)
        - Button styling via ButtonStyler

        Note:
            Uses manager classes if available, falls back to legacy methods.
            Installs child dialog filter to prevent style bleeding.
        """
        if self._theme_manager:
            self._theme_manager.setup()
        else:
            self._apply_auto_configuration()
            self._apply_stylesheet()
            self._setup_theme_watcher()
            # FIX 2026-01-21: Install child dialog filter for legacy path
            self._install_legacy_child_dialog_filter()

        if self._icon_manager:
            self._icon_manager.setup()
        elif ICON_THEME_AVAILABLE:
            IconThemeManager.set_theme(StyleLoader.detect_qgis_theme())

        if self._button_styler:
            self._button_styler.setup()

    def _install_legacy_child_dialog_filter(self):
        """
        Install child dialog filter for legacy code path.

        This prevents FilterMate styles from affecting QGIS dialogs
        when ThemeManager is not available.

        FIX 2026-01-21: DISABLED - Testing if the issue comes from FilterMate or QGIS itself.
        The global filter was causing more problems than it solved.
        """
        # DISABLED 2026-01-21: Testing without filter to isolate the root cause
        # try:
        #     from ui.styles.theme_manager import GlobalDialogStyleFilter
        #     # Install global filter on QApplication (singleton pattern)
        #     GlobalDialogStyleFilter.install()
        #     logger.debug("Global dialog style filter installed")
        # except Exception as e:
        #     logger.debug(f"Could not install global dialog filter: {e}")

    def _setup_theme_watcher(self):
        """Setup QGIS theme watcher for dark/light mode switching."""
        try:
            self._theme_watcher = QGISThemeWatcher.get_instance(); current_theme = StyleLoader.detect_qgis_theme()
            if ICON_THEME_AVAILABLE: IconThemeManager.set_theme(current_theme)
            self._theme_watcher.add_callback(self._on_qgis_theme_changed)
            if not self._theme_watcher.is_watching: self._theme_watcher.start_watching()
            if current_theme == 'dark': self._refresh_icons_for_theme()
        except Exception as e: logger.warning(f"Could not setup theme watcher: {e}")

    def _on_qgis_theme_changed(self, new_theme: str):
        """Handle QGIS theme change event."""
        try:
            if ICON_THEME_AVAILABLE: IconThemeManager.set_theme(new_theme)
            StyleLoader.set_theme_from_config(self.dockWidgetContents, self.CONFIG_DATA, new_theme); self._refresh_icons_for_theme()
            if hasattr(self, 'config_view') and self.config_view: self.config_view.refresh_theme_stylesheet(force_dark=(new_theme == 'dark'))
            show_info("FilterMate", f"Theme adapted: {'Dark mode' if new_theme == 'dark' else 'Light mode'}")
        except Exception as e: logger.error(f"Error applying theme change: {e}")

    def _refresh_icons_for_theme(self):
        """Refresh all button icons for the current theme."""
        if not ICON_THEME_AVAILABLE or not self.widgets_initialized: return
        try:
            for idx, icon in enumerate(["filter_multi.png", "save.png", "parameters.png"]):
                p = os.path.join(self.plugin_dir, "icons", icon)
                if os.path.exists(p): self.toolBox_tabTools.setItemIcon(idx, get_themed_icon(p))
            for wg in self.widgets:
                for wn in self.widgets[wg]:
                    wi = self.widgets[wg][wn]
                    if wi.get("TYPE") != "PushButton": continue
                    if (ip := wi.get("ICON") or wi.get("ICON_ON_FALSE")) and os.path.exists(ip): wi.get("WIDGET").setIcon(get_themed_icon(ip)); wi.get("WIDGET").setProperty('icon_path', ip)
        except Exception as e: logger.debug(f"refresh_button_icons cosmetic update: {e}")

    def set_widgets_enabled_state(self, state):
        """
        v4.0 S18: Enable/disable all plugin widgets.
        v4.0.5: Some widgets (comboBox_filtering_current_layer, checkBox_filtering_use_centroids_source_layer)
                are ALWAYS enabled regardless of the state parameter.
        """
        skip_types = ("JsonTreeView", "LayerTreeView", "JsonModel", "ToolBox")

        # Widgets that should ALWAYS remain enabled
        always_enabled_widgets = {
            'comboBox_filtering_current_layer',
            'checkBox_filtering_use_centroids_source_layer'
        }

        for wg in self.widgets:
            for wn in self.widgets[wg]:
                wt, w = self.widgets[wg][wn]["TYPE"], self.widgets[wg][wn]["WIDGET"]
                if wt in skip_types: continue

                # Check if this is an always-enabled widget
                widget_name = None
                if hasattr(w, 'objectName'):
                    widget_name = w.objectName()

                is_always_enabled = widget_name in always_enabled_widgets if widget_name else False

                w.blockSignals(True)
                if wt in ("PushButton", "GroupBox") and w.isCheckable() and not state:
                    w.setChecked(False)
                    if wt == "GroupBox":
                        w.setCollapsed(True)

                # Apply state or force enabled
                w.setEnabled(True if is_always_enabled else state)
                w.blockSignals(False)

    def connect_widgets_signals(self):
        """Connect all widget signals to their handlers.

        Iterates through the widgets registry and connects signals defined in
        widget configuration. Uses manageSignal() for actual connection logic.

        Note:
            Handles already-connected signals gracefully.
            Skips 'QGIS' group as those are managed separately.
        """
        for grp in [g for g in self.widgets if g != 'QGIS']:
            for w in self.widgets[grp]:
                try: self.manageSignal([grp, w], 'connect')
                except Exception:  # Signal may already be connected - expected
                    pass

    def disconnect_widgets_signals(self):
        """Disconnect all widget signals from their handlers.

        Safely disconnects all signals connected by connect_widgets_signals().
        Used during plugin cleanup and when reinitializing widgets.

        Note:
            Handles already-disconnected signals gracefully.
            Skips 'QGIS' group as those are managed separately.
        """
        if not self.widgets: return
        for grp in [g for g in self.widgets if g != 'QGIS']:
            for w in self.widgets[grp]:
                try: self.manageSignal([grp, w], 'disconnect')
                except Exception:  # Signal may already be disconnected - expected
                    pass

    def force_reconnect_action_signals(self):
        """v4.0 Sprint 8: Ultra-simplified - force reconnect ACTION signals bypassing cache.

        FIX 2026-01-17 v4: CRITICAL - Use DIRECT method references instead of stored lambdas.
        Stored lambdas in widgets['ACTION'][x]['SIGNALS'] may become stale references
        when widgets dict is recreated. By using direct method wrappers, we ensure
        the connection is always to the current dockwidget instance.
        """

        # Map button names to their task names and widgets
        # Use direct attribute access to widgets (more reliable than widgets dict)
        action_buttons = {
            'FILTER': ('filter', getattr(self, 'pushButton_action_filter', None)),
            'UNFILTER': ('unfilter', getattr(self, 'pushButton_action_unfilter', None)),
            'UNDO_FILTER': ('undo', getattr(self, 'pushButton_action_undo_filter', None)),
            'REDO_FILTER': ('redo', getattr(self, 'pushButton_action_redo_filter', None)),
            'EXPORT': ('export', getattr(self, 'pushButton_action_export', None)),
        }

        connected_count = 0
        for btn_name, (task_name, widget) in action_buttons.items():
            if not widget:
                continue

            key = f"ACTION.{btn_name}.clicked"
            self._signal_connection_states.pop(key, None)

            try:
                # FIX 2026-01-17 v4: Disconnect ALL receivers to ensure clean state
                try:
                    widget.clicked.disconnect()
                except TypeError:
                    pass  # No receivers connected, which is fine

                # FIX 2026-01-17 v4: Connect using a closure that captures task_name
                # This avoids relying on potentially stale lambdas from widgets dict
                def make_handler(task):
                    """Factory function to create handler with properly captured task name."""
                    def handler(state=False):
                        self.launchTaskEvent(state, task)
                    return handler

                handler = make_handler(task_name)
                widget.clicked.connect(handler)
                self._signal_connection_states[key] = True
                connected_count += 1
            except Exception as e:
                logger.debug(f"Ignored in signal reconnection for {key}: {e}")

    def force_reconnect_exporting_signals(self):
        """
        FIX 2026-01-22: Force reconnect EXPORTING signals for file/folder selection buttons.

        Connects pushButton_checkable_exporting_output_folder and pushButton_checkable_exporting_zip
        clicked signals to their respective dialog handlers (dialog_export_output_path, dialog_export_output_pathzip).

        These buttons were defined in configuration_manager.py but their signals were never connected.
        This method ensures they are properly wired at startup.
        """
        if 'EXPORTING' not in self.widgets:
            logger.warning("force_reconnect_exporting_signals: EXPORTING category not in widgets")
            return

        # Map widget names to their handlers
        exporting_buttons = {
            'HAS_OUTPUT_FOLDER_TO_EXPORT': ('dialog_export_output_path', getattr(self, 'pushButton_checkable_exporting_output_folder', None)),
            'HAS_ZIP_TO_EXPORT': ('dialog_export_output_pathzip', getattr(self, 'pushButton_checkable_exporting_zip', None)),
        }

        connected_count = 0
        for btn_name, (handler_name, widget) in exporting_buttons.items():
            if not widget:
                logger.debug(f"force_reconnect_exporting_signals: {btn_name} widget not found")
                continue

            # Get handler method
            handler_method = getattr(self, handler_name, None)
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
                    logger.debug(f"  Disconnected all receivers from {btn_name}.clicked")
                except TypeError:
                    pass  # No receivers connected, which is fine

                # FIX 2026-01-22: Connect clicked signal to dialog handler
                # The lambda gets the widget's checked state and calls the dialog handler
                # which will call project_property_changed with custom_functions containing ON_CHANGE
                def make_handler(handler_func, widget_ref, property_name):
                    """Factory to create handler with proper closure."""
                    def handler(checked):
                        logger.debug(f"🎯 EXPORTING handler triggered: {property_name}, checked={checked}")
                        # Call dialog handler which opens file dialog and updates widget
                        handler_func()
                    return handler

                property_name = 'has_output_folder_to_export' if btn_name == 'HAS_OUTPUT_FOLDER_TO_EXPORT' else 'has_zip_to_export'
                handler = make_handler(handler_method, widget, property_name)
                widget.clicked.connect(handler)
                self._signal_connection_states[key] = True
                connected_count += 1
                logger.debug(f"✅ force_reconnect_exporting_signals: Connected {btn_name}.clicked → {handler_name}()")
            except Exception as e:
                logger.warning(f"force_reconnect_exporting_signals: Failed to connect {btn_name}: {e}")

        logger.debug(f"🔄 force_reconnect_exporting_signals COMPLETED: {connected_count}/2 signals connected")

    def diagnose_action_buttons(self):
        """
        v2026-01-17: DIAGNOSTIC method - call from QGIS console to test button signals.

        Usage in QGIS Python console:
            from filter_mate.filter_mate_dockwidget import FilterMateDockWidget
            dw = iface.mainWindow().findChild(FilterMateDockWidget)
            dw.diagnose_action_buttons()
        """

        if 'ACTION' not in self.widgets:
            return

        for btn_name in ['FILTER', 'UNFILTER', 'UNDO_FILTER', 'REDO_FILTER']:
            if btn_name not in self.widgets['ACTION']:
                continue

            widget_info = self.widgets['ACTION'][btn_name]
            widget = widget_info.get("WIDGET")

            if widget:

                # Check signal tuple
                signals = widget_info.get("SIGNALS", [])
                for s_tuple in signals:
                    s_tuple[0] if s_tuple else "?"
                    handler = s_tuple[-1] if s_tuple else None

                    if handler:
                        # Try to manually call the handler to see what happens
                        try:
                            handler(False)  # Simulate unchecked button click
                        except Exception as e:
                            logger.debug(f"Ignored in tool button handler simulation: {e}")

        if self.current_layer:
            pass

    def force_reconnect_exploring_signals(self):
        """v4.0 S18: Force reconnect EXPLORING signals bypassing cache."""
        if 'EXPLORING' not in self.widgets: return
        # REGRESSION FIX 2026-01-13: IS_SELECTING, IS_TRACKING, IS_LINKING use 'toggled' not 'clicked'
        # FIX 2026-01-15: IDENTIFY and ZOOM removed from here - connected directly in _connect_exploring_buttons_directly
        ws = {'SINGLE_SELECTION_FEATURES': ['featureChanged'], 'SINGLE_SELECTION_EXPRESSION': ['fieldChanged'], 'MULTIPLE_SELECTION_FEATURES': ['updatingCheckedItemList', 'filteringCheckedItemList'],
              'MULTIPLE_SELECTION_EXPRESSION': ['fieldChanged'], 'CUSTOM_SELECTION_EXPRESSION': ['fieldChanged'],
              'IS_SELECTING': ['toggled'], 'IS_TRACKING': ['toggled'], 'IS_LINKING': ['toggled'], 'RESET_ALL_LAYER_PROPERTIES': ['clicked']}
        for w, signals in ws.items():
            if w not in self.widgets['EXPLORING']: continue
            for s_tuple in self.widgets['EXPLORING'][w].get("SIGNALS", []):
                if not s_tuple[-1] or s_tuple[0] not in signals: continue
                key = f"EXPLORING.{w}.{s_tuple[0]}"; self._signal_connection_states.pop(key, None)
                try: self._signal_connection_states[key] = self.changeSignalState(['EXPLORING', w], s_tuple[0], s_tuple[-1], 'connect')
                except Exception:  # Signal connection may fail if widget deleted - expected during cleanup
                    pass

        # FIX 2026-01-14: CRITICAL - Connect exploring buttons DIRECTLY with explicit handlers
        # This bypasses the complex lambda/custom_functions mechanism that may fail silently
        self._connect_exploring_buttons_directly()

        # FIX 2026-01-15 (FIX-006): CRITICAL - Also reconnect expression widget signals
        # These must be connected whenever exploring signals are reconnected
        self._setup_expression_widget_direct_connections()

    def _connect_exploring_buttons_directly(self):
        """
        FIX 2026-01-15 v3: Connect ALL exploring buttons directly (IS_SELECTING, IS_TRACKING, IS_LINKING, IDENTIFY, ZOOM, RESET).

        This method bypasses the manageSignal/custom_functions mechanism and connects
        the button signals directly to their handlers. This ensures the handlers
        are ALWAYS called when the buttons are clicked/toggled, fixing the regression where:
        - IS_SELECTING toggle didn't activate the QGIS selection tool
        - IS_TRACKING toggle didn't enable auto-zoom
        - IS_LINKING toggle didn't synchronize expression widgets
        - IDENTIFY button didn't flash features
        - ZOOM button didn't zoom to features

        v3: Also synchronizes initial button state with PROJECT_LAYERS to prevent
        desynchronization between visual state and stored state.
        """
        logger.info("🔌 _connect_exploring_buttons_directly CALLED")

        # FIX 2026-01-15 (FIX-008): REMOVED widgets_initialized check
        # Buttons exist after setupUi() even if widgets dict isn't initialized yet
        # Original check prevented buttons from being connected during manage_interactions()

        # Check if buttons exist (they should after setupUi)
        if not hasattr(self, 'pushButton_exploring_identify'):
            logger.error("❌ pushButton_exploring_identify does NOT exist!")
            return

        # FIX 2026-01-15: Connect IDENTIFY and ZOOM buttons FIRST
        # These must be connected directly, NOT via changeSignalState which can break them
        try:
            self.pushButton_exploring_identify.clicked.disconnect()
        except (TypeError, RuntimeError):
            pass
        self.pushButton_exploring_identify.clicked.connect(self.exploring_identify_clicked)
        logger.debug("✓ Connected pushButton_exploring_identify.clicked DIRECTLY")

        try:
            self.pushButton_exploring_zoom.clicked.disconnect()
        except (TypeError, RuntimeError):
            pass
        self.pushButton_exploring_zoom.clicked.connect(self.exploring_zoom_clicked)
        logger.debug("✓ Connected pushButton_exploring_zoom.clicked DIRECTLY")

        try:
            self.pushButton_exploring_reset_layer_properties.clicked.disconnect()
        except (TypeError, RuntimeError):
            pass
        self.pushButton_exploring_reset_layer_properties.clicked.connect(
            lambda: self.resetLayerVariableEvent()
        )
        logger.debug("✓ Connected pushButton_exploring_reset_layer_properties.clicked DIRECTLY")

        # IS_SELECTING: Activate selection tool on canvas + sync features
        btn_selecting = self.pushButton_checkable_exploring_selecting
        try:
            btn_selecting.toggled.disconnect()
        except (TypeError, RuntimeError):
            pass  # No connection to disconnect

        # FIX v2: Sync initial state from button to PROJECT_LAYERS on reconnection
        if self.current_layer and self.widgets_initialized:
            layer_id = self.current_layer.id()
            if layer_id in self.PROJECT_LAYERS:
                current_button_state = btn_selecting.isChecked()
                stored_state = self.PROJECT_LAYERS[layer_id]["exploring"].get("is_selecting", False)

                # If mismatch detected, log warning and sync PROJECT_LAYERS to button state
                if current_button_state != stored_state:
                    logger.warning(f"IS_SELECTING state mismatch! Button={current_button_state}, Stored={stored_state}")  # nosec B608 - false positive: logger statement, no SQL execution
                    self.PROJECT_LAYERS[layer_id]["exploring"]["is_selecting"] = current_button_state
                    logger.info(f"  → Synced is_selecting to button state: {current_button_state}")

        def _on_selecting_toggled(checked):
            """Handle IS_SELECTING toggle - activate selection tool + sync features."""
            if not self._is_layer_valid():
                return
            layer_id = self.current_layer.id()
            if layer_id in self.PROJECT_LAYERS:
                self.PROJECT_LAYERS[layer_id]["exploring"]["is_selecting"] = checked
                logger.info(f"IS_SELECTING state updated in PROJECT_LAYERS: {checked}")  # nosec B608 - false positive: logger statement, no SQL execution
            if checked:
                logger.info("IS_SELECTING ON: Calling exploring_select_features()")
                # FIX 2026-01-15 v9: Ensure selectionChanged stays connected for bidirectional sync
                self._ensure_selection_changed_connected()
                self.exploring_select_features()
            else:
                logger.info("IS_SELECTING OFF: Calling exploring_deselect_features()")
                self.exploring_deselect_features()

        btn_selecting.toggled.connect(_on_selecting_toggled)
        logger.debug("✓ Connected IS_SELECTING.toggled DIRECTLY to _on_selecting_toggled()")

        # IS_TRACKING: Enable auto-zoom on selection change
        btn_tracking = self.pushButton_checkable_exploring_tracking
        try:
            btn_tracking.toggled.disconnect()
        except (TypeError, RuntimeError):
            pass

        # FIX v2: Sync initial state from button to PROJECT_LAYERS
        if self.current_layer and self.widgets_initialized:
            layer_id = self.current_layer.id()
            if layer_id in self.PROJECT_LAYERS:
                current_button_state = btn_tracking.isChecked()
                stored_state = self.PROJECT_LAYERS[layer_id]["exploring"].get("is_tracking", False)
                if current_button_state != stored_state:
                    logger.warning(f"IS_TRACKING state mismatch! Button={current_button_state}, Stored={stored_state}")
                    self.PROJECT_LAYERS[layer_id]["exploring"]["is_tracking"] = current_button_state
                    logger.info(f"  → Synced is_tracking to button state: {current_button_state}")

        def _on_tracking_toggled(checked):
            """Handle IS_TRACKING toggle - enable auto-zoom on selection."""
            if not self._is_layer_valid():
                return
            layer_id = self.current_layer.id()
            if layer_id in self.PROJECT_LAYERS:
                self.PROJECT_LAYERS[layer_id]["exploring"]["is_tracking"] = checked
                logger.info(f"IS_TRACKING state updated in PROJECT_LAYERS: {checked}")
            if checked:
                logger.info("IS_TRACKING ON: Triggering zoom to current selection")
                # FIX 2026-01-15 v9: Ensure selectionChanged stays connected for tracking
                self._ensure_selection_changed_connected()
                self.exploring_zoom_clicked()

        btn_tracking.toggled.connect(_on_tracking_toggled)
        logger.debug("✓ Connected IS_TRACKING.toggled DIRECTLY to _on_tracking_toggled()")

        # IS_LINKING: Synchronize single/multiple selection expressions
        btn_linking = self.pushButton_checkable_exploring_linking_widgets
        try:
            btn_linking.toggled.disconnect()
        except (TypeError, RuntimeError):
            pass

        # FIX v2: Sync initial state from button to PROJECT_LAYERS
        if self.current_layer and self.widgets_initialized:
            layer_id = self.current_layer.id()
            if layer_id in self.PROJECT_LAYERS:
                current_button_state = btn_linking.isChecked()
                stored_state = self.PROJECT_LAYERS[layer_id]["exploring"].get("is_linking", False)
                if current_button_state != stored_state:
                    logger.warning(f"IS_LINKING state mismatch! Button={current_button_state}, Stored={stored_state}")
                    self.PROJECT_LAYERS[layer_id]["exploring"]["is_linking"] = current_button_state
                    logger.info(f"  → Synced is_linking to button state: {current_button_state}")

        def _on_linking_toggled(checked):
            """Handle IS_LINKING toggle - sync single/multiple selection widgets."""
            if not self._is_layer_valid():
                return
            layer_id = self.current_layer.id()
            if layer_id in self.PROJECT_LAYERS:
                self.PROJECT_LAYERS[layer_id]["exploring"]["is_linking"] = checked
                logger.info(f"IS_LINKING state updated in PROJECT_LAYERS: {checked}")
            logger.info(f"IS_LINKING {'ON' if checked else 'OFF'}: Calling exploring_link_widgets()")

            # FIX 2026-01-18 v6: When enabling IS_LINKING, propagate the CURRENT groupbox's field
            # to the other picker. This respects the user's active selection context.
            if checked and self.current_exploring_groupbox in ("single_selection", "multiple_selection"):
                # Pass the current groupbox as change_source to propagate its field to the other
                self.exploring_link_widgets(change_source=self.current_exploring_groupbox)
            else:
                self.exploring_link_widgets()

        btn_linking.toggled.connect(_on_linking_toggled)
        logger.debug("✓ Connected IS_LINKING.toggled DIRECTLY to _on_linking_toggled()")

    def manage_interactions(self):
        """v4.0 Sprint 8: Optimized - initialize widget interactions and default values."""
        logger.info("🚀 manage_interactions CALLED - Starting widget configuration")

        self.coordinateReferenceSystem = QgsCoordinateReferenceSystem()

        # FIX 2026-01-15 (FIX-009): CRITICAL - Connect exploring buttons FIRST before accessing widgets dict
        # self.widgets may not exist yet, so connect buttons first (they exist after setupUi)
        logger.info("🔌 Calling _connect_exploring_buttons_directly BEFORE widgets access...")
        self._connect_exploring_buttons_directly()
        logger.info("✅ _connect_exploring_buttons_directly completed")

        # Now safe to access self.widgets (may still fail if not initialized, but buttons are connected)
        if hasattr(self, 'widgets') and 'FILTERING' in self.widgets:
            self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"].setExpressionsEnabled(True)
            self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"].setClearValue(0.0)

        if self.PROJECT and hasattr(self, 'widgets') and 'EXPORTING' in self.widgets:
            self.widgets["EXPORTING"]["PROJECTION_TO_EXPORT"]["WIDGET"].setCrs(self.PROJECT.crs())

        # REMOVED duplicate call - already called above (FIX-009)
        # self._connect_exploring_buttons_directly()

        if self.has_loaded_layers and self.PROJECT_LAYERS:
            self.set_widgets_enabled_state(True)
            self.connect_widgets_signals()
            # FIX 2026-01-14: Force reconnect exploring button signals (IS_SELECTING, IS_TRACKING, IS_LINKING)
            # FIX 2026-01-15: This also connects IDENTIFY, ZOOM, and RESET buttons
            self.force_reconnect_exploring_signals()
            # FIX 2026-01-15 v9: Connect fieldChanged signals for expression widgets (display expression sync)
            # This was present in before_migration but missing in the migrated code
            self._setup_expression_widget_direct_connections()
            # FIX 2026-01-15 v10: CRITICAL - Force reconnect ACTION button signals (FILTER, UNFILTER, etc.)
            # Without this, clicking filter button won't trigger launchTaskEvent
            logger.debug("🔌 Force reconnecting ACTION button signals...")
            self.force_reconnect_action_signals()
            logger.debug("✓ ACTION button signals reconnected")
        else:
            self.set_widgets_enabled_state(False)
            for sp in [["DOCK", "SINGLE_SELECTION"], ["DOCK", "MULTIPLE_SELECTION"], ["DOCK", "CUSTOM_SELECTION"]]:
                try: self.manageSignal(sp, 'connect')
                except Exception:  # Signal may already be connected - expected
                    pass

        self._connect_groupbox_signals_directly()
        self.filtering_populate_predicates_chekableCombobox()
        self.filtering_populate_buffer_type_combobox()

        # UX Enhancement: Setup conditional widget states based on pushbutton toggles
        self._setup_conditional_widget_states()

        if self.init_layer and isinstance(self.init_layer, QgsVectorLayer):
            self.manage_output_name()
            # Don't populate export combobox here - will be done via projectLayersReady signal
            # self.manageSignal(["EXPORTING","LAYERS_TO_EXPORT"], 'disconnect')
            # self.exporting_populate_combobox()
            # self.manageSignal(["EXPORTING","LAYERS_TO_EXPORT"], 'connect', 'checkedItemsChanged')
            self.set_exporting_properties()
            self.exploring_groupbox_init()
            self.current_layer_changed(self.init_layer)
            self.filtering_auto_current_layer_changed()

    def _setup_conditional_widget_states(self):
        """
        UX Enhancement: Setup conditional widget enable/disable based on pushbutton checkable states.

        Connects all checkable pushbuttons to automatically enable/disable their associated widgets
        when toggled. This provides clear visual feedback about which filter/export options are active.

        Pattern: pushbutton.toggled(bool) → widgets.setEnabled(bool)

        v4.0 UX Improvement - Added January 2026
        v4.0.5: comboBox_filtering_current_layer and checkBox_filtering_use_centroids_source_layer
                are ALWAYS enabled (not controlled by pushbutton)
        """
        # Mapping: pushbutton → list of associated widgets to control
        widget_mappings = {
            # FILTERING Section
            # NOTE: pushButton_checkable_filtering_auto_current_layer has NO associated widgets
            # comboBox_filtering_current_layer and checkBox_filtering_use_centroids_source_layer
            # are ALWAYS enabled (see _ensure_always_enabled_widgets)
            'pushButton_checkable_filtering_auto_current_layer': [],
            'pushButton_checkable_filtering_layers_to_filter': [
                'checkableComboBoxLayer_filtering_layers_to_filter',
                'checkBox_filtering_use_centroids_distant_layers'
            ],
            'pushButton_checkable_filtering_current_layer_combine_operator': [
                'comboBox_filtering_source_layer_combine_operator',
                'comboBox_filtering_other_layers_combine_operator'
            ],
            'pushButton_checkable_filtering_geometric_predicates': [
                'comboBox_filtering_geometric_predicates'  # FIX: was checkableComboBox_
            ],
            'pushButton_checkable_filtering_buffer_value': [
                'mQgsDoubleSpinBox_filtering_buffer_value',
                'mPropertyOverrideButton_filtering_buffer_value_property'
            ],
            'pushButton_checkable_filtering_buffer_type': [
                'comboBox_filtering_buffer_type',
                'mQgsSpinBox_filtering_buffer_segments'
            ],

            # EXPORTING Section
            'pushButton_checkable_exporting_layers': [
                'checkableComboBoxLayer_exporting_layers'
            ],
            'pushButton_checkable_exporting_projection': [
                'mQgsProjectionSelectionWidget_exporting_projection'
            ],
            'pushButton_checkable_exporting_styles': [
                'comboBox_exporting_styles'  # FIX: was checkBox_exporting_styles_save
            ],
            'pushButton_checkable_exporting_datatype': [
                'comboBox_exporting_datatype'
            ],
            'pushButton_checkable_exporting_output_folder': [
                'lineEdit_exporting_output_folder',
                'checkBox_batch_exporting_output_folder'  # FIX: was toolButton_exporting_output_folder
            ],
            'pushButton_checkable_exporting_zip': [
                'lineEdit_exporting_zip',  # FIX: was checkBox_exporting_zip
                'checkBox_batch_exporting_zip'
            ]
        }

        # Connect each pushbutton to its widget control function
        for pushbutton_name, widget_names in widget_mappings.items():
            if not hasattr(self, pushbutton_name):
                logger.warning(f"_setup_conditional_widget_states: Pushbutton {pushbutton_name} not found")
                continue

            pushbutton = getattr(self, pushbutton_name)

            # Get actual widget references
            widgets_to_control = []
            for widget_name in widget_names:
                if hasattr(self, widget_name):
                    widgets_to_control.append(getattr(self, widget_name))
                else:
                    logger.warning(f"_setup_conditional_widget_states: Widget {widget_name} not found for {pushbutton_name}")

            if not widgets_to_control:
                logger.warning(f"_setup_conditional_widget_states: No widgets found for {pushbutton_name}")
                continue

            # Connect the toggled signal
            pushbutton.toggled.connect(
                lambda checked, widgets=widgets_to_control: self._toggle_associated_widgets(checked, widgets)
            )

            # Set initial state based on current pushbutton state
            initial_state = pushbutton.isChecked()
            self._toggle_associated_widgets(initial_state, widgets_to_control)

            logger.debug(f"✓ Connected {pushbutton_name} to {len(widgets_to_control)} widget(s)")

        # EXPLORING section pushbuttons don't have associated widgets to disable
        # (they are toggle-only functions: selecting, tracking, linking)
        # So we skip them

        # Setup buffer buttons dependency on geometric_predicates
        self._setup_buffer_buttons_dependency()

        # Ensure certain widgets are ALWAYS enabled
        self._ensure_always_enabled_widgets()

        logger.info(f"_setup_conditional_widget_states: Configured {len(widget_mappings)} pushbutton→widget mappings")

    def _setup_buffer_buttons_dependency(self):
        """
        Setup dependency: buffer buttons are disabled unless geometric_predicates is checked.

        Buffer filtering only makes sense when geometric predicates are active.
        This ensures users can't enable buffer options without first enabling geometric predicates.

        v4.0.6 UX Enhancement - Added January 2026
        v4.0.6.1: Only controls pushbuttons, not widgets. Widgets are controlled by their pushbuttons.
        """
        if not hasattr(self, 'pushButton_checkable_filtering_geometric_predicates'):
            logger.warning("_setup_buffer_buttons_dependency: geometric_predicates button not found")
            return

        predicates_btn = self.pushButton_checkable_filtering_geometric_predicates

        # Only collect buffer BUTTONS (not their associated widgets)
        buffer_buttons = []
        buffer_button_names = [
            'pushButton_checkable_filtering_buffer_value',
            'pushButton_checkable_filtering_buffer_type'
        ]

        for name in buffer_button_names:
            if hasattr(self, name):
                buffer_buttons.append(getattr(self, name))
            else:
                logger.warning(f"_setup_buffer_buttons_dependency: Button {name} not found")

        if not buffer_buttons:
            logger.warning("_setup_buffer_buttons_dependency: No buffer buttons found")
            return

        # Connect to geometric_predicates toggle
        def _on_predicates_toggled(checked):
            """
            Enable buffer BUTTONS only when geometric predicates is checked.

            When disabled, also uncheck the buttons to prevent inconsistent state.
            The widgets are controlled by their respective buttons via _toggle_associated_widgets().
            """
            for btn in buffer_buttons:
                btn.setEnabled(checked)
                # Force uncheck when disabling to maintain consistency
                if not checked and btn.isChecked():
                    btn.setChecked(False)

            logger.debug(f"Buffer buttons {'enabled' if checked else 'disabled'} (geometric_predicates={checked})")

        predicates_btn.toggled.connect(_on_predicates_toggled)

        # Set initial state
        initial_state = predicates_btn.isChecked()
        _on_predicates_toggled(initial_state)

        logger.info(f"✓ Buffer buttons dependency configured ({len(buffer_buttons)} buttons)")

    def _toggle_associated_widgets(self, enabled, widgets):
        """
        Enable or disable a list of widgets based on pushbutton toggle state.

        Args:
            enabled (bool): True to enable widgets, False to disable
            widgets (list): List of QWidget instances to enable/disable

        v4.0 UX Improvement - Added January 2026
        """
        for widget in widgets:
            if widget is not None:
                widget.setEnabled(enabled)

    def _ensure_always_enabled_widgets(self):
        """
        Ensure certain widgets are ALWAYS enabled regardless of other states.

        These widgets need to be always accessible:
        - comboBox_filtering_current_layer: Layer selection
        - checkBox_filtering_use_centroids_source_layer: Centroids option
        - pushButton_checkable_exporting_output_folder: Always clickable
        - pushButton_checkable_exporting_zip: Always clickable

        v4.0.5 - Added January 2026
        """
        always_enabled = [
            'comboBox_filtering_current_layer',
            'checkBox_filtering_use_centroids_source_layer',
            'pushButton_checkable_exporting_output_folder',
            'pushButton_checkable_exporting_zip'
        ]

        for widget_name in always_enabled:
            if hasattr(self, widget_name):
                widget = getattr(self, widget_name)
                widget.setEnabled(True)
                logger.debug(f"✓ Widget {widget_name} set to always enabled")

    def select_tabTools_index(self):
        """v4.0 S18: Update action buttons based on active tab."""
        if not self.widgets_initialized: return
        self.tabTools_current_index = self.widgets["DOCK"]["TOOLS"]["WIDGET"].currentIndex()
        states = {0: (True, True, True, True, False), 1: (False, False, False, False, True), 2: (False,) * 5}
        s = states.get(self.tabTools_current_index, (False,) * 5)
        for i, name in enumerate(['FILTER', 'UNDO_FILTER', 'REDO_FILTER', 'UNFILTER', 'EXPORT']): self.widgets["ACTION"][name]["WIDGET"].setEnabled(s[i])
        self.widgets["ACTION"]["ABOUT"]["WIDGET"].setEnabled(True)
        self.set_exporting_properties()

    def _connect_groupbox_signals_directly(self):
        """v4.0 S18: Connect groupbox signals for exclusive behavior.

        FIX 2026-01-18: Ensure signals are always unblocked even if exception occurs.
        """
        gbs = [(self.mGroupBox_exploring_single_selection, 'single_selection'),
               (self.mGroupBox_exploring_multiple_selection, 'multiple_selection'),
               (self.mGroupBox_exploring_custom_selection, 'custom_selection')]
        try:
            # Disconnect existing signals first
            for gb, _ in gbs:
                try:
                    gb.blockSignals(True)
                    try:
                        gb.toggled.disconnect()
                        gb.collapsedStateChanged.disconnect()
                    except TypeError:  # Signals not connected yet - expected on first setup
                        pass
                finally:
                    gb.blockSignals(False)  # Always unblock even if disconnect fails

            # Now connect new signals
            for gb, name in gbs:
                gb.toggled.connect(lambda c, n=name: self._on_groupbox_clicked(n, c))
                gb.collapsedStateChanged.connect(lambda col, n=name: self._on_groupbox_collapse_changed(n, col))

            logger.debug("_connect_groupbox_signals_directly: Signals connected successfully")
        except Exception as e:
            logger.warning(f"_connect_groupbox_signals_directly error: {e}")
            # Ensure all groupboxes have signals unblocked
            for gb, _ in gbs:
                try:
                    gb.blockSignals(False)
                except (RuntimeError, AttributeError):
                    pass  # Widget may have been deleted

    def _force_exploring_groupbox_exclusive(self, active_groupbox):
        """v4.0 S18: Force exclusive state for exploring groupboxes.

        FIX 2026-01-18: Added timeout protection to prevent click blocking if
        _updating_groupbox gets stuck True due to unexpected exception.
        Also ensures signals are always unblocked even if exception occurs.

        FIX 2026-01-19: Disable saveCheckedState/saveCollapsedState during update
        to prevent QGIS auto-save from interfering with exclusive behavior.
        """
        if self._updating_groupbox:
            # FIX: Check if stuck for too long (> 500ms) and force reset
            import time
            if hasattr(self, '_groupbox_update_start'):
                elapsed = time.time() - self._groupbox_update_start
                if elapsed > 0.5:
                    logger.warning(f"_force_exploring_groupbox_exclusive: _updating_groupbox stuck for {elapsed:.2f}s, forcing reset")
                    self._updating_groupbox = False
                else:
                    return
            else:
                return
        self._updating_groupbox = True
        import time
        self._groupbox_update_start = time.time()

        gbs = None
        try:
            gbs = {"single": self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"],
                   "multiple": self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"],
                   "custom": self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"]}
            active_key = active_groupbox.split("_")[0]

            # Block all signals AND disable QGIS state saving during update
            for gb in gbs.values():
                gb.blockSignals(True)
                # FIX 2026-01-19: Disable QGIS auto-save to prevent interference
                if hasattr(gb, 'setSaveCheckedState'):
                    gb.setSaveCheckedState(False)
                if hasattr(gb, 'setSaveCollapsedState'):
                    gb.setSaveCollapsedState(False)

            # Update states
            for key, gb in gbs.items():
                gb.setChecked(key == active_key)
                gb.setCollapsed(key != active_key)

            # FIX 2026-01-19: Force layout update to prevent key widgets from disappearing
            # When groupboxes collapse/expand, the layout needs to be explicitly updated
            # to ensure widget_exploring_keys remains visible
            if hasattr(self, 'widget_exploring_keys') and self.widget_exploring_keys:
                self.widget_exploring_keys.setVisible(True)
                self.widget_exploring_keys.updateGeometry()
                self.widget_exploring_keys.update()

            # Also update the parent grid layout
            if hasattr(self, 'gridLayout_main_actions') and self.gridLayout_main_actions:
                self.gridLayout_main_actions.update()
                self.gridLayout_main_actions.activate()

        except Exception as e:
            logger.warning(f"_force_exploring_groupbox_exclusive error: {e}")
        finally:
            # CRITICAL: Always unblock signals, re-enable state saving, and reset flag
            if gbs:
                for gb in gbs.values():
                    try:
                        gb.blockSignals(False)
                        # FIX 2026-01-19: Re-enable QGIS auto-save
                        if hasattr(gb, 'setSaveCheckedState'):
                            gb.setSaveCheckedState(True)
                        if hasattr(gb, 'setSaveCollapsedState'):
                            gb.setSaveCollapsedState(True)
                    except (RuntimeError, AttributeError):
                        pass  # Widget may have been deleted
            self._updating_groupbox = False

            # FIX 2026-01-19: Final visibility check after all updates
            from qgis.PyQt.QtCore import QTimer
            QTimer.singleShot(0, self._ensure_key_widgets_visible)

    def _ensure_key_widgets_visible(self):
        """FIX 2026-01-19: Ensure key widgets remain visible after groupbox changes.

        When QgsCollapsibleGroupBox collapse/expand, the layout can get corrupted
        causing widget_exploring_keys to disappear. This method forces visibility.
        """
        try:
            # Ensure exploring key widgets are visible
            if hasattr(self, 'widget_exploring_keys') and self.widget_exploring_keys:
                if not self.widget_exploring_keys.isVisible():
                    logger.warning("FIX-2026-01-19: widget_exploring_keys was hidden - restoring visibility")
                self.widget_exploring_keys.setVisible(True)
                self.widget_exploring_keys.raise_()  # Bring to front
                self.widget_exploring_keys.updateGeometry()

            # Force the parent frame to recalculate layout
            if hasattr(self, 'frame_exploring') and self.frame_exploring:
                self.frame_exploring.updateGeometry()
                self.frame_exploring.update()

        except Exception as e:
            logger.debug(f"_ensure_key_widgets_visible: {e}")

    def _on_groupbox_clicked(self, groupbox, state):
        """v4.0 S18: Handle groupbox toggle for exclusive behavior.

        FIX 2026-01-18: Added debug logging and safe signal blocking.
        """
        logger.debug(f"_on_groupbox_clicked: groupbox={groupbox}, state={state}, _updating_groupbox={self._updating_groupbox}, widgets_initialized={self.widgets_initialized}")
        if self._updating_groupbox or not self.widgets_initialized:
            logger.debug(f"_on_groupbox_clicked: BLOCKED - _updating_groupbox={self._updating_groupbox}")
            return
        if state:
            self.exploring_groupbox_changed(groupbox)
            return
        try:
            gbs = {"single_selection": self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"],
                   "multiple_selection": self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"],
                   "custom_selection": self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"]}
        except (KeyError, TypeError, AttributeError):
            return  # Widgets not yet initialized

        # Check if at least one other groupbox is checked
        if not any(gbs[k].isChecked() for k in gbs if k != groupbox):
            # No other groupbox checked - re-check this one (prevent all unchecked)
            gb = gbs[groupbox]
            try:
                gb.blockSignals(True)
                gb.setChecked(True)
                gb.setCollapsed(False)
            finally:
                gb.blockSignals(False)
        else:
            # Another groupbox is checked - switch to it
            for name, gb in gbs.items():
                if gb.isChecked():
                    self.exploring_groupbox_changed(name)
                    break

    def _on_groupbox_collapse_changed(self, groupbox, collapsed):
        """v3.1 Sprint 10: Handle groupbox expand - make it the active one.

        FIX 2026-01-18: Added debug logging to diagnose click issues.
        """
        logger.debug(f"_on_groupbox_collapse_changed: groupbox={groupbox}, collapsed={collapsed}, _updating_groupbox={self._updating_groupbox}")
        if self._updating_groupbox or not self.widgets_initialized or collapsed:
            return
        self.exploring_groupbox_changed(groupbox)

    def exploring_groupbox_init(self):
        """Initialize the exploring groupbox based on current layer.

        Configures the selection mode groupbox (single/multiple/custom) based on:
        - Current layer properties from PROJECT_LAYERS
        - Saved user preferences for groupbox state

        Defaults to 'single_selection' if no saved state exists.

        Note:
            Called on layer change and plugin initialization.
            Requires widgets_initialized to be True.
        """
        if not self.widgets_initialized: return
        self.properties_group_state_enabler(self.layer_properties_tuples_dict["selection_expression"])
        groupbox = self.PROJECT_LAYERS.get(self.current_layer.id(), {}).get("exploring", {}).get("current_exploring_groupbox", "single_selection") if self.current_layer and self.current_layer.id() in self.PROJECT_LAYERS else "single_selection"
        self.exploring_groupbox_changed(groupbox)

    def _update_exploring_buttons_state(self):
        """
        v4.0 S18: Update identify/zoom buttons based on selection.

        FIX 2026-01-15: Improved detection and fallback to canvas selection.
        FIX 2026-01-16: Use _is_layer_valid() for safe layer checking.
        """
        if not self._is_layer_valid():
            self.pushButton_exploring_identify.setEnabled(False)
            self.pushButton_exploring_zoom.setEnabled(False)
            logger.debug("_update_exploring_buttons_state: Disabled (no layer)")
            return

        has_features = False
        detection_source = "none"

        try:
            w = self.widgets.get("EXPLORING", {})

            # Check widget-specific features
            if self.current_exploring_groupbox == "single_selection":
                picker = w.get("SINGLE_SELECTION_FEATURES", {}).get("WIDGET")
                if picker:
                    # FIX 2026-01-22: Also check saved FID as authoritative source
                    # picker.feature() may be invalid if layer has a filter excluding the selected feature
                    saved_fid = getattr(self, '_last_single_selection_fid', None)
                    saved_layer_id = getattr(self, '_last_single_selection_layer_id', None)
                    if saved_fid is not None and self.current_layer and saved_layer_id == self.current_layer.id():
                        has_features = True
                        detection_source = "single_picker_saved_fid"
                    else:
                        f = picker.feature()
                        has_features = f is not None and (not hasattr(f, 'isValid') or f.isValid())
                        detection_source = "single_picker" if has_features else "single_picker_empty"

            elif self.current_exploring_groupbox == "multiple_selection":
                combo = w.get("MULTIPLE_SELECTION_FEATURES", {}).get("WIDGET")
                if combo:
                    has_features = bool(combo.checkedItems())
                    detection_source = "multiple_combo" if has_features else "multiple_combo_empty"

            elif self.current_exploring_groupbox == "custom_selection":
                expr = w.get("CUSTOM_SELECTION_EXPRESSION", {}).get("WIDGET")
                if expr:
                    has_features = bool(expr.expression() and expr.expression().strip())
                    detection_source = "custom_expr" if has_features else "custom_expr_empty"

            # FIX 2026-01-15: Fallback to canvas selection if widgets don't show features
            if not has_features and self.current_layer:
                canvas_selection_count = len(self.current_layer.selectedFeatureIds())
                if canvas_selection_count > 0:
                    has_features = True
                    detection_source = f"canvas_selection_{canvas_selection_count}"
                    logger.debug(f"_update_exploring_buttons_state: Using canvas selection ({canvas_selection_count} features)")

        except Exception as e:
            logger.debug(f"_update_exploring_buttons_state error: {e}")
            # Last resort: check canvas selection
            try:
                if self.current_layer and len(self.current_layer.selectedFeatureIds()) > 0:
                    has_features = True
                    detection_source = "canvas_fallback"
            except (RuntimeError, AttributeError):
                pass  # Layer may have been deleted

        self.pushButton_exploring_identify.setEnabled(has_features)
        self.pushButton_exploring_zoom.setEnabled(has_features)
        logger.debug(f"_update_exploring_buttons_state: {has_features} (source: {detection_source})")

    def _configure_groupbox_common(self, groupbox_name):
        """v4.0 Sprint 17: Common groupbox configuration logic."""
        self.current_exploring_groupbox = groupbox_name
        self.manageSignal(["EXPLORING", "SINGLE_SELECTION_FEATURES"], 'disconnect')
        self.manageSignal(["EXPLORING", "MULTIPLE_SELECTION_FEATURES"], 'disconnect')

        # FIX 2026-01-16: Configure widgets even if layer not in PROJECT_LAYERS
        # Use first field as fallback - this fixes empty combobox on layer change
        if not self.current_layer:
            self._update_exploring_buttons_state()
            return None

        layer_props = None
        layer_in_project = self.current_layer.id() in self.PROJECT_LAYERS

        if layer_in_project:
            self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["current_exploring_groupbox"] = groupbox_name
            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
            logger.debug("_configure_groupbox_common: Layer IN PROJECT_LAYERS")
        else:
            # FIX 2026-01-16 v3: Layer not in PROJECT_LAYERS yet - MUST use fallback
            logger.info(f"⚠️ _configure_groupbox_common: Layer {self.current_layer.name()} NOT in PROJECT_LAYERS - fallback REQUIRED")

        # Try controller first (only if layer_props available)
        controller_success = False
        if self._controller_integration and layer_in_project and layer_props:
            try:
                controller_success = self._controller_integration.delegate_exploring_configure_groupbox(groupbox_name, self.current_layer, layer_props)
                logger.debug(f"_configure_groupbox_common: Controller delegation = {controller_success}")
            except Exception as e:
                logger.debug(f"_configure_groupbox_common: Controller delegation failed: {e}")
                controller_success = False

        # FIX 2026-01-16 v3: CRITICAL - Force fallback when layer not in PROJECT_LAYERS
        # Even if controller returns True, we MUST configure widgets with first field
        if not layer_in_project:
            controller_success = False
            logger.info("🔧 FORCING fallback configuration (layer not in PROJECT_LAYERS)")

        # FIX 2026-01-18 v12: Skip fallback during QGIS sync to avoid clearing populated list
        # The _sync_multiple_selection_from_qgis will handle widget population
        if self._syncing_from_qgis:
            logger.info("🛡️ _configure_groupbox_common: Skipping fallback during QGIS sync")
            return layer_props

        # FIX 2026-01-15 v5 + 2026-01-16 v2: FALLBACK - ALWAYS configure expression widgets
        # This prevents empty comboboxes when layer not in PROJECT_LAYERS yet
        # Pattern from before_migration: setEnabled(True) and setLayer(current_layer)
        if not controller_success:
            logger.debug(f"_configure_groupbox_common: Using fallback for {groupbox_name} (layer_props={'available' if layer_props else 'NULL'})")
            try:
                # Map groupbox to widget keys
                widget_configs = {
                    'single_selection': [
                        ('SINGLE_SELECTION_FEATURES', True),
                        ('SINGLE_SELECTION_EXPRESSION', True)
                    ],
                    'multiple_selection': [
                        ('MULTIPLE_SELECTION_FEATURES', True),
                        ('MULTIPLE_SELECTION_EXPRESSION', True)
                    ],
                    'custom_selection': [
                        ('CUSTOM_SELECTION_EXPRESSION', True)
                    ]
                }

                for widget_key, should_set_layer in widget_configs.get(groupbox_name, []):
                    widget_info = self.widgets.get("EXPLORING", {}).get(widget_key, {})
                    widget = widget_info.get("WIDGET")
                    if widget:
                        widget.setEnabled(True)
                        if should_set_layer and hasattr(widget, 'setLayer'):
                            try:
                                # FIX 2026-01-19: Skip setLayer if widget already has the same layer
                                # with populated list to avoid clearing checked items
                                skip_set_layer = False
                                if widget_key == 'MULTIPLE_SELECTION_FEATURES':
                                    if hasattr(widget, 'layer') and widget.layer and widget.layer.id() == self.current_layer.id():
                                        if hasattr(widget, 'list_widgets') and self.current_layer.id() in widget.list_widgets:
                                            if widget.list_widgets[self.current_layer.id()].count() > 0:
                                                logger.debug(f"_configure_groupbox_common: Skipping setLayer for {widget_key} - same layer with items")
                                                skip_set_layer = True
                                    if not skip_set_layer:
                                        widget.setLayer(self.current_layer, layer_props if layer_props else {})
                                else:
                                    widget.setLayer(self.current_layer)
                            except Exception as e:
                                logger.debug(f"Could not setLayer on {widget_key}: {e}")

                        # Set display expression for feature widgets
                        if widget_key in ('SINGLE_SELECTION_FEATURES', 'MULTIPLE_SELECTION_FEATURES'):
                            expr_key = {
                                'SINGLE_SELECTION_FEATURES': 'single_selection_expression',
                                'MULTIPLE_SELECTION_FEATURES': 'multiple_selection_expression'
                            }.get(widget_key)
                            if expr_key and hasattr(widget, 'setDisplayExpression'):
                                expr = layer_props.get("exploring", {}).get(expr_key, "") if layer_props else ""
                                # FIX 2026-01-19: Only set display expression if different
                                if expr and widget_key == 'MULTIPLE_SELECTION_FEATURES':
                                    current_expr = widget.displayExpression() if hasattr(widget, 'displayExpression') else ""
                                    if current_expr == expr:
                                        logger.debug(f"_configure_groupbox_common: Skipping setDisplayExpression for {widget_key} - same expression")
                                        continue
                                if expr:
                                    try:
                                        # FIX 2026-01-19 v4: Always preserve checked for MULTIPLE_SELECTION
                                        if widget_key == 'MULTIPLE_SELECTION_FEATURES':
                                            widget.setDisplayExpression(expr, preserve_checked=True)
                                        else:
                                            widget.setDisplayExpression(expr)
                                    except Exception as e:
                                        logger.debug(f"Could not setDisplayExpression on {widget_key}: {e}")

                        # FIX 2026-01-16 v2: CRITICAL - ALWAYS set default field for expression widgets
                        # This fixes empty combobox when layer not in PROJECT_LAYERS
                        if widget_key in ('SINGLE_SELECTION_EXPRESSION', 'MULTIPLE_SELECTION_EXPRESSION', 'CUSTOM_SELECTION_EXPRESSION'):
                            expr_key = {
                                'SINGLE_SELECTION_EXPRESSION': 'single_selection_expression',
                                'MULTIPLE_SELECTION_EXPRESSION': 'multiple_selection_expression',
                                'CUSTOM_SELECTION_EXPRESSION': 'custom_selection_expression'
                            }.get(widget_key)
                            expr = layer_props.get("exploring", {}).get(expr_key, "") if layer_props else ""

                            # FIX 2026-01-16 v2: If no saved expression, ALWAYS fallback to first field
                            if not expr and self.current_layer:
                                fields = self.current_layer.fields()
                                if fields.count() > 0:
                                    expr = fields[0].name()
                                    logger.info(f"Using FIRST field '{expr}' for {widget_key} (layer not in PROJECT_LAYERS)")

                            if expr:
                                try:
                                    from qgis.core import QgsExpression
                                    if QgsExpression(expr).isField():
                                        widget.setField(expr)
                                        logger.info(f"✓ Set {widget_key} field to '{expr}'")
                                    else:
                                        widget.setExpression(expr)
                                        logger.info(f"✓ Set {widget_key} expression to '{expr}'")
                                except Exception as e:
                                    logger.error(f"Could not setField on {widget_key}: {e}")

                        # Special handling for single selection picker
                        if widget_key == 'SINGLE_SELECTION_FEATURES' and hasattr(widget, 'setAllowNull'):
                            widget.setAllowNull(True)
            except Exception as e:
                logger.error(f"_configure_groupbox_common: Fallback failed: {e}")

        return layer_props

    def _configure_single_selection_groupbox(self):
        """v4.0 Sprint 17: Configure single selection groupbox."""
        layer_props = self._configure_groupbox_common("single_selection")
        if layer_props is None: return True

        # FIX 2026-01-15 v5: CRITICAL - Reconnect featureChanged signal AFTER _configure_groupbox_common disconnected it!
        # before_migration pattern: direct connection of featureChanged signal to exploring_features_changed
        # This was missing in the migrated code, causing the feature picker to not update when feature changes.
        if "EXPLORING" in self.widgets and "SINGLE_SELECTION_FEATURES" in self.widgets["EXPLORING"]:
            picker_widget = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
            if picker_widget:
                # First try to disconnect any existing connection (ignore errors)
                try:
                    picker_widget.featureChanged.disconnect(self.exploring_features_changed)
                except TypeError:
                    pass  # Not connected
                # Now connect directly (same as before_migration line 7085)
                picker_widget.featureChanged.connect(self.exploring_features_changed)
                logger.debug("_configure_single_selection_groupbox: Connected featureChanged signal")

        # FIX 2026-01-15 v9: Ensure selectionChanged stays connected for IS_TRACKING/IS_SELECTING
        self._ensure_selection_changed_connected()

        # FIX 2026-01-18 v12: Don't connect multiple selection signals during QGIS sync
        # This prevents the updatingCheckedItemList signal from firing during sync
        if not self._syncing_from_qgis:
            self.manageSignal(["EXPLORING", "MULTIPLE_SELECTION_FEATURES"], 'connect', 'filteringCheckedItemList')
            self.manageSignal(["EXPLORING", "MULTIPLE_SELECTION_FEATURES"], 'connect', 'updatingCheckedItemList')

        # FIX 2026-01-18 v7: Don't call exploring_link_widgets during QGIS sync
        if not self._syncing_from_qgis:
            self.exploring_link_widgets()
            # FIX 2026-01-22: Prefer _last_single_selection_fid over widget.feature()
            # When layer has a filter (subsetString), widget.feature() may return wrong feature
            # if the actual selected feature is excluded by the filter
            f = None
            picker = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
            # First try to use saved FID from canvas selection (authoritative source)
            saved_fid = getattr(self, '_last_single_selection_fid', None)
            saved_layer_id = getattr(self, '_last_single_selection_layer_id', None)
            if saved_fid is not None and self.current_layer and saved_layer_id == self.current_layer.id():
                try:
                    f = self.current_layer.getFeature(saved_fid)
                    if not f or not f.isValid():
                        f = None
                        logger.debug(f"_configure_single_selection_groupbox: saved FID {saved_fid} not found, falling back to widget")
                except Exception as e:
                    logger.debug(f"Ignored in single selection feature retrieval for FID {saved_fid}: {e}")
                    f = None
            # Fallback to widget.feature() only if no saved FID
            if f is None:
                f = picker.feature()
            if f and f.isValid(): self.exploring_features_changed(f)

        self._update_exploring_buttons_state()
        # FIX 2026-01-15: Force visual refresh of single selection widget
        if "EXPLORING" in self.widgets and "SINGLE_SELECTION_FEATURES" in self.widgets["EXPLORING"]:
            widget = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
            if widget:
                widget.update()
                widget.repaint()
        return True

    def _configure_multiple_selection_groupbox(self):
        """v4.0 Sprint 17: Configure multiple selection groupbox."""
        layer_props = self._configure_groupbox_common("multiple_selection")
        if layer_props is None: return True

        # FIX 2026-01-15 v9: Ensure selectionChanged stays connected for IS_TRACKING/IS_SELECTING
        self._ensure_selection_changed_connected()

        # FIX 2026-01-18 v11: Don't connect signals during QGIS sync - they will be connected after
        # This prevents the signal from triggering exploring_features_changed immediately
        if not self._syncing_from_qgis:
            self.manageSignal(["EXPLORING", "MULTIPLE_SELECTION_FEATURES"], 'connect')

        # FIX 2026-01-18 v7: Don't call exploring_link_widgets during QGIS sync
        # exploring_link_widgets can trigger setDisplayExpression which clears the list,
        # causing checked items to disappear immediately after being set
        # FIX 2026-01-19: Also skip if we're being called from exploring_features_changed
        # to prevent feedback loop that clears the list
        if not self._syncing_from_qgis:
            self.exploring_link_widgets()
            # FIX 2026-01-19: Only call exploring_features_changed if NOT from a selection event
            # The call to currentSelectedFeatures() + exploring_features_changed() was causing
            # the list to be cleared because it triggered _configure_multiple_selection_groupbox again
            # Check if we're in a nested call by looking at stack or use a flag
            if not getattr(self, '_configuring_groupbox', False):
                self._configuring_groupbox = True
                try:
                    features = self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].currentSelectedFeatures()
                    if features:
                        self.exploring_features_changed(features, True)
                finally:
                    self._configuring_groupbox = False

        self._update_exploring_buttons_state()
        # FIX 2026-01-15: Force visual refresh of multiple selection widget
        if "EXPLORING" in self.widgets and "MULTIPLE_SELECTION_FEATURES" in self.widgets["EXPLORING"]:
            widget = self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"]
            if widget:
                widget.update()
                widget.repaint()
        return True

    def _configure_custom_selection_groupbox(self):
        """v4.0 Sprint 17: Configure custom selection groupbox."""
        layer_props = self._configure_groupbox_common("custom_selection")
        if layer_props is None: return True
        self.manageSignal(["EXPLORING", "CUSTOM_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
        self.manageSignal(["EXPLORING", "MULTIPLE_SELECTION_FEATURES"], 'connect', 'filteringCheckedItemList')
        self.manageSignal(["EXPLORING", "MULTIPLE_SELECTION_FEATURES"], 'connect', 'updatingCheckedItemList')
        self.exploring_link_widgets()
        custom_expr = layer_props["exploring"].get("custom_selection_expression", "")
        if custom_expr or not self.current_layer.subsetString(): self.exploring_custom_selection()
        self._update_exploring_buttons_state(); return True

    def exploring_groupbox_changed(self, groupbox):
        """v4.0 Sprint 18: Handle groupbox change with exclusive behavior."""
        if not self.widgets_initialized: return
        if self._controller_integration: self._controller_integration.delegate_exploring_set_groupbox_mode(groupbox)
        elif hasattr(self, '_exploring_cache') and self.current_layer:
            old = self.current_exploring_groupbox
            if old and old != groupbox: self._exploring_cache.invalidate(self.current_layer.id(), old)
        self._force_exploring_groupbox_exclusive(groupbox)
        {'single_selection': self._configure_single_selection_groupbox, 'multiple_selection': self._configure_multiple_selection_groupbox, 'custom_selection': self._configure_custom_selection_groupbox}.get(groupbox, lambda: None)()

    def exploring_identify_clicked(self):
        """
        v4.0 Sprint 18: Flash selected features on map.

        FIX 2026-01-15 v5: Complete rewrite based on before_migration pattern.
        Uses cache first for optimal performance, then fallback to widget retrieval.

        Key pattern from before_migration (lines 7312-7378):
        1. Check cache for feature_ids (fast path)
        2. Validate cache for custom_selection (expression match)
        3. Flash cached IDs if available
        4. Fallback: get features from widgets
        """
        logger.info("🔍 IDENTIFY button clicked!")
        if not self._is_layer_valid():
            logger.warning("IDENTIFY: Invalid layer")
            return

        try:
            from qgis.PyQt.QtGui import QColor

            layer_id = self.current_layer.id()
            groupbox_type = self.current_exploring_groupbox

            # OPTIMIZATION (from before_migration): Try cached feature_ids first
            if hasattr(self, '_exploring_cache') and groupbox_type:
                # For custom_selection, verify cached expression matches widget
                use_cached_ids = True
                if groupbox_type == "custom_selection":
                    cached = self._exploring_cache.get(layer_id, groupbox_type)
                    if cached:
                        current_widget_expr = self.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"].expression()
                        cached_expr = cached.get('expression', '')
                        if current_widget_expr != cached_expr:
                            logger.debug("IDENTIFY: CACHE STALE for custom_selection - invalidating")
                            self._exploring_cache.invalidate(layer_id, groupbox_type)
                            use_cached_ids = False

                if use_cached_ids:
                    feature_ids = self._exploring_cache.get_feature_ids(layer_id, groupbox_type)
                    if feature_ids and len(feature_ids) > 0:
                        logger.info(f"IDENTIFY: Using cached feature_ids ({len(feature_ids)} features)")
                        self.iface.mapCanvas().flashFeatureIds(
                            self.current_layer,
                            feature_ids,
                            startColor=QColor(235, 49, 42, 255),
                            endColor=QColor(237, 97, 62, 25),
                            flashes=6,
                            duration=400
                        )
                        return

            # Fallback: Get features from widgets (will also populate cache)
            features = []
            try:
                features, _ = self.get_current_features(use_cache=False)  # Force refresh
            except Exception as e:
                logger.debug(f"get_current_features failed: {e}")

            # Step 2: Fallback if no features from controller
            if not features:
                features, _ = self._fallback_get_current_features()

            logger.info(f"IDENTIFY: Got {len(features) if features else 0} features")

            # Step 3: Flash features if any
            if features and len(features) > 0:
                # FIX 2026-01-15: Validate geometry before flashing
                feature_ids = []
                for f in features:
                    if f and f.isValid():
                        if f.hasGeometry() and not f.geometry().isEmpty():
                            feature_ids.append(f.id())
                        else:
                            logger.warning(f"IDENTIFY: Feature {f.id()} has no geometry - skipping")

                if not feature_ids:
                    logger.error("IDENTIFY: No features with valid geometry to flash")
                    from qgis.utils import iface
                    iface.messageBar().pushWarning(
                        "FilterMate - Identify",
                        "Les features sélectionnées n'ont pas de géométrie."
                    )
                    return

                logger.info(f"IDENTIFY: Flashing {len(feature_ids)} features")
                self.iface.mapCanvas().flashFeatureIds(
                    self.current_layer,
                    feature_ids,
                    startColor=QColor(235, 49, 42, 255),
                    endColor=QColor(237, 97, 62, 25),
                    flashes=6,
                    duration=400
                )
                logger.info(f"IDENTIFY: ✓ Flashed {len(feature_ids)} features")
            else:
                logger.warning("IDENTIFY: No features to flash")
                from qgis.utils import iface
                iface.messageBar().pushWarning(
                    "FilterMate - Identify",
                    "Aucune feature sélectionnée. Sélectionnez une feature dans la liste déroulante."
                )
        except Exception as e:
            logger.error(f"exploring_identify_clicked error: {e}", exc_info=True)

    def get_current_features(self, use_cache: bool = True) -> tuple:
        """Get selected features based on active exploring groupbox.

        Retrieves features from the appropriate widget based on selection mode:
        - Single selection: From QgsFeaturePickerWidget
        - Multiple selection: From QgsCheckableComboBoxFeaturesListPickerWidget
        - Custom expression: From expression widget evaluation

        Args:
            use_cache: If True, use cached results when available.

        Returns:
            Tuple of (features_list, expression_string). Features is a list of
            feature values (IDs or display values), expression is the filter string.

        Note:
            Falls back to _fallback_get_current_features() if controller returns empty.
            Feature picker is the primary source for single_selection mode.
        """
        # DIAGNOSTIC 2026-01-16: ULTRA-DETAILED TRACE
        logger.info("=" * 80)
        logger.info("🔍 get_current_features() CALLED")
        logger.info("=" * 80)
        logger.info(f"   use_cache: {use_cache}")
        logger.info(f"   current_exploring_groupbox: {self.current_exploring_groupbox}")
        logger.info(f"   _controller_integration: {self._controller_integration is not None}")

        features, expression = [], ''

        # Try controller delegation first
        if self._controller_integration:
            try:
                logger.info("   → Calling _controller_integration.delegate_get_current_features()...")
                features, expression = self._controller_integration.delegate_get_current_features(use_cache)
                logger.info(f"   → Controller returned: {len(features)} features, expression='{expression}'")
            except Exception as e:
                logger.warning(f"   → Controller delegation FAILED: {e}")
        else:
            logger.warning("   → No _controller_integration available!")

        # FIX 2026-01-15: ALWAYS try fallback if controller returns empty
        # This ensures feature picker is used as primary source
        logger.info(f"   → features after controller: {len(features)}")
        if not features:
            logger.info("   → features EMPTY - calling _fallback_get_current_features()...")
            fallback_features, fallback_expr = self._fallback_get_current_features()
            logger.info(f"   → Fallback returned: {len(fallback_features)} features")
            if fallback_features:
                features = fallback_features
                if fallback_expr:
                    expression = fallback_expr
                logger.debug(f"get_current_features: Used fallback, got {len(features)} features")

        return features, expression

    def _fallback_get_current_features(self):
        """
        FIX 2026-01-15 v10: Fallback for get_current_features when controller unavailable.
        FIX 2026-01-18: Check for restored_task_features from favorite application.

        Pattern from before_migration (lines 7385-7480):
        - single_selection: get feature from QgsFeaturePickerWidget, ALWAYS reload to get geometry
        - multiple_selection: get checked items, ALWAYS fetch full features with geometry
        - custom_selection: delegate to exploring_custom_selection()
        - FAVORITE_RESTORE: use _restored_task_features if present (from favorite application)

        CRITICAL: The widget may return features WITHOUT geometry loaded.
        We MUST reload each feature from the layer to ensure geometry is available.

        User requirement: "si pas de selection QGIS, et single selection alors
        feature active est la feature active du feature picker single selection
        (meme si pushButton_checkable_exploring_selecting est unchecked)"

        FIX 2026-01-16: Use _is_layer_valid() for safe layer checking.
        """
        # Check if features were restored from favorite
        if hasattr(self, '_restored_task_features') and self._restored_task_features:
            features = self._restored_task_features
            logger.info(f"Using {len(features)} restored task_features from favorite")
            # Clear after use to avoid reusing in next filter
            self._restored_task_features = None
            return features, ''

        if not self._is_layer_valid():
            logger.warning("   🔴 _fallback_get_current_features: Layer is INVALID!")
            return [], ''
        try:
            from qgis.core import QgsFeatureRequest
            groupbox_type = self.current_exploring_groupbox
            logger.info("=" * 80)
            logger.info("🔍 _fallback_get_current_features CALLED")
            logger.info("=" * 80)
            logger.info(f"   groupbox_type: {groupbox_type}")
            logger.info(f"   current_layer: {self.current_layer.name() if self.current_layer else 'None'}")

            if groupbox_type == "single_selection":
                picker = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
                logger.info(f"   picker widget: {type(picker).__name__}")

                # FIX 2026-01-22: When is_selecting is active, check saved FID FIRST
                # picker.feature() may return wrong feature if layer has a filter (subsetString)
                # that excludes the actually selected feature from canvas
                is_selecting_active = self.pushButton_checkable_exploring_selecting.isChecked()
                saved_fid = getattr(self, '_last_single_selection_fid', None)
                saved_layer_id = getattr(self, '_last_single_selection_layer_id', None)

                # Strategy 0 (NEW): If is_selecting AND saved FID available for current layer, use it FIRST
                if is_selecting_active and saved_fid is not None and saved_layer_id == self.current_layer.id():
                    logger.info(f"   🎯 is_selecting active, using saved FID {saved_fid} as authoritative source")
                    try:
                        reloaded = self.current_layer.getFeature(saved_fid)
                        if reloaded.isValid():
                            if reloaded.hasGeometry() and not reloaded.geometry().isEmpty():
                                logger.info(f"  ✓ Using feature {saved_fid} from saved FID (with geometry)")
                                return [reloaded], ""
                            else:
                                logger.warning(f"  ⚠️ Feature {saved_fid} has NO geometry - flash/zoom will fail")
                                return [reloaded], ""
                    except Exception as e:
                        logger.warning(f"  ⚠️ Could not load saved FID {saved_fid}: {e}, falling back to picker")

                feature = picker.feature()
                logger.info(f"   picker.feature(): {feature}")
                logger.info(f"   feature.isValid(): {feature.isValid() if feature else 'N/A'}")
                logger.info(f"   feature.id(): {feature.id() if feature and feature.isValid() else 'N/A'}")

                # Strategy 1: Widget has a valid feature (PRIMARY SOURCE - user requirement)
                if feature and feature.isValid():
                    fid = feature.id()
                    logger.info(f"   ✅ Feature {fid} is VALID - proceeding to reload")
                    # Always save the FID for recovery
                    self._last_single_selection_fid = fid
                    self._last_single_selection_layer_id = self.current_layer.id()

                    # FIX 2026-01-15: ALWAYS reload from layer to get complete feature with geometry
                    # QgsFeaturePickerWidget may return features WITHOUT geometry loaded
                    try:
                        reloaded = self.current_layer.getFeature(fid)
                        if reloaded.isValid():
                            if reloaded.hasGeometry() and not reloaded.geometry().isEmpty():
                                logger.info(f"  ✓ Using feature {fid} from picker (with geometry)")
                                return [reloaded], ""
                            else:
                                # Feature exists but no geometry (e.g., non-spatial table)
                                logger.warning(f"  ⚠️ Feature {fid} has NO geometry - flash/zoom will fail")
                                # Still return it for attribute-based operations
                                return [reloaded], ""
                        else:
                            logger.error(f"  ❌ Feature {fid} from picker is INVALID after reload")
                            # Fall through to Strategy 2
                    except Exception as e:
                        logger.error(f"  ❌ Could not reload feature {fid}: {e}")
                        # Fall through to Strategy 2

                # Strategy 2: Try saved FID recovery
                if (hasattr(self, '_last_single_selection_fid')
                    and self._last_single_selection_fid is not None
                        and self.current_layer.id() == getattr(self, '_last_single_selection_layer_id', None)):
                    try:
                        recovered = self.current_layer.getFeature(self._last_single_selection_fid)
                        if recovered.isValid():
                            logger.info(f"  → Recovered feature {self._last_single_selection_fid} from saved FID")
                            return [recovered], ""
                    except Exception as e:
                        logger.debug(f"  → Recovery failed: {e}")

                # Strategy 3 (FIX v9): Try QGIS selection if is_selecting is active
                # This handles the case where user selected on canvas but picker wasn't updated
                if self.pushButton_checkable_exploring_selecting.isChecked():
                    selected_fids = self.current_layer.selectedFeatureIds()
                    if len(selected_fids) == 1:
                        try:
                            selected_feature = self.current_layer.getFeature(selected_fids[0])
                            if selected_feature.isValid():
                                logger.info(f"  → Using QGIS single selection {selected_fids[0]} (is_selecting active)")
                                return [selected_feature], ""
                        except Exception as e:
                            logger.debug(f"  → Could not get QGIS selection: {e}")

                logger.debug("  → No feature in single_selection picker")
                return [], ''

            elif groupbox_type == "multiple_selection":
                picker = self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"]
                feature_ids_to_fetch = []

                # DIAGNOSTIC 2026-01-28: Detailed multiple_selection debugging
                logger.info("  🔍 MULTIPLE_SELECTION DEBUG:")  # nosec B608 - false positive: logger statement, no SQL execution
                logger.info(f"     picker type: {type(picker).__name__}")
                logger.info(f"     picker.layer: {picker.layer.name() if picker.layer else 'None'}")
                if picker.layer:
                    logger.info(f"     picker.layer.id(): {picker.layer.id()}")
                    logger.info(f"     list_widgets keys: {list(picker.list_widgets.keys()) if hasattr(picker, 'list_widgets') else 'N/A'}")
                    if picker.layer.id() in picker.list_widgets:
                        lw = picker.list_widgets[picker.layer.id()]
                        logger.info(f"     list_widget count: {lw.count()}")
                        # Check how many checked items
                        checked_count = 0
                        for i in range(lw.count()):
                            item = lw.item(i)
                            if item and item.checkState() == Qt.Checked:
                                checked_count += 1
                        logger.info(f"     checked items count: {checked_count}")
                    else:
                        logger.warning("     ⚠️ layer.id() NOT in list_widgets!")

                # FIX v10: Use multiple strategies to get checked feature IDs
                # Strategy 1: Try checkedItemsData first (returns FIDs directly)
                if hasattr(picker, 'checkedItemsData'):
                    checked = picker.checkedItemsData()
                    if checked:
                        feature_ids_to_fetch = list(checked)
                        logger.info(f"  → Got {len(feature_ids_to_fetch)} FIDs from checkedItemsData")

                # Strategy 2: Fallback to checkedItems (returns [display, pk, ...] tuples)
                if not feature_ids_to_fetch and hasattr(picker, 'checkedItems'):
                    items = picker.checkedItems()
                    logger.info(f"  → checkedItems() returned: {len(items) if items else 0} items")
                    if items:
                        logger.info(f"     First item sample: {items[0] if items else 'N/A'}")
                        # Extract PK values (index 1) from items
                        for item in items:
                            if isinstance(item, (list, tuple)) and len(item) > 1:
                                feature_ids_to_fetch.append(item[1])
                        logger.info(f"  → Got {len(feature_ids_to_fetch)} PKs from checkedItems")

                # Strategy 3: Try saved FIDs from _last_multiple_selection_fids
                if not feature_ids_to_fetch:
                    if (hasattr(self, '_last_multiple_selection_fids')
                        and self._last_multiple_selection_fids
                            and self.current_layer.id() == getattr(self, '_last_multiple_selection_layer_id', None)):
                        feature_ids_to_fetch = self._last_multiple_selection_fids
                        logger.info(f"  → Recovered {len(feature_ids_to_fetch)} FIDs from saved state")

                # Now fetch features WITH geometry
                if feature_ids_to_fetch:
                    try:
                        request = QgsFeatureRequest().setFilterFids(feature_ids_to_fetch)
                        features = list(self.current_layer.getFeatures(request))
                        if features:
                            logger.debug(f"  → Got {len(features)} features from multiple selection")
                            return features, ""
                    except Exception as e:
                        logger.debug(f"  → setFilterFids failed: {e}, trying expression")

                    # Fallback: Build expression if setFilterFids didn't work (PK might not be FID)
                    try:
                        layer_props = self.PROJECT_LAYERS.get(self.current_layer.id(), {})
                        pk_name = layer_props.get("infos", {}).get("primary_key_name")
                        pk_is_numeric = layer_props.get("infos", {}).get("primary_key_is_numeric", True)

                        if pk_name and feature_ids_to_fetch:
                            if pk_is_numeric:
                                expr_str = f'"{pk_name}" IN ({",".join(str(v) for v in feature_ids_to_fetch)})'
                            else:
                                # Fix: Use proper string quoting for non-numeric primary keys
                                quoted_values = ",".join(f"'{v}'" for v in feature_ids_to_fetch)
                                expr_str = f'"{pk_name}" IN ({quoted_values})'
                            request = QgsFeatureRequest(QgsExpression(expr_str))
                            features = list(self.current_layer.getFeatures(request))
                            if features:
                                logger.debug(f"  → Got {len(features)} features via expression")
                                return features, ""
                    except Exception as e:
                        logger.debug(f"  → Expression fallback failed: {e}")

                # Last resort: Try QGIS canvas selection (allowed for multiple_selection)
                qgis_selected = self.current_layer.selectedFeatures()
                if len(qgis_selected) > 0:
                    logger.info(f"  → Using QGIS canvas selection ({len(qgis_selected)} features)")
                    return qgis_selected, ""

            elif groupbox_type == "custom_selection":
                return self.exploring_custom_selection()

        except Exception as e:
            logger.debug(f"_fallback_get_current_features error: {e}")
        return [], ''

    def exploring_zoom_clicked(self, features=[], expression=None):
        """
        v4.0 Sprint 18: Zoom to selected features.

        FIX 2026-01-15 v5: Complete rewrite based on before_migration pattern.
        Uses cached bbox for instant zoom when available.

        Key pattern from before_migration (lines 7625-7640):
        1. Check cache for bbox (instant zoom path)
        2. Validate cache for custom_selection
        3. Apply padding and CRS transform
        4. Fallback: get features and zoom
        """
        logger.info("🔎 ZOOM button clicked!")
        if not self._is_layer_valid():
            logger.warning("ZOOM: Invalid layer")
            return

        layer_id = self.current_layer.id()
        groupbox_type = self.current_exploring_groupbox

        # OPTIMIZATION (from before_migration): Try cached bbox for instant zoom
        if hasattr(self, '_exploring_cache') and groupbox_type and not features:
            # Validate cache for custom_selection
            use_cached_bbox = True
            if groupbox_type == "custom_selection":
                cached = self._exploring_cache.get(layer_id, groupbox_type)
                if cached:
                    current_widget_expr = self.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"].expression()
                    cached_expr = cached.get('expression', '')
                    if current_widget_expr != cached_expr:
                        logger.debug("ZOOM: CACHE STALE for custom_selection - invalidating")
                        self._exploring_cache.invalidate(layer_id, groupbox_type)
                        use_cached_bbox = False

            if use_cached_bbox:
                cached_bbox = self._exploring_cache.get_bbox(layer_id, groupbox_type)
                if cached_bbox and not cached_bbox.isEmpty():
                    logger.info("ZOOM: Using cached bbox for instant zoom")
                    try:
                        from qgis.core import QgsRectangle, QgsCoordinateTransform, QgsProject
                        # Apply padding (10% or minimum 5 units)
                        width_padding = max(cached_bbox.width() * 0.1, 5)
                        height_padding = max(cached_bbox.height() * 0.1, 5)
                        padded_bbox = QgsRectangle(cached_bbox)
                        padded_bbox.grow(max(width_padding, height_padding))

                        # Transform to canvas CRS if needed
                        layer_crs = self.current_layer.crs()
                        canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
                        if layer_crs != canvas_crs:
                            transform = QgsCoordinateTransform(layer_crs, canvas_crs, QgsProject.instance())
                            padded_bbox = transform.transformBoundingBox(padded_bbox)

                        self.iface.mapCanvas().zoomToFeatureExtent(padded_bbox)
                        self.iface.mapCanvas().refresh()
                        return
                    except Exception as e:
                        logger.debug(f"ZOOM: Cache bbox failed: {e}")

        # Step 1: Get features if not provided
        if not features:
            try:
                features, expression = self.get_current_features(use_cache=False)  # Force refresh
            except Exception as e:
                logger.debug(f"get_current_features failed: {e}")

            # Fallback if controller fails
            if not features:
                features, expression = self._fallback_get_current_features()

        logger.info(f"ZOOM: Got {len(features) if features else 0} features")

        # Step 2: Zoom to features
        if features and len(features) > 0:
            self.zooming_to_features(features, expression)
        else:
            logger.warning("ZOOM: No features to zoom to")

    def get_filtered_layer_extent(self, layer):
        """v3.1 Sprint 17: Calculate bounding box of filtered features with performance limit."""
        if not layer: return None
        try:
            MAX_FEATURES = 10000
            layer.updateExtents()
            if layer.featureCount() > MAX_FEATURES: return layer.extent()

            extent, count = QgsRectangle(), 0
            for f in layer.getFeatures(QgsFeatureRequest().setNoAttributes()):
                if f.hasGeometry() and not f.geometry().isEmpty():
                    extent = f.geometry().boundingBox() if extent.isEmpty() else extent.combineExtentWith(f.geometry().boundingBox()) or extent
                    count += 1
                    if count >= MAX_FEATURES: break
            return layer.extent() if extent.isEmpty() else extent
        except (RuntimeError, AttributeError, TypeError):
            return layer.extent()  # Fallback to layer extent on error

    def _compute_zoom_extent_for_mode(self):
        """v4.0 Sprint 18: Compute zoom extent - delegates to ExploringController."""
        return self._exploring_ctrl._compute_zoom_extent_for_mode() if self._exploring_ctrl else self.get_filtered_layer_extent(self.current_layer) if self.current_layer else None

    def zooming_to_features(self, features, expression=None):
        """
        v4.0 Sprint 18: Zoom to features.

        FIX 2026-01-15 v4: Enhanced fallback with geometry validation.
        """
        if not self._is_layer_valid():
            return

        if not features or len(features) == 0:
            logger.warning("zooming_to_features: No features provided")
            return

        # Try controller first
        if self._exploring_ctrl:
            try:
                self._exploring_ctrl.zooming_to_features(features, expression)
                return
            except Exception as e:
                logger.debug(f"Controller zooming_to_features failed: {e}")

        # FIX v4: Enhanced fallback with geometry validation and reload
        try:
            feature_ids = []
            for f in features:
                if f and hasattr(f, 'id'):
                    # Reload feature if no geometry
                    if not f.hasGeometry() or f.geometry().isEmpty():
                        try:
                            reloaded = self.current_layer.getFeature(f.id())
                            if reloaded.isValid() and reloaded.hasGeometry():
                                feature_ids.append(reloaded.id())
                                continue
                        except (RuntimeError, KeyError, AttributeError):
                            pass  # Feature reload failed - use original
                    feature_ids.append(f.id())

            if feature_ids:
                self.iface.mapCanvas().zoomToFeatureIds(self.current_layer, feature_ids)
                self.iface.mapCanvas().refresh()
                logger.info(f"zooming_to_features: Zoomed to {len(feature_ids)} features")
            else:
                logger.warning("zooming_to_features: No valid feature IDs")
        except Exception as e:
            logger.warning(f"zooming_to_features fallback error: {e}")

    def _ensure_selection_changed_connected(self):
        """
        FIX 2026-01-15 v9: Ensure the selectionChanged signal is connected to on_layer_selection_changed.

        FIX 2026-02-10 (C1): Now delegates to _connect_selection_signal for centralized management.
        This is called when IS_TRACKING or IS_SELECTING are activated to ensure
        the signal remains connected for auto-zoom/sync functionality.
        """
        self._connect_selection_signal()

    def on_layer_selection_changed(self, selected, deselected, clearAndSelect):
        """
        v4.0 Sprint 18: Handle layer selection change - delegates to ExploringController.

        FIX 2026-01-15 v5: Ensure selectionChanged signal stays connected for IS_TRACKING.
        The signal can be disconnected during layer changes and not always reconnected,
        causing tracking to only work for the first feature change.
        """
        # FIX v10: DEBUG - Confirm signal is triggered
        logger.info(f"🔔 on_layer_selection_changed TRIGGERED: selected={len(selected)}, deselected={len(deselected)}, clearAndSelect={clearAndSelect}")

        # FIX 2026-02-10 (C1): Self-healing removed - centralized in _connect_selection_signal
        # The signal is already connected if this handler was invoked.
        if self.current_layer and not self.current_layer_selection_connection:
            self.current_layer_selection_connection = True

        # FIX v10: DEBUG - Check delegation
        if self._controller_integration:
            logger.info("🔀 Delegating to ExploringController.handle_layer_selection_changed")
            if self._controller_integration.delegate_handle_layer_selection_changed(selected, deselected, clearAndSelect):
                logger.info("✅ Controller handled selection change")
                return
            else:
                logger.warning("⚠️ Controller delegation returned False")
        else:
            logger.warning("⚠️ No controller integration available")

        # FIX 2026-01-14: Fallback when controller not available
        logger.info("🔧 Using fallback handler")
        self._fallback_handle_layer_selection_changed()

    def _fallback_handle_layer_selection_changed(self):
        """FIX 2026-01-15 v4: Fallback for on_layer_selection_changed when controller unavailable.
        FIX 2026-01-16: Use _is_layer_valid() for safe layer checking.
        """
        try:
            if getattr(self, '_syncing_from_qgis', False):
                return
            if not self._is_layer_valid():
                return
            layer_props = self.PROJECT_LAYERS.get(self.current_layer.id())
            if not layer_props:
                return

            is_selecting = layer_props.get("exploring", {}).get("is_selecting", False)
            is_tracking = layer_props.get("exploring", {}).get("is_tracking", False)

            # FIX v4: Check actual button states and trust them over PROJECT_LAYERS
            btn_selecting = self.pushButton_checkable_exploring_selecting
            btn_tracking = self.pushButton_checkable_exploring_tracking
            selecting_button_checked = btn_selecting.isChecked()
            tracking_button_checked = btn_tracking.isChecked()

            # Correct mismatch for is_selecting
            if selecting_button_checked != is_selecting:
                logger.warning(f"Fallback: IS_SELECTING mismatch! Button={selecting_button_checked}, stored={is_selecting}")  # nosec B608 - false positive: logger statement, no SQL execution
                layer_id = self.current_layer.id()
                if layer_id in self.PROJECT_LAYERS:
                    self.PROJECT_LAYERS[layer_id]["exploring"]["is_selecting"] = selecting_button_checked
                    is_selecting = selecting_button_checked
                    logger.info(f"Fallback: Corrected is_selecting to {selecting_button_checked}")

            # FIX v4: Correct mismatch for is_tracking
            if tracking_button_checked != is_tracking:
                logger.warning(f"Fallback: IS_TRACKING mismatch! Button={tracking_button_checked}, stored={is_tracking}")
                layer_id = self.current_layer.id()
                if layer_id in self.PROJECT_LAYERS:
                    self.PROJECT_LAYERS[layer_id]["exploring"]["is_tracking"] = tracking_button_checked
                    is_tracking = tracking_button_checked
                    logger.info(f"Fallback: Corrected is_tracking to {tracking_button_checked}")

            # Sync widgets when button is checked OR is_selecting is active
            should_sync = selecting_button_checked or is_selecting
            if should_sync:
                logger.info("Fallback: Syncing widgets from QGIS selection")
                self._fallback_sync_widgets_from_qgis_selection()
            else:
                logger.debug(f"Fallback: Skipping sync (button={selecting_button_checked}, is_selecting={is_selecting})")

            # FIX v4: Zoom to selection when tracking is active (trust button state)
            if is_tracking or tracking_button_checked:
                from qgis.core import QgsFeatureRequest
                selected_ids = self.current_layer.selectedFeatureIds()
                if len(selected_ids) > 0:
                    request = QgsFeatureRequest().setFilterFids(selected_ids)
                    features = list(self.current_layer.getFeatures(request))
                    logger.info(f"Fallback: TRACKING zoom to {len(features)} features")
                    self.zooming_to_features(features)
        except Exception as e:
            logger.debug(f"_fallback_handle_layer_selection_changed error: {e}")

    def _fallback_sync_widgets_from_qgis_selection(self):
        """FIX 2026-01-14: Fallback for _sync_widgets_from_qgis_selection."""
        try:
            if not self.current_layer or not self.widgets_initialized:
                return

            selected_features = self.current_layer.selectedFeatures()
            selected_count = len(selected_features)
            current_groupbox = self.current_exploring_groupbox

            # Auto-switch groupbox based on selection count (v2.5.11+)
            # FIX 2026-01-18: Only auto-switch from single to multiple, NOT the reverse
            # User should stay on multiple_selection even with 1 feature selected
            if selected_count > 1 and current_groupbox == "single_selection":
                logger.info(f"Fallback: Auto-switching to multiple_selection ({selected_count} features)")
                self._syncing_from_qgis = True
                try:
                    self._force_exploring_groupbox_exclusive("multiple_selection")
                    self._configure_multiple_selection_groupbox()
                finally:
                    self._syncing_from_qgis = False
            elif current_groupbox == "multiple_selection":
                # FIX 2026-01-18: Stay on multiple_selection, just configure it
                logger.info(f"Fallback: Staying on multiple_selection ({selected_count} features)")
                self._syncing_from_qgis = True
                try:
                    self._configure_multiple_selection_groupbox()
                finally:
                    self._syncing_from_qgis = False

            # FIX 2026-01-15: Update button states before syncing widgets
            # This ensures buttons are enabled ASAP when there's a selection
            if selected_count > 0:
                logger.debug(f"_fallback_sync: Pre-updating button states (selection={selected_count})")
                self._update_exploring_buttons_state()

            # Sync single selection widget
            if selected_count >= 1:
                feature_picker = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
                current_feature = feature_picker.feature()
                feature_id = selected_features[0].id()
                if not (current_feature and current_feature.isValid() and current_feature.id() == feature_id):
                    self._syncing_from_qgis = True
                    try:
                        feature_picker.setFeature(feature_id)
                        # FIX 2026-01-22: Save FID for recovery (same as in _sync_single_selection_from_qgis)
                        self._last_single_selection_fid = feature_id
                        self._last_single_selection_layer_id = self.current_layer.id()
                        # FIX 2026-01-15: Force visual refresh
                        feature_picker.update()
                        feature_picker.repaint()
                    finally:
                        self._syncing_from_qgis = False

            # FIX 2026-01-15 v3: Sync multiple selection widget
            if selected_count >= 1:
                try:
                    multi_widget = self.widgets.get("EXPLORING", {}).get("MULTIPLE_SELECTION_FEATURES", {}).get("WIDGET")
                    if multi_widget and hasattr(multi_widget, 'list_widgets'):
                        layer_id = self.current_layer.id()
                        if layer_id in multi_widget.list_widgets:
                            list_widget = multi_widget.list_widgets[layer_id]
                            layer_props = self.PROJECT_LAYERS.get(layer_id, {})
                            pk_name = layer_props.get("infos", {}).get("primary_key_name")

                            # Get selected PK values from QGIS selection
                            selected_pk_values = set()
                            for f in selected_features:
                                try:
                                    pk_value = f[pk_name] if pk_name else f.id()
                                    selected_pk_values.add(str(pk_value) if pk_value is not None else str(f.id()))
                                except (KeyError, TypeError, AttributeError):
                                    selected_pk_values.add(str(f.id()))  # Fallback to FID

                            # Sync check states in list widget
                            self._syncing_from_qgis = True
                            try:
                                from qgis.PyQt.QtCore import Qt
                                for i in range(list_widget.count()):
                                    item = list_widget.item(i)
                                    item_pk = str(item.data(3)) if item.data(3) is not None else ""
                                    should_check = item_pk in selected_pk_values
                                    current_state = item.checkState() == Qt.Checked
                                    if should_check != current_state:
                                        item.setCheckState(Qt.Checked if should_check else Qt.Unchecked)
                                logger.debug(f"_fallback_sync: Synced {len(selected_pk_values)} items in multiple picker")
                            finally:
                                self._syncing_from_qgis = False
                except Exception as e:
                    logger.debug(f"_fallback_sync: Error syncing multiple picker: {e}")

            # FIX 2026-01-15: Force button state update after sync
            # This ensures IDENTIFY and ZOOM buttons are enabled after successful sync
            if selected_count > 0:
                logger.debug("_fallback_sync: Post-updating button states after sync")
                self._update_exploring_buttons_state()

        except Exception as e:
            logger.debug(f"_fallback_sync_widgets_from_qgis_selection error: {e}")

    def _sync_widgets_from_qgis_selection(self):
        """v4.0 Sprint 18: Sync widgets with QGIS selection - delegates to ExploringController."""
        if self._exploring_ctrl: self._exploring_ctrl._sync_widgets_from_qgis_selection()

    def _sync_single_selection_from_qgis(self, selected_features, selected_count):
        """v4.0 Sprint 18: Sync single selection - delegates to ExploringController."""
        if self._exploring_ctrl: self._exploring_ctrl._sync_single_selection_from_qgis(selected_features, selected_count)

    def _sync_multiple_selection_from_qgis(self, selected_features, selected_count):
        """v4.0 Sprint 18: Sync multiple selection - delegates to UILayoutController."""
        if not (hasattr(self, '_controller_integration') and self._controller_integration and self._controller_integration.delegate_sync_multiple_selection_from_qgis()):
            logger.warning("_sync_multiple_selection_from_qgis: Controller delegation failed")

    def exploring_source_params_changed(self, expression=None, groupbox_override=None, change_source=None):
        """v4.0 S18: → ExploringController."""
        if self._exploring_ctrl: self._exploring_ctrl.exploring_source_params_changed(expression, groupbox_override, change_source)

    def exploring_custom_selection(self):
        """
        v4.0 S18: Get features matching custom expression.

        FIX 2026-01-21: Load features directly instead of going through
        exploring_features_changed which has guards that can block feature retrieval
        (e.g., _syncing_from_qgis, _configuring_groupbox, sync_protection_until).

        FIX 2026-01-22: Use is_filter_expression() to properly detect non-filter expressions
        like field names, COALESCE, CONCAT, etc. These should not be used as filters.

        This ensures custom_selection always returns the features matching the expression
        for use in source layer filtering.
        """
        if not self.widgets_initialized or not self.current_layer or self.current_layer.id() not in self.PROJECT_LAYERS:
            return [], ''

        expression = self.PROJECT_LAYERS[self.current_layer.id()]["exploring"].get("custom_selection_expression", "")
        if not expression:
            return [], expression

        # FIX 2026-01-22: Use centralized filter expression detection
        # Expressions that don't return boolean values (field names, COALESCE, CONCAT, etc.)
        # should not be used as filters - they would cause SQL errors
        from .infrastructure.utils import should_skip_expression_for_filtering

        should_skip, reason = should_skip_expression_for_filtering(expression)
        if should_skip:
            logger.debug(f"exploring_custom_selection: Skipping non-filter expression - {reason}")
            logger.debug(f"  Expression: '{expression}'")
            return [], expression

        # Check cache first
        layer_id = self.current_layer.id()
        cached = self._get_cached_expression_result(layer_id, expression)
        if cached is not None:
            logger.debug(f"exploring_custom_selection: Cache HIT - {len(cached)} features")
            return cached, expression

        # FIX 2026-01-21: Load features DIRECTLY instead of via exploring_features_changed
        # This bypasses the guards that can prevent features from being returned
        features = []
        try:
            from qgis.core import QgsFeatureRequest
            request = QgsFeatureRequest().setFilterExpression(expression)
            features = list(self.current_layer.getFeatures(request))
            logger.info(f"exploring_custom_selection: Loaded {len(features)} features matching expression '{expression[:50]}...'")
        except Exception as e:
            logger.error(f"exploring_custom_selection: Error loading features: {e}")

        # Cache the result
        if features:
            self._set_cached_expression_result(layer_id, expression, features)

        return features, expression

    def exploring_deselect_features(self):
        """
        v4.0 Sprint 18: Deselect all features and switch to pan tool.

        FIX 2026-01-15: Switch to pan tool when IS_SELECTING is unchecked.
        """
        if not self._is_layer_valid():
            return

        # Clear selection
        if not (self._controller_integration and self._controller_integration.delegate_exploring_clear_selection()):
            self.current_layer.removeSelection()

        # FIX 2026-01-15: Switch to pan tool when deselecting
        try:
            self.iface.actionPan().trigger()
            logger.info("exploring_deselect_features: Switched to pan tool")
        except Exception as e:
            logger.warning(f"exploring_deselect_features: Failed to activate pan tool: {e}")

        # Disable the active groupbox when IS_SELECTING is inactive
        self._sync_groupbox_state_with_selecting(False)

    def exploring_select_features(self):
        """
        v4.0 Sprint 18: Activate QGIS selection tool and select features from active groupbox.

        FIX 2026-01-15:
        - Activate selection tool on canvas
        - Synchronize canvas selection with current groupbox features
        - Enable the active groupbox for interaction
        - Update button states after selection
        """
        if not self._is_layer_valid():
            return

        logger.info(f"🔍 exploring_select_features: START (groupbox={self.current_exploring_groupbox})")

        # STEP 1: ALWAYS activate QGIS selection tool on canvas (CRITICAL)
        # This must happen FIRST and ALWAYS, regardless of controller delegation
        try:
            self.iface.actionSelectRectangle().trigger()
            self.iface.setActiveLayer(self.current_layer)
            logger.info(f"exploring_select_features: ✓ Selection tool activated for '{self.current_layer.name()}'")
        except Exception as e:
            logger.warning(f"exploring_select_features: ✗ Failed to activate selection tool: {e}")

        # STEP 2: Get features from active groupbox and select them on the layer
        features, _ = self.get_current_features()
        logger.info(f"exploring_select_features: Got {len(features) if features else 0} features from groupbox")

        if features:
            try:
                self.current_layer.removeSelection()
                self.current_layer.select([f.id() for f in features])
                logger.info(f"exploring_select_features: ✓ Selected {len(features)} features on canvas")
            except Exception as e:
                logger.warning(f"exploring_select_features: ✗ Failed to select features: {e}")

        # STEP 3: Enable the active groupbox for interaction
        # FIX 2026-01-15: Make sure groupbox is enabled when IS_SELECTING is active
        self._sync_groupbox_state_with_selecting(True)

        # STEP 4: Force update button states
        # FIX 2026-01-15: Ensure IDENTIFY and ZOOM buttons are enabled after selection
        self._update_exploring_buttons_state()
        logger.info("exploring_select_features: DONE")

    def _sync_groupbox_state_with_selecting(self, is_selecting: bool):
        """
        FIX 2026-01-15: Synchronize groupbox enabled state with IS_SELECTING button.

        When IS_SELECTING is active, enable the current groupbox for interaction.
        When inactive, the groupbox state depends on other conditions.

        Args:
            is_selecting: True if IS_SELECTING button is checked, False otherwise
        """
        if not self.widgets_initialized or not self.current_exploring_groupbox:
            return

        try:
            # Get the active groupbox widget
            groupbox_map = {
                "single_selection": self.mGroupBox_exploring_single_selection,
                "multiple_selection": self.mGroupBox_exploring_multiple_selection,
                "custom_selection": self.mGroupBox_exploring_custom_selection
            }

            current_groupbox_widget = groupbox_map.get(self.current_exploring_groupbox)
            if current_groupbox_widget:
                # Enable groupbox when selecting is active
                current_groupbox_widget.setEnabled(True)
                logger.debug(f"_sync_groupbox_state_with_selecting: {self.current_exploring_groupbox} enabled={is_selecting}")
        except Exception as e:
            logger.debug(f"_sync_groupbox_state_with_selecting error: {e}")

    def exploring_features_changed(self, input=[], identify_by_primary_key_name=False, custom_expression=None, preserve_filter_if_empty=False):
        """
        WRAPPER: Delegates to ExploringController.

        Handle feature selection changes in exploration widgets.
        Migrated to ExploringController in v4.0 Sprint 2.
        """
        if self._exploring_ctrl: return self._exploring_ctrl.exploring_features_changed(input, identify_by_primary_key_name, custom_expression, preserve_filter_if_empty)
        return []

    def _handle_exploring_features_result(
        self,
        features,
        expression,
        layer_props,
        identify_by_primary_key_name=False
    ):
        """v4.0 S18: → ExploringController."""
        if self._exploring_ctrl: return self._exploring_ctrl.handle_exploring_features_result(features, expression, layer_props, identify_by_primary_key_name)
        return []

    def get_exploring_features(self, input, identify_by_primary_key_name=False, custom_expression=None):
        """v4.0 S18: → ExploringController."""
        if self._exploring_ctrl: return self._exploring_ctrl.get_exploring_features(input, identify_by_primary_key_name, custom_expression)
        return [], None

    def get_exploring_features_async(self, expression: str, on_complete=None, on_error=None, on_progress=None):
        """v3.1 Sprint 16: Async expression evaluation for large layers."""
        if not ASYNC_EXPRESSION_AVAILABLE or self._expression_manager is None:
            if on_error: on_error("Async evaluation not available", "")
            return None
        if not self.current_layer or not self.current_layer.isValid() or not expression:
            if on_error: on_error("Invalid layer or expression", self.current_layer.id() if self.current_layer else "")
            return None

        self._set_expression_loading_state(True)
        self.current_layer.id()

        def wrap_complete(features, expr, lid):
            self._set_expression_loading_state(False)
            self._pending_async_evaluation = None
            if features and expr: self._set_cached_expression_result(lid, expr, features)
            if on_complete: on_complete(features, expr, lid)

        def wrap_error(msg, lid):
            self._set_expression_loading_state(False)
            self._pending_async_evaluation = None
            if on_error: on_error(msg, lid)

        def wrap_cancel(lid):
            self._set_expression_loading_state(False)
            self._pending_async_evaluation = None

        task = self._expression_manager.evaluate(
            layer=self.current_layer, expression=expression, on_complete=wrap_complete,
            on_error=wrap_error, on_progress=on_progress, on_cancelled=wrap_cancel,
            cancel_existing=True, description=f"FilterMate: Evaluating on {self.current_layer.name()}")
        if task: self._pending_async_evaluation = task
        return task

    def cancel_async_expression_evaluation(self):
        """v4.0 S18: Cancel pending async expression evaluation."""
        if self._pending_async_evaluation: self._pending_async_evaluation.cancel(); self._pending_async_evaluation = None; self._set_expression_loading_state(False)
        if self._expression_manager and self.current_layer: self._expression_manager.cancel(self.current_layer.id())

    def should_use_async_expression(self, custom_expression: str = None) -> bool:
        """v4.0 S18: Check if async expression evaluation should be used."""
        if not ASYNC_EXPRESSION_AVAILABLE or not self._expression_manager or not self.current_layer or not custom_expression:
            return False
        return self.current_layer.featureCount() > self._async_expression_threshold

    def exploring_link_widgets(self, expression=None, change_source=None):
        """v4.0 S18: → ExploringController."""
        if self._exploring_ctrl: self._exploring_ctrl.exploring_link_widgets(expression, change_source)

    def get_layers_to_filter(self) -> list:
        """Get list of layer IDs selected for geometric filtering.

        Retrieves all checked layers from the filtering combobox widget.
        These are the "distant layers" that will be filtered based on their
        spatial relationship with the source layer.

        Returns:
            List of layer ID strings for checked layers, or empty list if
            widgets not initialized.

        Note:
            Also updates controller state via delegate_filtering_set_target_layer_ids().
        """
        if not self.widgets_initialized: return []
        checked = []
        w = self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"]
        for i in range(w.count()):
            if w.itemCheckState(i) == Qt.Checked:
                d = w.itemData(i, Qt.UserRole)
                checked.append(d["layer_id"] if isinstance(d, dict) and "layer_id" in d else d if isinstance(d, str) else None)
        checked = [c for c in checked if c]
        if self._controller_integration: self._controller_integration.delegate_filtering_set_target_layer_ids(checked)
        return checked

    def get_layers_to_export(self) -> list:
        """Get list of layer IDs selected for export.

        Retrieves all checked layers from the exporting combobox widget.
        These layers will be exported in the selected format.

        Returns:
            List of layer ID strings for checked layers, or None if widgets
            not initialized.

        Note:
            Handles both string and dict data formats from itemData().
        """
        if not self.widgets_initialized:
            return None

        w = self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"]
        checked = []

        for i in range(w.count()):
            if w.itemCheckState(i) == Qt.Checked:
                d = w.itemData(i, Qt.UserRole)

                # FIX 2026-01-22: Handle both dict and string data formats
                if isinstance(d, dict) and 'layer_id' in d:
                    # New format: data is a dict with 'layer_id' key
                    checked.append(d['layer_id'])
                elif isinstance(d, str):
                    # Old format: data is directly the layer_id string
                    checked.append(d)

        if self._controller_integration:
            self._controller_integration.delegate_export_set_layers_to_export(checked)

        return checked

    def get_current_crs_authid(self):
        """v4.0 S18: Get current export CRS."""
        return self.widgets["EXPORTING"]["PROJECTION_TO_EXPORT"]["WIDGET"].crs().authid() if self.widgets_initialized and self.has_loaded_layers else None

    def _validate_and_prepare_layer(self, layer):
        """Validate and prepare layer for change. Returns: (should_continue, layer, layer_props)"""
        if self._plugin_busy or not self.PROJECT_LAYERS or not self.widgets_initialized: return (False, None, None)
        if layer is None or not isinstance(layer, QgsVectorLayer): return (False, None, None)
        try: _ = layer.id()
        except RuntimeError: return (False, None, None)
        try:
            if not is_layer_source_available(layer):
                show_warning("FilterMate", "The selected layer is invalid or its source cannot be found.")
                return (False, None, None)
        except (RuntimeError, AttributeError, OSError):
            return (False, None, None)  # Layer source check failed
        # FIX 2026-02-10 (C1): Centralized selectionChanged disconnection
        if self.current_layer is not None and self.current_layer_selection_connection is not None:
            self._disconnect_selection_signal()

        self.current_layer = layer

        if self.current_layer.id() not in self.PROJECT_LAYERS:
            return (False, None, None)

        self.currentLayerChanged.emit()
        return (True, layer, self.PROJECT_LAYERS[self.current_layer.id()])

    def _reset_layer_expressions(self, layer_props):
        """v4.0 S18: → ExploringController."""
        if self._exploring_ctrl: self._controller_integration.delegate_reset_layer_expressions(layer_props)

    def _disconnect_layer_signals(self):
        """v3.1 Sprint 17: Disconnect all layer-related widget signals before updating.

        FIX 2026-01-15 (BUGFIX-COMBOBOX-20260115): CURRENT_LAYER signal NOT disconnected.
        Reason: User can change layer during update. Lock _updating_current_layer prevents reentrancy.
        """
        exploring = ["SINGLE_SELECTION_FEATURES", "SINGLE_SELECTION_EXPRESSION", "MULTIPLE_SELECTION_FEATURES", "MULTIPLE_SELECTION_EXPRESSION", "CUSTOM_SELECTION_EXPRESSION", "IDENTIFY", "ZOOM", "IS_SELECTING", "IS_TRACKING", "IS_LINKING", "RESET_ALL_LAYER_PROPERTIES"]
        # FIX 2026-01-15: CURRENT_LAYER removed - must stay connected for user interaction
        filtering = ["HAS_LAYERS_TO_FILTER", "LAYERS_TO_FILTER", "HAS_COMBINE_OPERATOR", "SOURCE_LAYER_COMBINE_OPERATOR", "OTHER_LAYERS_COMBINE_OPERATOR", "HAS_GEOMETRIC_PREDICATES", "GEOMETRIC_PREDICATES", "HAS_BUFFER_VALUE", "BUFFER_VALUE", "BUFFER_VALUE_PROPERTY", "HAS_BUFFER_TYPE", "BUFFER_TYPE"]
        widgets_to_stop = [["EXPLORING", w] for w in exploring] + [["FILTERING", w] for w in filtering]

        for wp in widgets_to_stop: self.manageSignal(wp, 'disconnect')

        for expr_key in ["SINGLE_SELECTION_EXPRESSION", "MULTIPLE_SELECTION_EXPRESSION", "CUSTOM_SELECTION_EXPRESSION"]:
            try: self.widgets.get("EXPLORING", {}).get(expr_key, {}).get("WIDGET", type('', (), {'setExpression': lambda s, x: None})()).setExpression("")
            except Exception:  # Widget may not be ready - expected during initialization
                pass

        if self.project_props.get("OPTIONS", {}).get("LAYERS", {}).get("LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"):
            self.manageSignal(["QGIS", "LAYER_TREE_VIEW"], 'disconnect')
        return widgets_to_stop

    def _detect_multi_step_filter(self, layer, layer_props):
        """v4.0 S18: → FilteringController."""
        if self._controller_integration and self._controller_integration.filtering_controller:
            succeeded, result = self._controller_integration.delegate_detect_multi_step_filter(layer, layer_props)
            if succeeded and result: self._sync_additive_mode_widgets(layer_props)
            return result if succeeded else False
        return False

    def _sync_additive_mode_widgets(self, layer_props):
        """v4.0 S18: Sync widgets after additive mode."""
        try:
            for key in ["SOURCE_LAYER_COMBINE_OPERATOR", "OTHER_LAYERS_COMBINE_OPERATOR"]:
                w = self.widgets["FILTERING"][key]["WIDGET"]; w.blockSignals(True); w.setCurrentIndex(0); w.blockSignals(False)
        except Exception as e: logger.debug(f"Error syncing additive mode widgets: {e}")

    def _synchronize_layer_widgets(self, layer, layer_props, manual_change=False):
        """
        v4.0 S18: → LayerSyncController with fallback for controller unavailable.
        FIX 2026-01-14: Added manual_change parameter.
        """
        # Try delegation first
        if self._layer_sync_ctrl:
            if self._controller_integration.delegate_synchronize_layer_widgets(layer, layer_props, manual_change=manual_change):
                return

        # Fallback: Minimal inline logic when controller unavailable (v4.0 Migration Fix)
        if not self._is_ui_ready() or not layer:
            return

        # FIX 2026-01-14: Define last_layer BEFORE using it
        last_layer = self.widgets["FILTERING"]["CURRENT_LAYER"]["WIDGET"].currentLayer()
        logger.debug(f"current_layer_changed: Syncing combo | last_layer={last_layer.name() if last_layer else None} | new_layer={layer.name()}")
        if last_layer is None or last_layer.id() != layer.id():
            logger.debug("  -> Layer changed, updating combo")
            self.manageSignal(["FILTERING", "CURRENT_LAYER"], 'disconnect')
            self.widgets["FILTERING"]["CURRENT_LAYER"]["WIDGET"].setLayer(layer)
            self.manageSignal(["FILTERING", "CURRENT_LAYER"], 'connect', 'layerChanged')
        else:
            logger.debug("  -> Same layer, skipping combo update")
        # NOTE: Removed duplicate last_layer definition - now defined at start of fallback block

        # Update backend indicator
        forced_backend = getattr(self, 'forced_backends', {}).get(layer.id())
        infos = layer_props.get('infos', {})
        provider_type = infos.get('layer_provider_type', layer.providerType())
        postgresql_conn = infos.get('postgresql_connection_available')
        self._update_backend_indicator(provider_type, postgresql_conn, actual_backend=forced_backend)

        # Initialize buffer property widget
        self.filtering_init_buffer_property()

        # CRITICAL: Update all layer property widgets (enable/disable based on group state)
        for group_name, tuple_group in self.layer_properties_tuples_dict.items():
            group_state = True
            # Skip groups that are always enabled
            if group_name not in ('is', 'selection_expression', 'source_layer'):
                if tuple_group:
                    group_property = tuple_group[0]
                    group_state = layer_props.get(group_property[0], {}).get(group_property[1], True)
                    if group_state is False:
                        self.properties_group_state_reset_to_default(tuple_group, group_name, group_state)
                    else:
                        self.properties_group_state_enabler(tuple_group)

            if group_state is True:
                for prop_tuple in tuple_group:
                    if prop_tuple[0].upper() not in self.widgets:
                        continue
                    if prop_tuple[1].upper() not in self.widgets.get(prop_tuple[0].upper(), {}):
                        continue
                    widget_info = self.widgets[prop_tuple[0].upper()][prop_tuple[1].upper()]
                    widget = widget_info.get("WIDGET")
                    widget_type = widget_info.get("TYPE")
                    stored_value = layer_props.get(prop_tuple[0], {}).get(prop_tuple[1])

                    if widget is None:
                        continue

                    # Sync widget based on type
                    widget.blockSignals(True)
                    try:
                        if widget_type == 'PushButton' and widget.isCheckable():
                            widget.setChecked(bool(stored_value))
                            if "ICON_ON_TRUE" in widget_info and "ICON_ON_FALSE" in widget_info:
                                self.switch_widget_icon(prop_tuple, stored_value)
                        elif widget_type == 'CheckableComboBox':
                            widget.setCheckedItems(stored_value if isinstance(stored_value, list) else [])
                        elif widget_type == 'ComboBox':
                            if prop_tuple[1] in ('source_layer_combine_operator', 'other_layers_combine_operator'):
                                widget.setCurrentIndex(self._combine_operator_to_index(stored_value))
                            else:
                                idx = widget.findText(str(stored_value) if stored_value else "")
                                widget.setCurrentIndex(max(idx, 0))
                        elif widget_type == 'QgsFieldExpressionWidget':
                            widget.setLayer(layer)
                            widget.setExpression(str(stored_value) if stored_value else "")
                        elif widget_type in ('QgsDoubleSpinBox', 'QgsSpinBox'):
                            widget.setValue(float(stored_value) if stored_value else 0)
                        elif widget_type == 'CheckBox':
                            widget.setChecked(bool(stored_value))
                        elif widget_type == 'LineEdit':
                            widget.setText(str(stored_value) if stored_value else "")
                        elif widget_type == 'QgsProjectionSelectionWidget':
                            crs = QgsCoordinateReferenceSystem(str(stored_value) if stored_value else "")
                            if crs.isValid():
                                widget.setCrs(crs)
                        elif widget_type == 'PropertyOverrideButton':
                            widget.setActive(bool(stored_value))
                    finally:
                        widget.blockSignals(False)

        # Populate layers combobox
        self.manageSignal(["FILTERING", "LAYERS_TO_FILTER"], 'disconnect')
        self.filtering_populate_layers_chekableCombobox(layer)
        self.manageSignal(["FILTERING", "LAYERS_TO_FILTER"], 'connect', 'checkedItemsChanged')
        # Force visual refresh
        if "FILTERING" in self.widgets and "LAYERS_TO_FILTER" in self.widgets["FILTERING"]:
            widget = self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"]
            if widget:
                widget.update()
                widget.repaint()

        # Synchronize checkable button associated widgets enabled state
        self.filtering_layers_to_filter_state_changed()
        self.filtering_combine_operator_state_changed()
        self.filtering_geometric_predicates_state_changed()

    def _reload_exploration_widgets(self, layer, layer_props):
        """v4.0 S18: → ExploringController with fallback."""
        logger.info(f"_reload_exploration_widgets called for layer: {layer.name() if layer else 'None'}")
        if self._exploring_ctrl:
            logger.debug("Delegating to ExploringController")
            self._exploring_ctrl._reload_exploration_widgets(layer, layer_props)
        else:
            logger.warning("ExploringController NOT available - using fallback")
            # Fallback: Update exploring widgets layer when controller unavailable
            self._fallback_reload_exploration_widgets(layer, layer_props)

    def _fallback_reload_exploration_widgets(self, layer, layer_props):
        """FIX 2026-01-14: Fallback to update exploring widgets when controller unavailable."""
        if not self.widgets_initialized or not layer:
            logger.warning(f"Fallback skipped: widgets_initialized={self.widgets_initialized}, layer={layer}")
            return
        logger.info(f"=== FALLBACK _reload_exploration_widgets === layer: {layer.name()}")
        try:
            # FIX 2026-01-15 v6: CRITICAL - Disconnect ALL exploration signals BEFORE updating widgets
            # Pattern from before_migration (lines 9721-9725) prevents spurious signal emissions
            self.manageSignal(["EXPLORING", "SINGLE_SELECTION_FEATURES"], 'disconnect')
            self.manageSignal(["EXPLORING", "MULTIPLE_SELECTION_FEATURES"], 'disconnect')
            self.manageSignal(["EXPLORING", "SINGLE_SELECTION_EXPRESSION"], 'disconnect')
            self.manageSignal(["EXPLORING", "MULTIPLE_SELECTION_EXPRESSION"], 'disconnect')
            self.manageSignal(["EXPLORING", "CUSTOM_SELECTION_EXPRESSION"], 'disconnect')

            # Get expressions from layer_props
            exploring = layer_props.get("exploring", {})
            single_expr = exploring.get("single_selection_expression", "")
            multiple_expr = exploring.get("multiple_selection_expression", "")
            custom_expr = exploring.get("custom_selection_expression", "")

            # v4.0 SMART FIELD SELECTION: Upgrade PK-only expressions to better fields
            primary_key = layer_props.get("infos", {}).get("primary_key_name", "")
            logger.debug(f"Expressions: single={single_expr}, multiple={multiple_expr}, custom={custom_expr}, pk={primary_key}")

            # Check if expressions are just the primary key (default) - upgrade if better field exists
            should_upgrade_single = (single_expr == primary_key or not single_expr)
            should_upgrade_multiple = (multiple_expr == primary_key or not multiple_expr)
            should_upgrade_custom = (custom_expr == primary_key or not custom_expr)

            if should_upgrade_single or should_upgrade_multiple or should_upgrade_custom:
                from .infrastructure.utils import get_best_display_field
                best_field = get_best_display_field(layer)

                # Fallback if no descriptive field found
                if not best_field or best_field == primary_key:
                    fields = layer.fields()
                    for field in fields:
                        if field.name() != primary_key:
                            best_field = field.name()
                            break
                    if not best_field:
                        best_field = fields[0].name() if fields.count() > 0 else (primary_key or "$id")

                # Only upgrade if different from PK
                if best_field and best_field != primary_key:
                    if should_upgrade_single:
                        single_expr = best_field
                        exploring["single_selection_expression"] = best_field
                        logger.info(f"✨ FALLBACK: Upgraded single_selection to '{best_field}'")
                    if should_upgrade_multiple:
                        multiple_expr = best_field
                        exploring["multiple_selection_expression"] = best_field
                        logger.info(f"✨ FALLBACK: Upgraded multiple_selection to '{best_field}'")
                    if should_upgrade_custom:
                        custom_expr = best_field
                        exploring["custom_selection_expression"] = best_field
                        logger.info(f"✨ FALLBACK: Upgraded custom_selection to '{best_field}'")

            # Update single selection widget (QgsFeaturePickerWidget)
            if "SINGLE_SELECTION_FEATURES" in self.widgets.get("EXPLORING", {}):
                widget = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
                if widget:
                    logger.debug(f"Updating SINGLE_SELECTION_FEATURES: old_layer={widget.layer().name() if widget.layer() else 'None'} → new_layer={layer.name()}")  # nosec B608 - false positive: logger statement, no SQL execution
                    widget.setLayer(None)  # Force refresh
                    widget.setLayer(layer)
                    widget.setDisplayExpression(single_expr)
                    widget.setFetchGeometry(True)
                    widget.setShowBrowserButtons(True)
                    widget.setAllowNull(True)
                    # FIX 2026-01-15: Force visual refresh to display features
                    widget.update()
                    widget.repaint()
                    logger.info(f"✓ SINGLE_SELECTION_FEATURES updated: layer={widget.layer().name() if widget.layer() else 'None'}, expr={widget.displayExpression()}")  # nosec B608 - false positive: logger statement, no SQL execution
                else:
                    logger.warning("SINGLE_SELECTION_FEATURES widget is None!")

            # Update multiple selection widget (CheckableFeatureComboBox)
            if "MULTIPLE_SELECTION_FEATURES" in self.widgets.get("EXPLORING", {}):
                widget = self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"]
                if widget and hasattr(widget, 'setLayer'):
                    widget.setLayer(layer, layer_props, skip_task=True)
                    if hasattr(widget, 'setDisplayExpression'):
                        widget.setDisplayExpression(multiple_expr)

            # Update expression widgets (QgsFieldExpressionWidget)
            expr_mappings = [
                ("SINGLE_SELECTION_EXPRESSION", single_expr),
                ("MULTIPLE_SELECTION_EXPRESSION", multiple_expr),
                ("CUSTOM_SELECTION_EXPRESSION", custom_expr)
            ]
            from qgis.core import QgsExpression
            for expr_key, expr_value in expr_mappings:
                if expr_key in self.widgets.get("EXPLORING", {}):
                    widget = self.widgets["EXPLORING"][expr_key]["WIDGET"]
                    if widget and hasattr(widget, 'setLayer'):
                        old_layer = widget.layer().name() if widget.layer() else 'None'
                        widget.setLayer(layer)
                        # FIX 2026-01-16: Use setField for simple field names, setExpression for complex expressions
                        # This ensures the combobox properly selects the field
                        if expr_value:
                            if QgsExpression(expr_value).isField():
                                widget.setField(expr_value)
                            else:
                                widget.setExpression(expr_value)
                        new_layer = widget.layer().name() if widget.layer() else 'None'
                        logger.info(f"✓ {expr_key} updated: {old_layer} → {new_layer}, expr={expr_value}")
                    else:
                        logger.warning(f"{expr_key} widget is None or has no setLayer!")

            # FIX 2026-01-15 v5: CRITICAL - Reconnect signals AFTER all widgets are updated
            # Pattern from before_migration (lines 9898-9904): manageSignal approach
            # This was completely missing in the fallback!
            self.manageSignal(["EXPLORING", "SINGLE_SELECTION_FEATURES"], 'connect', 'featureChanged')
            self.manageSignal(["EXPLORING", "MULTIPLE_SELECTION_FEATURES"], 'connect', 'updatingCheckedItemList')
            self.manageSignal(["EXPLORING", "MULTIPLE_SELECTION_FEATURES"], 'connect', 'filteringCheckedItemList')
            self.manageSignal(["EXPLORING", "SINGLE_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
            self.manageSignal(["EXPLORING", "MULTIPLE_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
            self.manageSignal(["EXPLORING", "CUSTOM_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')

            # ALSO: Direct connection for featureChanged (more reliable than manageSignal)
            # Pattern from before_migration property change handler
            if "SINGLE_SELECTION_FEATURES" in self.widgets.get("EXPLORING", {}):
                picker_widget = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
                if picker_widget:
                    try:
                        picker_widget.featureChanged.disconnect(self.exploring_features_changed)
                    except TypeError:
                        pass
                    picker_widget.featureChanged.connect(self.exploring_features_changed)
                    logger.debug("✓ featureChanged signal directly reconnected")

            logger.debug(f"Fallback: Exploration widgets updated for layer {layer.name()}")
        except Exception as e:
            logger.warning(f"Fallback _reload_exploration_widgets failed: {e}")

    def _restore_groupbox_ui_state(self, groupbox_name):
        """v4.0 Sprint 17: Restore exploring groupbox visual state."""
        if not self.widgets_initialized: return
        self.current_exploring_groupbox = groupbox_name
        if self.current_layer and self.current_layer.id() in self.PROJECT_LAYERS:
            self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["current_exploring_groupbox"] = groupbox_name
        states = {"single_selection": (True, False, False, True, False, True),
                  "multiple_selection": (False, True, True, False, False, True),
                  "custom_selection": (False, True, False, True, True, False)}
        s = states.get(groupbox_name, states["single_selection"])
        gbs = [self.widgets["DOCK"][k]["WIDGET"] for k in ["SINGLE_SELECTION", "MULTIPLE_SELECTION", "CUSTOM_SELECTION"]]
        for gb in gbs: gb.blockSignals(True)
        try:
            for i, gb in enumerate(gbs): gb.setChecked(s[i * 2]); gb.setCollapsed(s[i * 2 + 1]); gb.update()
        finally:
            for gb in gbs: gb.blockSignals(False)

    def _reconnect_layer_signals(self, widgets_to_reconnect, layer_props):
        """v4.0 S18: → LayerSyncController with fallback."""
        if self._layer_sync_ctrl:
            self._controller_integration.delegate_reconnect_layer_signals(widgets_to_reconnect, layer_props)
        else:
            # Fallback: Minimal reconnection logic when controller unavailable
            self._fallback_reconnect_layer_signals(widgets_to_reconnect, layer_props)

    def _fallback_reconnect_layer_signals(self, widgets_to_reconnect, layer_props):
        """FIX 2026-01-14: Fallback for _reconnect_layer_signals when controller unavailable."""
        # Exploring widget prefixes - already reconnected in _reload_exploration_widgets
        exploring_prefixes = [
            ["EXPLORING", "SINGLE_SELECTION_FEATURES"],
            ["EXPLORING", "SINGLE_SELECTION_EXPRESSION"],
            ["EXPLORING", "MULTIPLE_SELECTION_FEATURES"],
            ["EXPLORING", "MULTIPLE_SELECTION_EXPRESSION"],
            ["EXPLORING", "CUSTOM_SELECTION_EXPRESSION"]
        ]

        # Reconnect only non-exploring signals
        for widget_path in widgets_to_reconnect:
            if widget_path not in exploring_prefixes:
                try:
                    self.manageSignal(widget_path, 'connect')
                except Exception as e:
                    logger.debug(f"Fallback reconnect {widget_path} failed: {e}")

        # Reconnect legend link if enabled
        if self.project_props and self.project_props.get("OPTIONS", {}).get("LAYERS", {}).get("LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG", False):
            try:
                self.manageSignal(["QGIS", "LAYER_TREE_VIEW"], 'connect')
            except Exception as e:
                logger.debug(f"Ignored in legend link signal reconnection: {e}")

        # FIX 2026-02-10 (C1): Centralized selectionChanged connection
        if self.current_layer:
            self._connect_selection_signal()

        # Restore exploring groupbox state
        if layer_props and "current_exploring_groupbox" in layer_props.get("exploring", {}):
            saved_groupbox = layer_props["exploring"]["current_exploring_groupbox"]
            if saved_groupbox:
                self._restore_groupbox_ui_state(saved_groupbox)

        # Initialize selection sync when is_selecting is enabled
        is_selecting = layer_props.get("exploring", {}).get("is_selecting", False) if layer_props else False
        if is_selecting:
            logger.debug("Fallback: is_selecting=True, initializing selection sync")
            self.exploring_select_features()

        # FIX 2026-01-14 v2: Force sync button states with PROJECT_LAYERS after reconnection
        self._force_sync_exploring_button_states(layer_props)

    def _force_sync_exploring_button_states(self, layer_props):
        """
        FIX 2026-01-14 v2: Ensure button states match PROJECT_LAYERS.

        This prevents desynchronization where a button appears checked but
        PROJECT_LAYERS["exploring"]["is_selecting"] is False (or vice versa).

        Called after reconnecting layer signals to ensure consistency.
        """
        if not self.current_layer or not layer_props or not self.widgets_initialized:
            return

        exploring = layer_props.get("exploring", {})
        self.current_layer.id()

        # Sync IS_SELECTING button with stored state
        btn_selecting = self.pushButton_checkable_exploring_selecting
        stored_is_selecting = exploring.get("is_selecting", False)
        if btn_selecting.isChecked() != stored_is_selecting:
            logger.info(f"Force sync IS_SELECTING button: {btn_selecting.isChecked()} → {stored_is_selecting}")  # nosec B608 - false positive: logger statement, no SQL execution
            btn_selecting.blockSignals(True)
            btn_selecting.setChecked(stored_is_selecting)
            btn_selecting.blockSignals(False)

        # Sync IS_TRACKING button with stored state
        btn_tracking = self.pushButton_checkable_exploring_tracking
        stored_is_tracking = exploring.get("is_tracking", False)
        if btn_tracking.isChecked() != stored_is_tracking:
            logger.info(f"Force sync IS_TRACKING button: {btn_tracking.isChecked()} → {stored_is_tracking}")
            btn_tracking.blockSignals(True)
            btn_tracking.setChecked(stored_is_tracking)
            btn_tracking.blockSignals(False)

        # Sync IS_LINKING button with stored state
        btn_linking = self.pushButton_checkable_exploring_linking_widgets
        stored_is_linking = exploring.get("is_linking", False)
        if btn_linking.isChecked() != stored_is_linking:
            logger.info(f"Force sync IS_LINKING button: {btn_linking.isChecked()} → {stored_is_linking}")
            btn_linking.blockSignals(True)
            btn_linking.setChecked(stored_is_linking)
            btn_linking.blockSignals(False)

    def _ensure_valid_current_layer(self, requested_layer):
        """v4.0 Sprint 18: Ensure valid layer - delegates to LayerSyncController."""
        if self._layer_sync_ctrl:
            try:
                result = self._controller_integration.delegate_ensure_valid_current_layer(requested_layer)
                if result is not None: return result
            except Exception:  # Delegation may fail if controller not ready - expected
                pass
        if requested_layer:
            try: _ = requested_layer.id(); return requested_layer
            except Exception:  # Layer may be deleted - expected during cleanup
                pass
        return None

    def _is_layer_truly_deleted(self, layer):
        """v4.0 Sprint 18: Check if layer is truly deleted - delegates to LayerSyncController."""
        if layer is None: return True
        try:
            if self._layer_sync_ctrl: return self._controller_integration.delegate_is_layer_truly_deleted(layer)
            import sip
            return sip.isdeleted(layer)
        except (ImportError, RuntimeError, AttributeError):
            return True  # Assume deleted if we can't check

    def current_layer_changed(self, layer: QgsVectorLayer, manual_change: bool = False) -> None:
        """Handle current layer change event from QGIS or user interaction.

        Updates all UI components when the active layer changes:
        - Validates layer and retrieves properties from PROJECT_LAYERS
        - Resets selection tracking and expression cache
        - Synchronizes filtering/exporting widgets
        - Reloads exploration widgets (feature picker, combobox)
        - Reconnects layer-specific signals

        Args:
            layer: The new current QgsVectorLayer.
            manual_change: True if user manually selected layer from combobox.
                          Bypasses protection windows when True.

        Note:
            - Ignores layer changes during active filtering (_filtering_in_progress)
            - Defers changes if plugin is busy (_plugin_busy)
            - Handles deleted C++ objects gracefully
        """
        import traceback
        logger.info(f"=== current_layer_changed ENTRY === layer: {layer.name() if layer else 'None'}, manual: {manual_change}")
        logger.debug(f"Flags: _updating={self._updating_current_layer}, _filtering={self._filtering_in_progress}, _busy={self._plugin_busy}")
        logger.debug(f"Caller stack:\n{''.join(traceback.format_stack()[-4:-1])}")

        if self._updating_current_layer:
            logger.debug("current_layer_changed: Already updating, skipping")
            return

        # FIX-5 (2026-01-16): CRITICAL - Ignore layer change signals during filtering
        # This prevents the comboBox from changing value when layerTreeView emits currentLayerChanged
        # Restored from v2.9.26 - was lost during hexagonal migration
        if getattr(self, '_filtering_in_progress', False):
            logger.debug("v4.0.5: 🛡️ current_layer_changed BLOCKED - filtering in progress")
            return

        # CRITICAL FIX (2026-01-14): Delegate to controller with manual_change flag
        # Manual changes should bypass protection windows and always update widgets
        if self._controller_integration:
            validation_result = self._controller_integration.delegate_current_layer_changed(layer, manual_change=manual_change)
            if validation_result is False:
                if manual_change:
                    # Manual change bypasses protection - continue with update
                    logger.info("⚠️ Controller blocked but continuing anyway (manual user change)")
                else:
                    # Automatic change blocked by controller - STOP here
                    logger.info("⚠️ Controller blocked automatic layer change (protection active) - STOPPING")
                    return
        layer = self._ensure_valid_current_layer(layer)
        if layer is None:
            logger.debug("current_layer_changed: Layer is None after validation")
            return
        if self._plugin_busy:
            logger.debug("current_layer_changed: Plugin busy, deferring")
            self._defer_layer_change(layer)
            return
        try: _ = layer.id()
        except (RuntimeError, AttributeError):
            logger.warning("current_layer_changed: Layer C++ object deleted")
            return
        self._updating_current_layer = True
        self._reset_selection_tracking_for_layer(layer)
        try:
            should_continue, validated_layer, layer_props = self._validate_and_prepare_layer(layer)
            if not should_continue: return
            self._reset_layer_expressions(layer_props); widgets = self._disconnect_layer_signals()
            logger.info("✓ Step 1: Layer validated and expressions reset")

            # FIX 2026-01-14: Pass manual_change flag to widget synchronization
            self._synchronize_layer_widgets(validated_layer, layer_props, manual_change=manual_change)
            logger.info("✓ Step 2: Layer widgets synchronized")

            self._reload_exploration_widgets(validated_layer, layer_props)
            logger.info("✓ Step 3: Exploration widgets reloaded")

            # Force visual update of exploration widgets
            if "EXPLORING" in self.widgets:
                for key, widget_info in self.widgets["EXPLORING"].items():
                    if "WIDGET" in widget_info and widget_info["WIDGET"]:
                        try:
                            widget_info["WIDGET"].update()
                            widget_info["WIDGET"].repaint()
                        except Exception as e:
                            logger.debug(f"Ignored in exploring widget repaint for {key}: {e}")
                logger.debug("Exploring widgets visually refreshed")

            # CRITICAL: Initialize exploring groupbox for ALL layers, not just existing ones
            # This ensures widgets are updated even when switching to a new layer
            if self.current_layer:
                # Ensure layer is in PROJECT_LAYERS before initializing
                if self.current_layer.id() not in self.PROJECT_LAYERS:
                    logger.debug(f"Layer {self.current_layer.name()} not in PROJECT_LAYERS yet - will be added")
                self.exploring_groupbox_init()
                logger.info("✓ Step 4: Exploring groupbox initialized")

            self._update_exploring_buttons_state()
            logger.info("✓ Step 5: Exploring buttons state updated")

            self._reconnect_layer_signals(widgets, layer_props)
            logger.debug("✓ Step 6: Layer signals reconnected")

            logger.info(f"=== current_layer_changed SUCCESS === layer: {validated_layer.name()}")
        except Exception as e:
            logger.error(f"❌ Error in current_layer_changed: {e}")
            import traceback
            logger.error(f"Traceback:\n{traceback.format_exc()}")
        finally:
            self._updating_current_layer = False
            logger.debug("current_layer_changed: Lock released")

    def _defer_layer_change(self, layer):
        """v4.0 Sprint 18: Defer layer change when plugin is busy."""
        from qgis.PyQt.QtCore import QTimer
        from qgis.core import QgsProject
        captured_id = layer.id() if layer else None
        weak_self = weakref.ref(self)

        def safe_change():
            s = weak_self()
            if s and captured_id:
                fresh = QgsProject.instance().mapLayer(captured_id)
                if fresh: s.current_layer_changed(fresh)
        QTimer.singleShot(150, safe_change)

    def _reset_selection_tracking_for_layer(self, layer):
        """Reset selection tracking when layer changes."""
        # Reset single_selection FID
        if hasattr(self, '_last_single_selection_layer_id'):
            if layer is None or layer.id() != self._last_single_selection_layer_id:
                self._last_single_selection_fid = None
                self._last_single_selection_layer_id = None

        # Reset multiple_selection FIDs
        if hasattr(self, '_last_multiple_selection_layer_id'):
            if layer is None or layer.id() != self._last_multiple_selection_layer_id:
                self._last_multiple_selection_fids = None
                self._last_multiple_selection_layer_id = None

    def project_property_changed(self, input_property, input_data=None, custom_functions={}):
        """v4.0 S18: → PropertyController."""
        if self._property_ctrl: self._controller_integration.delegate_change_project_property(input_property, input_data, custom_functions)

    # v4.0 Sprint 9: Property helper methods removed - logic migrated to PropertyController
    # Removed: _parse_property_data, _find_property_path, _update_is_property,
    # _update_selection_expression_property, _update_other_property (~130 lines)

    def layer_property_changed(self, input_property, input_data=None, custom_functions={}):
        """v4.0 S18: → PropertyController with fallback for controller unavailable."""
        if custom_functions is None:
            custom_functions = {}

        # Try delegation to PropertyController first
        if self._property_ctrl:
            if self._controller_integration.delegate_change_layer_property(input_property, input_data, custom_functions):
                return

        # Fallback: Minimal inline logic when controller is unavailable (v4.0 Migration Fix)
        # FIX 2026-01-16: Use _is_layer_valid() for safe layer checking
        if not self._is_layer_valid():
            return
        if self.current_layer.id() not in self.PROJECT_LAYERS:
            return

        # Find property path in layer_properties_tuples_dict
        properties_group_key, property_path, properties_tuples = None, None, None
        for group_key, tuples in self.layer_properties_tuples_dict.items():
            for tup in tuples:
                if tup[1] == input_property:
                    properties_group_key, property_path, properties_tuples = group_key, tup, tuples
                    break
            if properties_group_key:
                break

        if not properties_group_key or not property_path:
            logger.warning(f"layer_property_changed fallback: property '{input_property}' not found")
            return

        # Get group state from parent widget
        group_state = True
        if properties_tuples:
            group_widget_info = self.widgets.get(properties_tuples[0][0].upper(), {}).get(properties_tuples[0][1].upper(), {})
            group_widget = group_widget_info.get("WIDGET")
            if group_widget and hasattr(group_widget, 'isChecked'):
                group_state = group_widget.isChecked()

        # Enable/disable widgets based on group state
        if group_state:
            self.properties_group_state_enabler(properties_tuples)
        else:
            self.properties_group_state_reset_to_default(properties_tuples, properties_group_key, group_state)

        # Update PROJECT_LAYERS
        if property_path[0] in self.PROJECT_LAYERS[self.current_layer.id()]:
            self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = input_data

        # Call custom callbacks
        if "ON_CHANGE" in custom_functions:
            custom_functions["ON_CHANGE"](0)
        if input_data and "ON_TRUE" in custom_functions:
            custom_functions["ON_TRUE"](0)
        elif not input_data and "ON_FALSE" in custom_functions:
            custom_functions["ON_FALSE"](0)

        # FIX 2026-01-15 v5: CRITICAL - Reconnect widgets using direct connection for featureChanged signal
        # Pattern from before_migration (lines 10670-10681): manageSignal approach using isSignalConnected
        # is unreliable, so we use direct connection for featureChanged.
        if "EXPLORING" in self.widgets and "SINGLE_SELECTION_FEATURES" in self.widgets["EXPLORING"]:
            picker_widget = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
            if picker_widget:
                try:
                    picker_widget.featureChanged.disconnect(self.exploring_features_changed)
                except TypeError:
                    pass
                picker_widget.featureChanged.connect(self.exploring_features_changed)

        # Reconnect other widgets via manageSignal (same as before_migration lines 10678-10682)
        try:
            self.manageSignal(["EXPLORING", "SINGLE_SELECTION_EXPRESSION"], 'connect')
            self.manageSignal(["EXPLORING", "MULTIPLE_SELECTION_FEATURES"], 'connect')
            self.manageSignal(["EXPLORING", "MULTIPLE_SELECTION_EXPRESSION"], 'connect')
            self.manageSignal(["EXPLORING", "CUSTOM_SELECTION_EXPRESSION"], 'connect')
        except Exception as e:
            logger.debug(f"layer_property_changed fallback: Could not reconnect signals: {e}")

    def layer_property_changed_with_buffer_style(self, input_property, input_data=None):
        """v4.0 S18: → PropertyController."""
        if self._property_ctrl: self._controller_integration.property_controller.change_property_with_buffer_style(input_property, input_data)

    def _update_buffer_spinbox_style(self, buffer_value):
        """Update buffer spinbox style based on value (negative = erosion mode)."""
        spinbox = self.mQgsDoubleSpinBox_filtering_buffer_value
        if buffer_value is not None and buffer_value < 0:
            spinbox.setStyleSheet("QgsDoubleSpinBox{background-color:#FFF3CD;border:2px solid #FFC107;color:#856404;}QgsDoubleSpinBox:focus{border:2px solid #FF9800;}")
            spinbox.setToolTip(self.tr("Negative buffer (erosion): shrinks polygons inward"))
        else:
            spinbox.setStyleSheet("")
            spinbox.setToolTip(self.tr("Buffer value in meters (positive=expand, negative=shrink polygons)"))

    def _update_buffer_validation(self):
        """Update buffer spinbox validation - delegates to PropertyController."""
        if self._property_ctrl:
            try: self._controller_integration.delegate_update_buffer_validation(); return
            except Exception as e: logger.debug(f"Buffer validation delegation failed (using fallback): {e}")
        logger.warning("_update_buffer_validation: Controller delegation failed")

    def set_exporting_properties(self):
        """v3.1 Sprint 16: Set exporting widgets from project properties."""
        if not self._is_ui_ready(): return

        widgets_to_stop = [["EXPORTING", w] for w in ["HAS_LAYERS_TO_EXPORT", "HAS_PROJECTION_TO_EXPORT", "HAS_STYLES_TO_EXPORT",
            "HAS_DATATYPE_TO_EXPORT", "LAYERS_TO_EXPORT", "PROJECTION_TO_EXPORT", "STYLES_TO_EXPORT", "DATATYPE_TO_EXPORT"]]

        for wp in widgets_to_stop: self.manageSignal(wp, 'disconnect')

        for group_key, properties_tuples in self.export_properties_tuples_dict.items():
            group_state = self.widgets[properties_tuples[0][0].upper()][properties_tuples[0][1].upper()]["WIDGET"].isChecked()

            if not group_state:
                self.properties_group_state_reset_to_default(properties_tuples, group_key, group_state)
            else:
                self.properties_group_state_enabler(properties_tuples)
                for prop_path in properties_tuples:
                    key0, key1 = prop_path[0].upper(), prop_path[1].upper()
                    if key0 not in self.widgets or key1 not in self.widgets.get(key0, {}):
                        continue
                    w = self.widgets[key0][key1]
                    val = self.project_props.get(key0, {}).get(key1)
                    self._set_widget_value(w, val, prop_path[1])

        for wp in widgets_to_stop: self.manageSignal(wp, 'connect')
        self.CONFIG_DATA["CURRENT_PROJECT"]['EXPORTING'] = self.project_props['EXPORTING']

    def _set_widget_value(self, widget_data, value, prop_name=None):
        """v3.1 Sprint 16: Set widget value by type."""
        w, wt = widget_data["WIDGET"], widget_data["TYPE"]
        if wt in ('PushButton', 'CheckBox'): w.setChecked(value)
        elif wt == 'CheckableComboBox': w.setCheckedItems(value)
        elif wt == 'ComboBox': w.setCurrentIndex(w.findText(value))
        elif wt == 'QgsDoubleSpinBox': w.setValue(value)
        elif wt == 'LineEdit':
            if not value and prop_name == 'output_folder_to_export': self.reset_export_output_path()
            elif not value and prop_name == 'zip_to_export': self.reset_export_output_pathzip()
            else: w.setText(value)
        elif wt == 'QgsProjectionSelectionWidget':
            crs = QgsCoordinateReferenceSystem(value)
            if crs.isValid(): w.setCrs(crs)

    def properties_group_state_enabler(self, tuple_group):
        """v4.0 S18: Enable widgets in a property group."""
        if not self._is_ui_ready(): return
        for t in tuple_group:
            if t[0].upper() not in self.widgets or t[1].upper() not in self.widgets[t[0].upper()]: continue
            we = self.widgets[t[0].upper()][t[1].upper()]
            # Has_output_folder_to_export and has_zip_to_export pushbuttons are ALWAYS enabled
            # They can be checked/unchecked at any time regardless of layer selection
            we["WIDGET"].setEnabled(True)
            if we["TYPE"] == 'QgsFieldExpressionWidget' and self.current_layer: we["WIDGET"].setLayer(self.current_layer)

    def properties_group_state_reset_to_default(self, tuple_group, group_name, state):
        """v4.0 S18: → PropertyController with fallback."""
        # Try delegation first
        if self._property_ctrl:
            if self._controller_integration.delegate_reset_property_group(tuple_group, group_name, state):
                return

        # Fallback: Minimal inline reset logic when controller unavailable (v4.0 Migration Fix)
        if not self._is_ui_ready():
            return

        for i, property_path in enumerate(tuple_group):
            if property_path[0].upper() not in self.widgets:
                continue
            if property_path[1].upper() not in self.widgets.get(property_path[0].upper(), {}):
                continue

            widget_info = self.widgets[property_path[0].upper()][property_path[1].upper()]
            widget = widget_info.get("WIDGET")
            widget_info.get("TYPE")

            if widget is None:
                continue

            # Handle enabled state: first widget (HAS_xxx) stays enabled, others disabled
            if i == 0 and property_path[1].upper().find('HAS') >= 0:
                widget.setEnabled(True)
            else:
                widget.setEnabled(state)

    def filtering_init_buffer_property(self):
        """v4.0 S18: Init buffer property override widget.

        v4.0.7: FIX - Use widget state (isChecked) as source of truth for has_buffer,
                not just the stored value in PROJECT_LAYERS which may be out of sync.
        v4.0.8: FIX - Removed has_loaded_layers guard as this is called during sync
                before layers are fully ready, and we need to set enabled states.
        """
        if not self.widgets_initialized or not self.current_layer or self.current_layer.id() not in self.PROJECT_LAYERS: return
        lp, lid = self.PROJECT_LAYERS[self.current_layer.id()], self.current_layer.id()
        prop_def = QgsPropertyDefinition(f"{lid}_buffer_property_definition", QgsPropertyDefinition.DataTypeNumeric, f"Replace buffer with expression for {lid}", 'Expression must return numeric values (meters)')
        buf_expr = lp["filtering"]["buffer_value_expression"]
        if not isinstance(buf_expr, str): buf_expr = str(buf_expr) if buf_expr else ''; lp["filtering"]["buffer_value_expression"] = buf_expr
        prop = QgsProperty.fromExpression(buf_expr) if buf_expr and buf_expr.strip() else QgsProperty()
        self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].init(0, prop, prop_def, self.current_layer)

        # Use widget isChecked() as source of truth - the stored value may lag behind
        has_buf_widget = self.widgets["FILTERING"]["HAS_BUFFER_VALUE"]["WIDGET"].isChecked()
        has_buf_stored = lp["filtering"].get("has_buffer_value", False)
        # Use widget state if available, fallback to stored value
        has_buf = has_buf_widget if self.widgets["FILTERING"]["HAS_BUFFER_VALUE"]["WIDGET"].isEnabled() else has_buf_stored

        is_active, has_expr = lp["filtering"]["buffer_value_property"], bool(buf_expr and buf_expr.strip())
        self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"].setEnabled(has_buf and not (is_active and has_expr))
        self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].setEnabled(has_buf)

    def filtering_buffer_property_changed(self):
        """v4.0 Sprint 8: Optimized - handle buffer property override button changes.

        v4.0.3: Do NOT disable layout - this is triggered by property button, not checkable pushbutton.
        The HAS_BUFFER_VALUE pushbutton controls the layout state.
        v4.0.8: FIX - Replaced _is_ui_ready() guard with widgets_initialized only guard
                to allow execution during layer sync before has_loaded_layers is True.
        """
        if not self.widgets_initialized or not self.current_layer or self.current_layer.id() not in self.PROJECT_LAYERS: return

        self.manageSignal(["FILTERING", "BUFFER_VALUE_PROPERTY"], 'disconnect')

        w = self.widgets["FILTERING"]
        has_buffer_checked = w["HAS_BUFFER_VALUE"]["WIDGET"].isChecked()
        is_active = w["BUFFER_VALUE_PROPERTY"]["WIDGET"].isActive()
        has_valid_expr = False

        layer_id = self.current_layer.id()
        lf = self.PROJECT_LAYERS[layer_id]["filtering"]

        if is_active:
            qgs_prop = w["BUFFER_VALUE_PROPERTY"]["WIDGET"].toProperty()
            if qgs_prop.propertyType() == QgsProperty.ExpressionBasedProperty:
                expr = qgs_prop.asExpression()
                has_valid_expr = bool(expr and expr.strip())
                lf["buffer_value_expression"] = expr if has_valid_expr else ''
                lf["buffer_value_property"] = has_valid_expr
            else:
                lf["buffer_value_expression"], lf["buffer_value_property"] = '', False
        else:
            lf["buffer_value_expression"], lf["buffer_value_property"] = '', False
            w["BUFFER_VALUE_PROPERTY"]["WIDGET"].setToProperty(QgsProperty())

        if self._controller_integration:
            self._controller_integration.delegate_filtering_set_buffer_property_active(is_active and has_valid_expr)

        w["BUFFER_VALUE"]["WIDGET"].setEnabled(has_buffer_checked and not (is_active and has_valid_expr))
        w["BUFFER_VALUE_PROPERTY"]["WIDGET"].setEnabled(has_buffer_checked)

        # Do NOT call _set_layout_widgets_enabled here - it's controlled by HAS_BUFFER_VALUE pushbutton

        self.manageSignal(["FILTERING", "BUFFER_VALUE_PROPERTY"], 'connect')

    def get_buffer_property_state(self):
        # v3.1 STORY-2.4: Try controller delegation first
        if self._controller_integration is not None:
            result = self._controller_integration.delegate_filtering_get_buffer_property_active()
            if result is not None:
                return result
        # Fallback to direct widget access
        return self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].isActive()

    def filtering_layers_to_filter_state_changed(self):
        """Handle changes to the has_layers_to_filter checkable button.

        When checked (True): Enable layers_to_filter combobox and use_centroids_distant_layers checkbox
        When unchecked (False): Disable these widgets

        v4.0.1: REGRESSION FIX - Restored original condition from v2.3.8
        v4.0.3: Disable entire row layout when unchecked
        """
        # Guard: Only process after full initialization
        if not (self.widgets_initialized is True and self.has_loaded_layers is True):
            return

        is_checked = self.widgets["FILTERING"]["HAS_LAYERS_TO_FILTER"]["WIDGET"].isChecked()

        # Disable entire row layout (includes all widgets in the row)
        self._set_layout_widgets_enabled('horizontalLayout_filtering_distant_layers', is_checked)

        # Also set individual widgets that may not be in the layout
        self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].setEnabled(is_checked)
        self.widgets["FILTERING"]["USE_CENTROIDS_DISTANT_LAYERS"]["WIDGET"].setEnabled(is_checked)

        # Optional controller delegation for additional logic
        if self._controller_integration and hasattr(self._controller_integration, 'delegate_filtering_layers_to_filter_state_changed'):
            self._controller_integration.delegate_filtering_layers_to_filter_state_changed(is_checked)

        logger.debug(f"filtering_layers_to_filter_state_changed: is_checked={is_checked}")

    def filtering_combine_operator_state_changed(self):
        """Handle changes to the has_combine_operator checkable button.

        When checked (True): Enable combine operator comboboxes
        When unchecked (False): Disable these widgets

        v4.0.1: REGRESSION FIX - Restored original condition from v2.3.8
        v4.0.3: Disable entire row layout when unchecked
        """
        # Guard: Only process after full initialization
        if not (self.widgets_initialized is True and self.has_loaded_layers is True):
            return

        is_checked = self.widgets["FILTERING"]["HAS_COMBINE_OPERATOR"]["WIDGET"].isChecked()

        # Disable entire row layout
        self._set_layout_widgets_enabled('horizontalLayout_filtering_values_search', is_checked)

        # Also set individual widgets
        self.widgets["FILTERING"]["SOURCE_LAYER_COMBINE_OPERATOR"]["WIDGET"].setEnabled(is_checked)
        self.widgets["FILTERING"]["OTHER_LAYERS_COMBINE_OPERATOR"]["WIDGET"].setEnabled(is_checked)

        # Optional controller delegation
        if self._controller_integration and hasattr(self._controller_integration, 'delegate_filtering_combine_operator_state_changed'):
            self._controller_integration.delegate_filtering_combine_operator_state_changed(is_checked)

        logger.debug(f"filtering_combine_operator_state_changed: is_checked={is_checked}")

    def filtering_geometric_predicates_state_changed(self):
        """Handle changes to the has_geometric_predicates checkable button.

        When checked (True): Enable geometric predicates combobox
        When unchecked (False): Disable this widget

        v4.0.1: REGRESSION FIX - Restored original condition from v2.3.8
        """
        # Guard: Only process after full initialization
        if not (self.widgets_initialized is True and self.has_loaded_layers is True):
            return

        is_checked = self.widgets["FILTERING"]["HAS_GEOMETRIC_PREDICATES"]["WIDGET"].isChecked()

        # Enable/disable geometric predicates widget
        self.widgets["FILTERING"]["GEOMETRIC_PREDICATES"]["WIDGET"].setEnabled(is_checked)

        # Optional controller delegation
        if self._controller_integration and hasattr(self._controller_integration, 'delegate_filtering_geometric_predicates_state_changed'):
            self._controller_integration.delegate_filtering_geometric_predicates_state_changed(is_checked)

        logger.debug(f"filtering_geometric_predicates_state_changed: is_checked={is_checked}")

    def filtering_buffer_value_state_changed(self):
        """Handle changes to the has_buffer_value checkable button.

        When checked (True): Enable buffer value widgets (spin box and property button)
        When unchecked (False): Disable these widgets

        v4.0.3: NEW - Separate from filtering_buffer_property_changed()
        v4.0.7: FIX - Property override button logic: when buffer is enabled,
                the spinbox is disabled if property override is active with valid expression.
                Property override button should be enabled when buffer is enabled.
        v4.0.8: FIX - Removed has_loaded_layers guard as this method is called during
                layer synchronization before layers are fully ready.
        """
        # Guard: Only process after widgets are initialized
        if not self.widgets_initialized:
            return

        is_checked = self.widgets["FILTERING"]["HAS_BUFFER_VALUE"]["WIDGET"].isChecked()

        # Get property override state to determine spinbox enabled state
        is_property_active = False
        has_valid_expr = False

        if is_checked and self.current_layer and self.current_layer.id() in self.PROJECT_LAYERS:
            lf = self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]
            is_property_active = lf.get("buffer_value_property", False)
            buf_expr = lf.get("buffer_value_expression", "")
            has_valid_expr = bool(buf_expr and str(buf_expr).strip())

        # Spinbox logic - disabled when:
        # 1. Buffer not checked (is_checked=False), OR
        # 2. Buffer checked BUT property override is active with valid expression
        spinbox_enabled = is_checked and not (is_property_active and has_valid_expr)

        # Property button is simply enabled when buffer is checked
        property_button_enabled = is_checked

        # Set layout widgets - but we need to fine-tune individual widgets after
        self._set_layout_widgets_enabled('horizontalLayout_filtering_values_buttons', is_checked)

        # Override with correct logic for spinbox (may need to be disabled even when is_checked=True)
        self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"].setEnabled(spinbox_enabled)
        self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].setEnabled(property_button_enabled)

        # Optional controller delegation
        if self._controller_integration and hasattr(self._controller_integration, 'delegate_filtering_buffer_value_state_changed'):
            self._controller_integration.delegate_filtering_buffer_value_state_changed(is_checked)

        logger.debug(f"filtering_buffer_value_state_changed: is_checked={is_checked}, spinbox_enabled={spinbox_enabled}, property_button_enabled={property_button_enabled}")

    def filtering_buffer_type_state_changed(self):
        """Handle changes to the has_buffer_type checkable button.

        When checked (True): Enable buffer type and segments widgets
        When unchecked (False): Disable these widgets

        v4.0.1: REGRESSION FIX - Restored original condition from v2.3.8
        v4.0.3: Disable entire row layout when unchecked
        """
        # Guard: Only process after full initialization
        if not (self.widgets_initialized is True and self.has_loaded_layers is True):
            return

        is_checked = self.widgets["FILTERING"]["HAS_BUFFER_TYPE"]["WIDGET"].isChecked()

        # Disable entire row layout
        self._set_layout_widgets_enabled('horizontalLayout_filtering_buffer_type_segments', is_checked)

        # Also set individual widgets
        self.widgets["FILTERING"]["BUFFER_TYPE"]["WIDGET"].setEnabled(is_checked)
        self.widgets["FILTERING"]["BUFFER_SEGMENTS"]["WIDGET"].setEnabled(is_checked)

        # Optional controller delegation
        if self._controller_integration and hasattr(self._controller_integration, 'delegate_filtering_buffer_type_state_changed'):
            self._controller_integration.delegate_filtering_buffer_type_state_changed(is_checked)

        logger.debug(f"filtering_buffer_type_state_changed: is_checked={is_checked}")

    def _update_centroids_source_checkbox_state(self):
        """v4.0 Sprint 8: Optimized - update centroids checkbox enabled state."""
        if not self.widgets_initialized: return
        if (combo := self.widgets.get("FILTERING", {}).get("CURRENT_LAYER", {}).get("WIDGET")) and \
           (checkbox := self.widgets.get("FILTERING", {}).get("USE_CENTROIDS_SOURCE_LAYER", {}).get("WIDGET")):
            checkbox.setEnabled(combo.currentLayer() is not None and combo.isEnabled())

    def _enable_filtering_checkable_buttons(self):
        """v4.0.7: Enable all filtering checkable buttons.

        CRITICAL FIX: The pushButton_checkable_filtering_buffer_value widget is disabled
        by default in the .ui file. This method enables all filtering checkable buttons
        so they can be interacted with when a layer is selected.

        The checkable buttons control the visibility/enabled state of their associated
        widgets (spinbox, combobox, property button, etc.).
        """
        if not self.widgets_initialized:
            return

        # List of all filtering checkable button keys
        checkable_button_keys = [
            "HAS_LAYERS_TO_FILTER",
            "HAS_COMBINE_OPERATOR",
            "HAS_GEOMETRIC_PREDICATES",
            "HAS_BUFFER_VALUE",
            "HAS_BUFFER_TYPE"
        ]

        filtering_widgets = self.widgets.get("FILTERING", {})
        for key in checkable_button_keys:
            widget_config = filtering_widgets.get(key, {})
            widget = widget_config.get("WIDGET")
            if widget:
                # Enable the checkable button itself
                widget.setEnabled(True)
                logger.debug(f"✓ Enabled filtering checkable button: {key}")

    def _set_layout_widgets_enabled(self, layout_name: str, enabled: bool):
        """v4.0.3: Enable/disable all widgets in a horizontal layout.

        Args:
            layout_name: Name of the layout (e.g., 'horizontalLayout_filtering_distant_layers')
            enabled: True to enable widgets, False to disable
        """
        # Guard: Don't process if widgets not initialized
        if not self.widgets_initialized:
            return

        if not hasattr(self, layout_name):
            logger.warning(f"Layout {layout_name} not found")
            return

        layout = getattr(self, layout_name)
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                widget.setEnabled(enabled)

    def dialog_export_output_path(self):
        """v3.1 Sprint 12: Simplified - dialog for export output path."""
        if not self._is_ui_ready(): return
        path = ''
        state = self.widgets["EXPORTING"]["HAS_OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].isChecked()
        datatype = self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"].currentText() if self.widgets["EXPORTING"]["HAS_DATATYPE_TO_EXPORT"]["WIDGET"].isChecked() else ''

        if state:
            if self.widgets["EXPORTING"]["HAS_LAYERS_TO_EXPORT"]["WIDGET"].isChecked():
                layers = self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].checkedItems()
                if len(layers) == 1 and datatype:
                    layer = layers[0]
                    match = re.search('.* ', layer)
                    layer = match.group() if match else layer
                    path = str(QtWidgets.QFileDialog.getSaveFileName(self, 'Save your layer to a file', os.path.join(self.current_project_path, self.output_name + '_' + layer.strip()), f'*.{datatype}')[0])
                elif datatype.upper() == 'GPKG':
                    path = str(QtWidgets.QFileDialog.getSaveFileName(self, 'Save your layer to a file', os.path.join(self.current_project_path, self.output_name + '.gpkg'), '*.gpkg')[0])
                else:
                    path = str(QtWidgets.QFileDialog.getExistingDirectory(self, 'Select a folder where to export your layers', self.current_project_path))
            else:
                path = str(QtWidgets.QFileDialog.getExistingDirectory(self, 'Select a folder where to export your layers', self.current_project_path))

            if path:
                self.widgets["EXPORTING"]["OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].setText(os.path.normcase(path))
            else:
                state = False
                self.widgets["EXPORTING"]["OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].clear()
        else:
            self.widgets["EXPORTING"]["OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].clear()

        self.project_property_changed('has_output_folder_to_export', state)
        self.project_property_changed('output_folder_to_export', path)

    def reset_export_output_path(self):
        """v4.0 S18: Reset export output path."""
        if not self.widgets_initialized or not self.has_loaded_layers or self.widgets["EXPORTING"]["OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].text(): return
        self.widgets["EXPORTING"]["OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].clear(); self.widgets["EXPORTING"]["HAS_OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].setChecked(False)
        self.project_property_changed('has_output_folder_to_export', False); self.project_property_changed('output_folder_to_export', '')

    def dialog_export_output_pathzip(self):
        """v3.1 Sprint 12: Simplified - dialog for zip export path."""
        if not self._is_ui_ready(): return
        path = ''
        state = self.widgets["EXPORTING"]["HAS_ZIP_TO_EXPORT"]["WIDGET"].isChecked()
        if state:
            path = str(QtWidgets.QFileDialog.getSaveFileName(self, 'Save your exported data to a zip file', os.path.join(self.current_project_path, self.output_name), '*.zip')[0])
            if path:
                self.widgets["EXPORTING"]["ZIP_TO_EXPORT"]["WIDGET"].setText(os.path.normcase(path))
            else:
                state = False
                self.widgets["EXPORTING"]["ZIP_TO_EXPORT"]["WIDGET"].clear()
        else:
            self.widgets["EXPORTING"]["ZIP_TO_EXPORT"]["WIDGET"].clear()
        self.project_property_changed('has_zip_to_export', state)
        self.project_property_changed('zip_to_export', path)

    def reset_export_output_pathzip(self):
        """v4.0 S18: Reset zip export path."""
        if not self.widgets_initialized or not self.has_loaded_layers or self.widgets["EXPORTING"]["ZIP_TO_EXPORT"]["WIDGET"].text(): return
        self.widgets["EXPORTING"]["ZIP_TO_EXPORT"]["WIDGET"].clear(); self.widgets["EXPORTING"]["HAS_ZIP_TO_EXPORT"]["WIDGET"].setChecked(False)
        self.project_property_changed('has_zip_to_export', False); self.project_property_changed('zip_to_export', '')

    def filtering_auto_current_layer_changed(self, state=None):
        """
        v3.1 Sprint 12: Simplified - handle auto current layer toggle.
        v4.0.5: When checked, synchronizes comboBox_filtering_current_layer with iface.activeLayer()
        FIX 2026-01-14: Clear signal cache to ensure connection/disconnection works properly.
        """
        if not self._is_ui_ready(): return
        if state is None:
            state = self.project_props["OPTIONS"]["LAYERS"]["LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"]
        self.widgets["FILTERING"]["AUTO_CURRENT_LAYER"]["WIDGET"].setChecked(state)
        self.project_props["OPTIONS"]["LAYERS"]["LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"] = state

        # When enabling auto sync, immediately sync current layer with active layer
        if state and hasattr(self, 'comboBox_filtering_current_layer'):
            active_layer = self.iface.activeLayer()
            if active_layer and isinstance(active_layer, QgsVectorLayer):
                logger.debug(f"Auto-sync enabled: Setting current layer to {active_layer.name()}")
                self.comboBox_filtering_current_layer.setLayer(active_layer)

        # FIX 2026-01-14: Clear signal cache before connect/disconnect to avoid stale state
        cache_key = "QGIS.LAYER_TREE_VIEW.currentLayerChanged"
        if cache_key in self._signal_connection_states:
            logger.debug(f"Clearing cache for {cache_key} before {'connect' if state else 'disconnect'}")
            del self._signal_connection_states[cache_key]

        self.manageSignal(["QGIS", "LAYER_TREE_VIEW"], 'connect' if state else 'disconnect')
        self.setProjectVariablesEvent()

    def _update_project_layers_data(self, project_layers, project=None):
        """v3.1 Sprint 12: Simplified - update PROJECT and PROJECT_LAYERS references."""
        if project is not None:
            self.PROJECT = project
        self.PROJECT_LAYERS = project_layers
        self.has_loaded_layers = len(self.PROJECT_LAYERS) > 0

    def _determine_active_layer(self):
        """v3.1 Sprint 12: Simplified - determine active layer for UI."""
        try:
            if self.current_layer and self.current_layer.id() in self.PROJECT_LAYERS:
                layers = [l for l in self.PROJECT.mapLayersByName(
                    self.PROJECT_LAYERS[self.current_layer.id()]["infos"]["layer_name"]
                ) if l.id() == self.current_layer.id()]
                if layers:
                    return layers[0]
            if self.iface.activeLayer():
                return self.iface.activeLayer()
            if self.PROJECT_LAYERS:
                return self.PROJECT.mapLayer(list(self.PROJECT_LAYERS.keys())[0])
        except (AttributeError, KeyError, RuntimeError):
            if self.iface.activeLayer():
                return self.iface.activeLayer()
            if self.PROJECT_LAYERS:
                return self.PROJECT.mapLayer(list(self.PROJECT_LAYERS.keys())[0])
        return None

    def _activate_layer_ui(self):
        """v3.1 Sprint 12: Simplified - enable UI widgets and configure export."""
        was_empty = not self.has_loaded_layers
        self.has_loaded_layers = True
        self.set_widgets_enabled_state(True)

        # Don't populate export combobox here - will be done via projectLayersReady signal
        # self.manageSignal(["EXPORTING","LAYERS_TO_EXPORT"], 'disconnect')
        # self.exporting_populate_combobox()
        # self.manageSignal(["EXPORTING","LAYERS_TO_EXPORT"], 'connect', 'checkedItemsChanged')
        self.set_exporting_properties()

        if not self._signals_connected:
            self.connect_widgets_signals()
            self._signals_connected = True

        # FIX 2026-01-14: Force reconnect exploring button signals (IS_SELECTING, IS_TRACKING, IS_LINKING)
        # These are checkable pushbuttons that may not be properly connected via connect_widgets_signals()
        self.force_reconnect_exploring_signals()

        # Update backend indicator
        if self.PROJECT_LAYERS:
            first_layer_id = list(self.PROJECT_LAYERS.keys())[0]
            layer_props = self.PROJECT_LAYERS.get(first_layer_id, {})
            infos = layer_props.get('infos', {})
            if 'layer_provider_type' in infos:
                forced = self.forced_backends.get(first_layer_id) if hasattr(self, 'forced_backends') else None
                self._update_backend_indicator(infos['layer_provider_type'], infos.get('postgresql_connection_available'), actual_backend=forced)

        if was_empty and self.PROJECT_LAYERS:
            show_success("FilterMate", f"Plugin activated with {len(self.PROJECT_LAYERS)} vector layer(s)")

    def _refresh_layer_specific_widgets(self, layer):
        """v3.1 Sprint 12: Simplified - refresh UI widgets for active layer."""
        if not layer or not isinstance(layer, QgsVectorLayer):
            return

        if layer.id() in self.PROJECT_LAYERS:
            infos = self.PROJECT_LAYERS[layer.id()].get('infos', {})
            if 'layer_provider_type' in infos:
                forced = self.forced_backends.get(layer.id()) if hasattr(self, 'forced_backends') else None
                self._update_backend_indicator(infos['layer_provider_type'], actual_backend=forced)

        self.manage_output_name()
        self.select_tabTools_index()
        # current_layer_changed handles all widget updates including:
        # - exploring_groupbox_init()
        # - _synchronize_layer_widgets (which includes filtering_populate_layers_chekableCombobox)
        # - _reload_exploration_widgets
        self.current_layer_changed(layer)

        self.filtering_auto_current_layer_changed()

    def get_project_layers_from_app(self, project_layers, project=None):
        """v3.1 Sprint 16: Simplified - update dockwidget with layer info from app."""
        if self._filtering_in_progress:
            if project_layers: self.PROJECT_LAYERS = project_layers
            if project: self.PROJECT = project
            return
        if self._updating_layers: return
        if project_layers is None: project_layers = {}

        self._updating_layers, self._plugin_busy = True, True

        try:
            self._update_project_layers_data(project_layers, project)
            if not self.widgets_initialized:
                self._pending_layers_update = True
                return
            if self.PROJECT and self.PROJECT_LAYERS:
                if not self._signals_connected: self.connect_widgets_signals(); self._signals_connected = True
                # FIX 2026-01-14: Force reconnect exploring button signals (IS_SELECTING, IS_TRACKING, IS_LINKING)
                self.force_reconnect_exploring_signals()
                layer = self._determine_active_layer()
                self._activate_layer_ui()
                if layer: self._refresh_layer_specific_widgets(layer)
                # Emit signal after PROJECT_LAYERS is fully populated
                logger.info(f"Emitting projectLayersReady signal ({len(self.PROJECT_LAYERS)} layers)")
                self.projectLayersReady.emit()
                return
            if self.current_layer and self.current_layer.isValid():
                if not self._signals_connected: self.connect_widgets_signals(); self._signals_connected = True
                # FIX 2026-01-14: Force reconnect exploring button signals
                self.force_reconnect_exploring_signals()
                return
            # No layers - disable UI
            self.has_loaded_layers, self.current_layer = False, None
            self.disconnect_widgets_signals()
            self._signals_connected = False
            self.set_widgets_enabled_state(False)
            if self.backend_indicator_label:
                self.backend_indicator_label.setText("...")
                # Soft "mousse" style for waiting state
                self.backend_indicator_label.setStyleSheet("QLabel#label_backend_indicator { color: #7f8c8d; font-size: 8pt; font-weight: 500; padding: 2px 8px; border-radius: 10px; border: none; background-color: #f4f6f6; }")
        finally:
            self._updating_layers, self._plugin_busy = False, False

    def open_project_page(self):
        """v4.0 S18: Open GitHub project page."""
        url = self.CONFIG_DATA.get("APP", {}).get("OPTIONS", {}).get("GITHUB_PAGE", "")
        if url and url.startswith("http"): webbrowser.open(url)

    def reload_plugin(self):
        """v4.0 S18: Reload FilterMate plugin."""
        try:
            from qgis.utils import plugins; from qgis.PyQt.QtCore import QTimer
            self.save_configuration_model()
            if 'filter_mate' not in plugins: show_warning("FilterMate", self.tr("Could not reload plugin automatically.")); return
            fm = plugins['filter_mate']; self.close(); fm.pluginIsActive, fm.app = False, None; QTimer.singleShot(100, fm.run)
        except Exception as e: show_error("FilterMate", self.tr("Error reloading plugin: {0}").format(str(e)))

    def setLayerVariableEvent(self, layer=None, properties=None):
        """v4.0 Sprint 18: Emit signal to set layer variables."""
        if not self.widgets_initialized: return
        layer = layer or self.current_layer
        if is_valid_layer(layer): self.settingLayerVariable.emit(layer, properties if isinstance(properties, list) else [])

    def resetLayerVariableOnErrorEvent(self, layer, properties=None):
        """v4.0 Sprint 18: Emit signal to reset layer variables after error."""
        if not self.widgets_initialized: return
        layer = layer or self.current_layer
        if not self._is_layer_truly_deleted(layer):
            try: self.resettingLayerVariableOnError.emit(layer, properties if isinstance(properties, list) else [])
            except RuntimeError:  # Layer or widget may be deleted - expected during cleanup
                pass

    def resetLayerVariableEvent(self, layer=None, properties=None):
        """v4.0 Sprint 18: Reset layer properties to default values."""
        if not self.widgets_initialized: return
        layer = layer or self.current_layer
        if not layer or not is_valid_layer(layer) or layer.id() not in self.PROJECT_LAYERS: return
        try:
            layer_props = self.PROJECT_LAYERS[layer.id()]
            best_field = get_best_display_field(layer) or layer_props.get("infos", {}).get("primary_key_name", "")
            defaults = {"exploring": {"is_changing_all_layer_properties": True, "is_tracking": False, "is_selecting": False, "is_linking": False, "current_exploring_groupbox": "single_selection", "single_selection_expression": best_field, "multiple_selection_expression": best_field, "custom_selection_expression": best_field},
                        "filtering": {"has_layers_to_filter": False, "layers_to_filter": [], "has_combine_operator": False, "source_layer_combine_operator": "AND", "other_layers_combine_operator": "AND", "has_geometric_predicates": False, "geometric_predicates": [], "has_buffer_value": False, "buffer_value": 0.0, "buffer_value_property": False, "buffer_value_expression": "", "has_buffer_type": False, "buffer_type": "Round"}}
            props_to_save = []
            for cat, props in defaults.items(): layer_props[cat].update(props); props_to_save.extend((cat, k) for k in props)
            self.settingLayerVariable.emit(layer, props_to_save); self._synchronize_layer_widgets(layer, layer_props)
            self._update_buffer_spinbox_style(0.0); self._reset_exploring_button_states(layer_props); self._reset_filtering_button_states(layer_props)
            if should_show_message('layer_reset'):
                self.iface.messageBar().pushSuccess("FilterMate", self.tr("Layer properties reset to defaults"))
        except Exception as e: self.iface.messageBar().pushCritical("FilterMate", self.tr("Error resetting layer properties: {}").format(str(e)))

    def _reset_exploring_button_states(self, layer_props):
        """v4.0 Sprint 17: Reset exploring button visual states."""
        try:
            exp = layer_props["exploring"]
            for key, prop in [("IS_SELECTING", "is_selecting"), ("IS_TRACKING", "is_tracking"), ("IS_LINKING", "is_linking")]:
                w = self.widgets["EXPLORING"][key]["WIDGET"]
                w.blockSignals(True); w.setChecked(exp[prop]); w.blockSignals(False)
        except Exception as e:
            logger.debug(f"Error resetting exploring button states: {e}")

    def _reset_filtering_button_states(self, layer_props):
        """v3.1 Sprint 17: Reset filtering button visual states based on layer properties."""
        try:
            f = layer_props["filtering"]
            btns = {"HAS_LAYERS_TO_FILTER": f["has_layers_to_filter"], "HAS_COMBINE_OPERATOR": f["has_combine_operator"], "HAS_GEOMETRIC_PREDICATES": f["has_geometric_predicates"], "HAS_BUFFER_VALUE": f["has_buffer_value"], "HAS_BUFFER_TYPE": f["has_buffer_type"]}

            for k, v in btns.items():
                w = self.widgets["FILTERING"][k]["WIDGET"]
                w.blockSignals(True); w.setChecked(v); w.blockSignals(False)

            for combo in ["SOURCE_LAYER_COMBINE_OPERATOR", "OTHER_LAYERS_COMBINE_OPERATOR"]:
                w = self.widgets["FILTERING"][combo]["WIDGET"]
                w.blockSignals(True); w.setCurrentIndex(0); w.blockSignals(False)

            for widget_key, val, method in [("BUFFER_VALUE", 0.0, "setValue"), ("GEOMETRIC_PREDICATES", [], "setCheckedItems"), ("LAYERS_TO_FILTER", [], "setCheckedItems")]:
                w = self.widgets["FILTERING"][widget_key]["WIDGET"]
                w.blockSignals(True); getattr(w, method)(val); w.blockSignals(False)
        except Exception as e: logger.debug(f"_reset_filtering_button_states cosmetic update: {e}")

    def setProjectVariablesEvent(self):
        """v4.0 S18: Emit project variables signal."""
        if self.widgets_initialized: self.settingProjectVariables.emit()

    def _update_backend_indicator(self, provider_type, postgresql_connection_available=None, actual_backend=None):
        """v4.0 Sprint 18: Update backend indicator via BackendController."""
        # Store provider info for later use
        self._current_provider_type = provider_type
        self._current_postgresql_available = postgresql_connection_available

        # Try delegation to BackendController first
        if self._controller_integration and self._controller_integration.backend_controller:
            # Use current_layer if available, otherwise create minimal layer context
            layer = self.current_layer
            if layer and self._controller_integration.delegate_update_backend_indicator(layer, postgresql_connection_available, actual_backend):
                return

        # Fallback: Apply styling directly (v4.0 Migration Fix - restored from v2.9.42)
        if not hasattr(self, 'backend_indicator_label') or not self.backend_indicator_label:
            return

        # Determine backend type
        backend_type = actual_backend.lower() if actual_backend else provider_type.lower() if provider_type else 'unknown'
        if backend_type == 'postgres':
            backend_type = 'postgresql'

        # Backend styling configuration - Softer "mousse" colors (same as BackendController.BACKEND_STYLES)
        BACKEND_STYLES = {
            'postgresql': {'text': 'PostgreSQL', 'color': 'white', 'background': '#58d68d'},
            'spatialite': {'text': 'Spatialite', 'color': 'white', 'background': '#bb8fce'},
            'ogr': {'text': 'OGR', 'color': 'white', 'background': '#5dade2'},
            'ogr_fallback': {'text': 'OGR*', 'color': 'white', 'background': '#f0b27a'},
            'unknown': {'text': '...', 'color': '#7f8c8d', 'background': '#f4f6f6'}
        }

        style = BACKEND_STYLES.get(backend_type, BACKEND_STYLES['unknown'])
        self.backend_indicator_label.setText(style['text'])

        # Soft "mousse" style with smoother colors
        base_style = """
            QLabel#label_backend_indicator {{
                color: {style['color']};
                background-color: {style['background']};
                font-size: 8pt;
                font-weight: 500;
                padding: 2px 8px;
                border-radius: 10px;
                border: none;
            }}
            QLabel#label_backend_indicator:hover {{
                filter: brightness(1.1);
            }}
        """
        self.backend_indicator_label.setStyleSheet(base_style)
        self.backend_indicator_label.adjustSize()

    def getProjectLayersEvent(self, event):
        if self.widgets_initialized: self.gettingProjectLayers.emit()

    def closeEvent(self, event):
        """Handle dockwidget close event.

        Performs cleanup operations before closing:
        - Disconnects layer deletion signals
        - Clears layer references from widgets
        - Invalidates exploring cache
        - Emits closingPlugin signal

        Args:
            event: Qt close event to accept.

        Note:
            Always accepts the event after cleanup.
            Handles RuntimeError gracefully during shutdown.
        """
        if not self.widgets_initialized:
            event.accept()
            return

        # FIX 2026-01-19: Disconnect willBeDeleted signal before cleanup
        try: self._disconnect_feature_picker_layer_deletion() if hasattr(self, '_disconnect_feature_picker_layer_deletion') else None
        except Exception:  # May already be disconnected - expected
            pass
        try: self.comboBox_filtering_current_layer.setLayer(None) if hasattr(self, 'comboBox_filtering_current_layer') else None
        except RuntimeError:  # Widget may already be deleted - expected during shutdown
            pass
        try: self.mFeaturePickerWidget_exploring_single_selection.setLayer(None) if hasattr(self, 'mFeaturePickerWidget_exploring_single_selection') else None
        except RuntimeError:  # Widget may already be deleted - expected during shutdown
            pass
        try: self._exploring_cache.invalidate_all() if hasattr(self, '_exploring_cache') else None
        except Exception:  # Cache may be None - expected
            pass
        try: self._theme_watcher.remove_callback(self._on_qgis_theme_changed) if self._theme_watcher else None
        except Exception:  # Callback may not be registered - expected
            pass
        try: self._controller_integration.teardown() if self._controller_integration else None
        except Exception:  # Controller may already be torn down - expected
            pass

        self.closingPlugin.emit()
        event.accept()

    def get_exploring_cache_stats(self):
        """v4.0 Sprint 18: Get cache statistics."""
        return (self._controller_integration.delegate_exploring_get_cache_stats() if self._controller_integration else None) or (self._exploring_cache.get_stats() if hasattr(self, '_exploring_cache') else {})

    def invalidate_exploring_cache(self, layer_id: str = None, groupbox_type: str = None) -> None:
        """Invalidate cached exploring features data.

        Clears cached feature lists to force fresh retrieval on next access.
        Called when layer data changes (edit, filter, etc.).

        Args:
            layer_id: Specific layer ID to invalidate. If None, invalidates all.
            groupbox_type: Specific groupbox type to invalidate. If None with layer_id,
                          invalidates all groupboxes for that layer.

        Note:
            Delegates to controller if available, otherwise uses local cache.
        """
        """v4.0 Sprint 18: Invalidate exploring cache."""
        if layer_id is None and groupbox_type is None and self._controller_integration and self._controller_integration.delegate_exploring_clear_cache(): return
        if hasattr(self, '_exploring_cache'):
            self._exploring_cache.invalidate_all() if layer_id is None else (self._exploring_cache.invalidate_layer(layer_id) if groupbox_type is None else self._exploring_cache.invalidate(layer_id, groupbox_type))

    def launchTaskEvent(self, state: str, task_name: str) -> None:
        """Emit signal to launch a FilterMate task.

        Validates state and emits launchingTask signal for task execution.
        Handles special cases for user action tasks (undo, redo, unfilter, reset, export)
        which should not be blocked by protection flags.

        Args:
            state: Current state identifier.
            task_name: Task to launch ('filter', 'unfilter', 'reset', 'undo', 'redo', 'export').

        Note:
            - User action tasks bypass _filtering_in_progress protection
            - Attempts to recover current_layer from saved ID or combobox if None
            - Export task syncs HAS_LAYERS_TO_EXPORT flag before execution
        """
        # FIX 2026-01-17 v3 + 2026-01-22: Define user action tasks early (needed for recovery logic)
        user_action_tasks = ('undo', 'redo', 'unfilter', 'reset', 'export')
        is_user_action = task_name in user_action_tasks

        # FIX 2026-01-17 v3: For user actions during protection window, try to recover current_layer
        if is_user_action and not self.current_layer:

            # Try 1: Recover from saved layer ID (set during filtering)
            saved_id = getattr(self, '_saved_layer_id_before_filter', None)
            if saved_id:
                from qgis.core import QgsProject
                recovered_layer = QgsProject.instance().mapLayer(saved_id)
                if recovered_layer and recovered_layer.isValid():
                    self.current_layer = recovered_layer

            # Try 2: Recover from combobox current selection
            if not self.current_layer:
                combo_layer = self.comboBox_filtering_current_layer.currentLayer()
                if combo_layer and combo_layer.isValid():
                    self.current_layer = combo_layer

            # Try 3: Use first layer in PROJECT_LAYERS
            if not self.current_layer and self.PROJECT_LAYERS:
                first_id = list(self.PROJECT_LAYERS.keys())[0]
                from qgis.core import QgsProject
                first_layer = QgsProject.instance().mapLayer(first_id)
                if first_layer and first_layer.isValid():
                    self.current_layer = first_layer

        # FIX 2026-01-17 v3: For user actions, reset _filtering_in_progress immediately
        # This allows the action to proceed without waiting for the 1.5s protection window
        if is_user_action and getattr(self, '_filtering_in_progress', False):
            self._filtering_in_progress = False

        # FIX 2026-01-22 v2: Relaxed validation for export task
        # Export doesn't require PROJECT_LAYERS sync - it works directly with QGIS layers
        if task_name == 'export':
            if not self.widgets_initialized or not self.current_layer:
                return

            # FIX 2026-01-22 Sync HAS_LAYERS_TO_EXPORT JUST-IN-TIME before export
            # Qt restores widget states without emitting signals - sync flag to match UI
            try:
                layers_to_export = self.get_layers_to_export()
                if layers_to_export:
                    has_layers = len(layers_to_export) > 0
                    current_has_layers = self.project_props.get('EXPORTING', {}).get('HAS_LAYERS_TO_EXPORT', False)
                    if has_layers != current_has_layers:
                        self.project_props['EXPORTING']['HAS_LAYERS_TO_EXPORT'] = has_layers
                        has_layers_widget = self.widgets.get('EXPORTING', {}).get('HAS_LAYERS_TO_EXPORT', {}).get('WIDGET')
                        if has_layers_widget and hasattr(has_layers_widget, 'setChecked'):
                            has_layers_widget.blockSignals(True)
                            has_layers_widget.setChecked(has_layers)
                            has_layers_widget.blockSignals(False)
            except Exception as e:
                logger.warning(f"Failed to sync HAS_LAYERS_TO_EXPORT: {e}")

            # FIX 2026-01-22 Sync ALL export flags JUST-IN-TIME
            # Qt restores widget states without emitting signals - sync all flags to match UI
            try:
                exporting_props = self.project_props.get('EXPORTING', {})

                # Sync HAS_DATATYPE_TO_EXPORT
                datatype_widget = self.widgets.get('EXPORTING', {}).get('DATATYPE_TO_EXPORT', {}).get('WIDGET')
                if datatype_widget:
                    current_datatype = datatype_widget.currentText()
                    if current_datatype and current_datatype.strip() and not exporting_props.get('HAS_DATATYPE_TO_EXPORT', False):
                        self.project_props['EXPORTING']['HAS_DATATYPE_TO_EXPORT'] = True
                        self.project_props['EXPORTING']['DATATYPE_TO_EXPORT'] = current_datatype
                        has_datatype_widget = self.widgets.get('EXPORTING', {}).get('HAS_DATATYPE_TO_EXPORT', {}).get('WIDGET')
                        if has_datatype_widget and hasattr(has_datatype_widget, 'setChecked'):
                            has_datatype_widget.blockSignals(True)
                            has_datatype_widget.setChecked(True)
                            has_datatype_widget.blockSignals(False)

                # Sync HAS_OUTPUT_FOLDER_TO_EXPORT
                output_folder_widget = self.widgets.get('EXPORTING', {}).get('OUTPUT_FOLDER_TO_EXPORT', {}).get('WIDGET')
                if output_folder_widget:
                    current_folder = output_folder_widget.text() if hasattr(output_folder_widget, 'text') else ''
                    if current_folder and current_folder.strip() and not exporting_props.get('HAS_OUTPUT_FOLDER_TO_EXPORT', False):
                        self.project_props['EXPORTING']['HAS_OUTPUT_FOLDER_TO_EXPORT'] = True
                        self.project_props['EXPORTING']['OUTPUT_FOLDER_TO_EXPORT'] = current_folder
                        has_folder_widget = self.widgets.get('EXPORTING', {}).get('HAS_OUTPUT_FOLDER_TO_EXPORT', {}).get('WIDGET')
                        if has_folder_widget and hasattr(has_folder_widget, 'setChecked'):
                            has_folder_widget.blockSignals(True)
                            has_folder_widget.setChecked(True)
                            has_folder_widget.blockSignals(False)

                # Sync HAS_PROJECTION_TO_EXPORT
                projection_widget = self.widgets.get('EXPORTING', {}).get('PROJECTION_TO_EXPORT', {}).get('WIDGET')
                if projection_widget and hasattr(projection_widget, 'crs'):
                    crs = projection_widget.crs()
                    if crs and crs.isValid() and not exporting_props.get('HAS_PROJECTION_TO_EXPORT', False):
                        self.project_props['EXPORTING']['HAS_PROJECTION_TO_EXPORT'] = True
                        self.project_props['EXPORTING']['PROJECTION_TO_EXPORT'] = crs.toWkt()
                        has_proj_widget = self.widgets.get('EXPORTING', {}).get('HAS_PROJECTION_TO_EXPORT', {}).get('WIDGET')
                        if has_proj_widget and hasattr(has_proj_widget, 'setChecked'):
                            has_proj_widget.blockSignals(True)
                            has_proj_widget.setChecked(True)
                            has_proj_widget.blockSignals(False)

                # Sync HAS_STYLES_TO_EXPORT
                styles_widget = self.widgets.get('EXPORTING', {}).get('STYLES_TO_EXPORT', {}).get('WIDGET')
                if styles_widget:
                    current_style = styles_widget.currentText() if hasattr(styles_widget, 'currentText') else ''
                    if current_style and current_style.strip() and not exporting_props.get('HAS_STYLES_TO_EXPORT', False):
                        self.project_props['EXPORTING']['HAS_STYLES_TO_EXPORT'] = True
                        self.project_props['EXPORTING']['STYLES_TO_EXPORT'] = current_style
                        has_styles_widget = self.widgets.get('EXPORTING', {}).get('HAS_STYLES_TO_EXPORT', {}).get('WIDGET')
                        if has_styles_widget and hasattr(has_styles_widget, 'setChecked'):
                            has_styles_widget.blockSignals(True)
                            has_styles_widget.setChecked(True)
                            has_styles_widget.blockSignals(False)
            except Exception as e:
                logger.warning(f"Failed to sync export flags: {e}")
            self.launchingTask.emit(task_name)
            return

        # Standard validation for other tasks (filter, undo, redo, etc.)
        if not self.widgets_initialized or not self.current_layer or self.current_layer.id() not in self.PROJECT_LAYERS:
            logger.warning(f"launchTaskEvent BLOCKED: widgets_initialized={self.widgets_initialized}, current_layer={self.current_layer is not None}, in_PROJECT_LAYERS={self.current_layer.id() in self.PROJECT_LAYERS if self.current_layer else False}")
            return

        self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["layers_to_filter"] = self.get_layers_to_filter()
        self.setLayerVariableEvent(self.current_layer, [("filtering", "layers_to_filter")])
        self.launchingTask.emit(task_name)

    def _setup_truncation_tooltips(self):
        """v4.0 Sprint 17: Setup tooltips for widgets with truncated text."""
        widgets = [
            (self.comboBox_filtering_current_layer, 'currentTextChanged', lambda: self._update_combo_tooltip(self.comboBox_filtering_current_layer)),
            (self.checkableComboBoxLayer_filtering_layers_to_filter, 'checkedItemsChanged', lambda: self._update_checkable_combo_tooltip(self.checkableComboBoxLayer_filtering_layers_to_filter)),
            (self.checkableComboBoxLayer_exporting_layers, 'checkedItemsChanged', lambda: [self._update_checkable_combo_tooltip(self.checkableComboBoxLayer_exporting_layers), self._update_export_buttons_state()]),
            (self.mFieldExpressionWidget_exploring_single_selection, 'fieldChanged', lambda: self._update_expression_tooltip(self.mFieldExpressionWidget_exploring_single_selection)),
            (self.mFieldExpressionWidget_exploring_multiple_selection, 'fieldChanged', lambda: self._update_expression_tooltip(self.mFieldExpressionWidget_exploring_multiple_selection)),
            (self.mFieldExpressionWidget_exploring_custom_selection, 'fieldChanged', lambda: self._update_expression_tooltip(self.mFieldExpressionWidget_exploring_custom_selection)),
            (self.mFeaturePickerWidget_exploring_single_selection, 'featureChanged', lambda: self._update_feature_picker_tooltip(self.mFeaturePickerWidget_exploring_single_selection))]
        for w, sig, slot in widgets:
            if w and hasattr(w, sig):
                try: getattr(w, sig).connect(slot); slot()
                except Exception:  # Signal may already be connected - expected
                    pass

    def _update_combo_tooltip(self, combo):
        """v4.0 Sprint 17: Update tooltip for combo widget."""
        if not combo or not hasattr(combo, 'currentText'): return
        try:
            t = combo.currentText()
            combo.setToolTip(t if t and len(t) > 30 else QCoreApplication.translate("FilterMate", "Current layer: {0}").format(t) if t else QCoreApplication.translate("FilterMate", "No layer selected"))
        except Exception:  # Tooltip update is cosmetic - non-critical
            pass

    def _update_checkable_combo_tooltip(self, combo):
        """v4.0 Sprint 17: Update tooltip for checkable combo showing selected items."""
        if not combo or not hasattr(combo, 'checkedItems'): return
        try:
            items = combo.checkedItems()
            t = "\n".join([i.text() for i in items if hasattr(i, 'text')]) if items else ""
            combo.setToolTip(QCoreApplication.translate("FilterMate", "Selected layers:\n{0}").format(t) if t else QCoreApplication.translate("FilterMate", "No layers selected"))
        except Exception:  # Tooltip update is cosmetic - non-critical
            pass

    def _update_export_buttons_state(self):
        """
        v4.0 Sprint 17: Update export buttons based on layer selection.

        NOTE: pushButton_checkable_exporting_output_folder and pushButton_checkable_exporting_zip
        are ALWAYS enabled (can be checked/unchecked anytime). They are excluded from this logic.
        Only their associated widgets (lineEdit, checkBox) should be controlled by toggle state.
        """
        # These buttons are always enabled - no state update needed here
        # The toggle state controls their associated widgets, not the buttons themselves

    def _update_expression_tooltip(self, expr_widget):
        """v4.0 Sprint 17: Update tooltip for expression widget."""
        if not expr_widget or not hasattr(expr_widget, 'expression'): return
        try:
            e = expr_widget.expression()
            if e and len(e) > 40: e = e.replace(' AND ', '\nAND ').replace(' OR ', '\nOR ')
            expr_widget.setToolTip(QCoreApplication.translate("FilterMate", "Expression:\n{0}" if e and len(e) > 40 else "Expression: {0}").format(e) if e else QCoreApplication.translate("FilterMate", "No expression defined"))
        except Exception:  # Tooltip update is cosmetic - non-critical
            pass

    def _update_feature_picker_tooltip(self, picker):
        """v4.0 Sprint 17: Update tooltip for feature picker widget."""
        if not picker: return
        try:
            if hasattr(picker, 'displayExpression'):
                de = picker.displayExpression()
                if de and len(de) > 30: picker.setToolTip(QCoreApplication.translate("FilterMate", "Display expression: {0}").format(de)); return
            # FIX 2026-01-22: Also consider saved FID for tooltip accuracy
            saved_fid = getattr(self, '_last_single_selection_fid', None)
            saved_layer_id = getattr(self, '_last_single_selection_layer_id', None)
            f = None
            if saved_fid is not None and self.current_layer and saved_layer_id == self.current_layer.id():
                try:
                    f = self.current_layer.getFeature(saved_fid)
                    if not f or not f.isValid():
                        f = None
                except Exception as e:
                    logger.debug(f"Ignored in saved feature retrieval for FID {saved_fid}: {e}")
                    f = None
            if f is None and hasattr(picker, 'feature'):
                f = picker.feature()
            if f and f.isValid() and f.attributes():
                picker.setToolTip(QCoreApplication.translate("FilterMate", "Feature ID: {0}\nFirst attribute: {1}").format(f.id(), f.attributes()[0]))
        except Exception:  # Tooltip update is cosmetic - non-critical
            pass

    def retranslate_dynamic_tooltips(self):
        """Refresh all dynamic tooltips after a locale change."""
        if not getattr(self, 'widgets_initialized', False):
            return

        tooltip_refreshers = [
            lambda: self._update_combo_tooltip(self.comboBox_filtering_current_layer),
            lambda: self._update_checkable_combo_tooltip(self.checkableComboBoxLayer_filtering_layers_to_filter),
            lambda: self._update_checkable_combo_tooltip(self.checkableComboBoxLayer_exporting_layers),
            lambda: self._update_expression_tooltip(self.mFieldExpressionWidget_exploring_single_selection),
            lambda: self._update_expression_tooltip(self.mFieldExpressionWidget_exploring_multiple_selection),
            lambda: self._update_expression_tooltip(self.mFieldExpressionWidget_exploring_custom_selection),
            lambda: self._update_feature_picker_tooltip(self.mFeaturePickerWidget_exploring_single_selection)
        ]

        for refresh in tooltip_refreshers:
            try:
                refresh()
            except Exception as error:
                logger.debug(f"FilterMate: Could not refresh dynamic tooltip: {error}")

    def _setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts: F5=reload layers, Ctrl+Z=undo, Ctrl+Y=redo."""
        from qgis.PyQt.QtWidgets import QShortcut
        from qgis.PyQt.QtGui import QKeySequence
        self._reload_shortcut = QShortcut(QKeySequence("F5"), self); self._reload_shortcut.activated.connect(self._on_reload_layers_shortcut); self._reload_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._undo_shortcut = QShortcut(QKeySequence.Undo, self); self._undo_shortcut.activated.connect(self._on_undo_shortcut); self._undo_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._redo_shortcut = QShortcut(QKeySequence.Redo, self); self._redo_shortcut.activated.connect(self._on_redo_shortcut); self._redo_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        logger.debug("Keyboard shortcuts initialized: F5 = Reload layers, Ctrl+Z = Undo, Ctrl+Y = Redo")

    def _on_reload_layers_shortcut(self):
        """Handle F5 shortcut to reload layers."""
        if hasattr(self, 'backend_indicator_label') and self.backend_indicator_label:
            self.backend_indicator_label.setText("⟳"); self.backend_indicator_label.setStyleSheet("QLabel#label_backend_indicator { color: #3498db; font-size: 9pt; font-weight: 600; padding: 3px 10px; border-radius: 12px; border: none; background-color: #e8f4fc; }")
        self.launchingTask.emit('reload_layers')

    def _on_undo_shortcut(self):
        """Handle Ctrl+Z to undo last filter."""
        uw = self.widgets.get("ACTION", {}).get("UNDO_FILTER", {}).get("WIDGET")
        if uw and uw.isEnabled(): self.launchTaskEvent(False, 'undo')

    def _on_redo_shortcut(self):
        """Handle Ctrl+Y to redo last filter."""
        rw = self.widgets.get("ACTION", {}).get("REDO_FILTER", {}).get("WIDGET")
        if rw and rw.isEnabled(): self.launchTaskEvent(False, 'redo')

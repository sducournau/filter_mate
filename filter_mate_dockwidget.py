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
from osgeo import ogr

# Import logging for error handling
from .infrastructure.logging import get_app_logger
logger = get_app_logger()

# v4.0 Sprint 6: Widget configuration management
from .ui.managers import ConfigurationManager
from qgis.PyQt import QtGui, QtWidgets, QtCore
from qgis.PyQt.QtCore import (
    Qt,
    QCoreApplication,
    QMetaMethod,
    QObject,
    pyqtSignal,
    QTimer
)
from qgis.PyQt.QtGui import QColor, QFont
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsExpression,
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsLayerItem,
    QgsProject,
    QgsProperty,
    QgsPropertyDefinition,
    QgsRectangle,
    QgsVectorLayer
)
from qgis.gui import (
    QgsCheckableComboBox,
    QgsFeaturePickerWidget,
    QgsFieldComboBox,
    QgsFieldExpressionWidget,
    QgsMapLayerComboBox,
    QgsProjectionSelectionWidget
)

# Compatibility layer for proxy model classes (moved from qgis.core to qgis.gui in QGIS 3.30+)
try: from qgis.gui import QgsMapLayerProxyModel
except ImportError:
    try: from qgis.core import QgsMapLayerProxyModel
    except ImportError:
        class QgsMapLayerProxyModel: VectorLayer = 1

try: from qgis.gui import QgsFieldProxyModel
except ImportError:
    try: from qgis.core import QgsFieldProxyModel
    except ImportError:
        class QgsFieldProxyModel: AllTypes = 0
from qgis.utils import iface

import webbrowser
from .ui.widgets import QgsCheckableComboBoxFeaturesListPickerWidget, QgsCheckableComboBoxLayer
from .ui.widgets.json_view.model import JsonModel
from .ui.widgets.json_view.view import JsonView

# Object safety and layer utilities (migrated to infrastructure)
from .infrastructure.utils import is_layer_valid as is_valid_layer
from .infrastructure.utils import (
    get_best_display_field,
    is_layer_source_available
)
from .core.domain.exceptions import SignalStateChangeError
from .infrastructure.constants import PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR, get_geometry_type_string
from .ui.styles import StyleLoader, QGISThemeWatcher
from .infrastructure.feedback import show_info, show_warning, show_error, show_success

# Config helpers (migrated to config/)
from .config.config import get_optimization_thresholds
from .infrastructure.config import set_config_value

from .infrastructure.cache import ExploringFeaturesCache
from .filter_mate_dockwidget_base import Ui_FilterMateDockWidgetBase

# Import async expression evaluation for large layers (v2.5.10)
# EPIC-1: Migrated to core/tasks/
try:
    from .core.tasks import get_expression_manager
    ASYNC_EXPRESSION_AVAILABLE = True
except ImportError:
    ASYNC_EXPRESSION_AVAILABLE = False; get_expression_manager = None

# CRS utilities (migrated to core/geometry/)
try: from .core.geometry.crs_utils import is_geographic_crs, get_optimal_metric_crs, DEFAULT_METRIC_CRS; CRS_UTILS_AVAILABLE = True
except ImportError: CRS_UTILS_AVAILABLE = False; DEFAULT_METRIC_CRS = "EPSG:3857"

# Icon utilities for dark mode (migrated to ui/)
try: from .ui.icons import IconThemeManager, get_themed_icon; ICON_THEME_AVAILABLE = True
except ImportError: ICON_THEME_AVAILABLE = False

# UI configuration system
try: from .ui.config import UIConfig; from .ui import widget_utils as ui_utils; UI_CONFIG_AVAILABLE = True
except ImportError: UI_CONFIG_AVAILABLE = False

# MVC Controllers
try: from .ui.controllers.integration import ControllerIntegration; from .adapters.app_bridge import get_filter_service, is_initialized as is_hexagonal_initialized; CONTROLLERS_AVAILABLE = True
except ImportError: CONTROLLERS_AVAILABLE = False; get_filter_service = None; is_hexagonal_initialized = lambda: False

# Layout Managers
try: from .ui.layout import SplitterManager, DimensionsManager, SpacingManager, ActionBarManager; LAYOUT_MANAGERS_AVAILABLE = True
except ImportError: LAYOUT_MANAGERS_AVAILABLE = False; SplitterManager = DimensionsManager = SpacingManager = ActionBarManager = None

# Style Managers
try: from .ui.styles import ThemeManager, IconManager, ButtonStyler; STYLE_MANAGERS_AVAILABLE = True
except ImportError: STYLE_MANAGERS_AVAILABLE = False; ThemeManager = IconManager = ButtonStyler = None

class FilterMateDockWidget(QtWidgets.QDockWidget, Ui_FilterMateDockWidgetBase):

    closingPlugin = pyqtSignal()
    launchingTask = pyqtSignal(str)
    currentLayerChanged = pyqtSignal()
    widgetsInitialized = pyqtSignal()

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
        self._expression_debounce_timer = QTimer()
        self._expression_debounce_timer.setSingleShot(True); self._expression_debounce_timer.setInterval(450)
        self._expression_debounce_timer.timeout.connect(self._execute_debounced_expression_change)
        self._pending_expression_change = self._last_expression_change_source = None
        self._expression_cache, self._expression_cache_max_age, self._expression_cache_max_size = {}, 60.0, 100
        thresholds = get_optimization_thresholds(ENV_VARS)
        self._async_expression_threshold = thresholds['async_expression_threshold']
        self._expression_manager = get_expression_manager() if ASYNC_EXPRESSION_AVAILABLE else None
        self._pending_async_evaluation, self._expression_loading, self._configuration_manager = None, False, None
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
                except: pass
        self._theme_manager = self._icon_manager = self._button_styler = None
        if STYLE_MANAGERS_AVAILABLE:
            try: self._theme_manager, self._icon_manager, self._button_styler = ThemeManager(self), IconManager(self), ButtonStyler(self)
            except: pass
        
        # Controllers
        self._controller_integration = None
        if CONTROLLERS_AVAILABLE:
            try:
                filter_service = get_filter_service() if is_hexagonal_initialized() and get_filter_service else None
                self._controller_integration = ControllerIntegration(dockwidget=self, filter_service=filter_service, enabled=True)
            except: pass
        
        self._last_single_selection_fid = self._last_single_selection_layer_id = None
        self._last_multiple_selection_fids = self._last_multiple_selection_layer_id = None
        self.predicates = self.project_props = self.layer_properties_tuples_dict = self.export_properties_tuples_dict = None
        self.buffer_property_has_been_init = False
        self.json_template_project_exporting = '{"has_layers_to_export":false,"layers_to_export":[],"has_projection_to_export":false,"projection_to_export":"","has_styles_to_export":false,"styles_to_export":"","has_datatype_to_export":false,"datatype_to_export":"","datatype_to_export":"","has_output_folder_to_export":false,"output_folder_to_export":"","has_zip_to_export":false,"zip_to_export":"","batch_output_folder":false,"batch_zip":false }'
        self.pending_config_changes, self.config_changes_pending = [], False
        if ICON_THEME_AVAILABLE:
            try: IconThemeManager.set_theme(StyleLoader.detect_qgis_theme())
            except: pass
        self.setupUi(self)
        self.setupUiCustom()
        self.manage_ui_style()
        try: self.manage_interactions()
        except Exception as e: logger.error(f"Error in manage_interactions: {e}")

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
        """v4.0 S16: Manage signal connection/disconnection."""
        if not isinstance(widget_path, list) or len(widget_path) != 2:
            raise SignalStateChangeError(None, widget_path, 'Incorrect input parameters')
        widget_object, state = self.widgets[widget_path[0]][widget_path[1]], None
        signals_to_process = [(s[0], s[-1]) for s in widget_object["SIGNALS"] 
                              if s[-1] is not None and (custom_signal_name is None or s[0] == custom_signal_name)]
        for signal_name, func in signals_to_process:
            state_key, cached = f"{widget_path[0]}.{widget_path[1]}.{signal_name}", self._signal_connection_states.get(f"{widget_path[0]}.{widget_path[1]}.{signal_name}")
            if (custom_action == 'connect' and cached is True) or (custom_action == 'disconnect' and cached is False):
                state = cached; continue
            state = self.changeSignalState(widget_path, signal_name, func, custom_action)
            self._signal_connection_states[state_key] = state
        return True if state is None and widget_object["SIGNALS"] else state
        if state is None: raise SignalStateChangeError(state, widget_path)

    def changeSignalState(self, widget_path, signal_name, func, custom_action=None):
        """v4.0 S16: Change signal connection state."""
        if not isinstance(widget_path, list) or len(widget_path) != 2: raise SignalStateChangeError(None, widget_path)
        widget = self.widgets[widget_path[0]][widget_path[1]]["WIDGET"]
        if not hasattr(widget, signal_name): raise SignalStateChangeError(None, widget_path)
        is_ltv = widget_path == ["QGIS", "LAYER_TREE_VIEW"]
        state, signal = (self._layer_tree_view_signal_connected if is_ltv else widget.isSignalConnected(self.getSignal(widget, signal_name))), getattr(widget, signal_name)
        should_connect = (custom_action == 'connect' and not state) or (custom_action is None and not state)
        should_disconnect = (custom_action == 'disconnect' and state) or (custom_action is None and state)
        try:
            if should_disconnect: signal.disconnect(func)
            elif should_connect: signal.connect(func)
        except TypeError: pass
        if is_ltv: self._layer_tree_view_signal_connected = should_connect
        return self._layer_tree_view_signal_connected if is_ltv else widget.isSignalConnected(self.getSignal(widget, signal_name))

    def reset_multiple_checkable_combobox(self):
        """v4.0 S18: Reset and recreate multiple checkable combobox widget."""
        try:
            layout = self.horizontalLayout_exploring_multiple_feature_picker
            if layout.count() > 0 and (item := layout.itemAt(0)) and item.widget():
                layout.removeWidget(item.widget()); item.widget().deleteLater()
            if hasattr(self, 'checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection') and self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection:
                try: self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection.reset(); self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection.close(); self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection.deleteLater()
                except (RuntimeError, AttributeError): pass
            # Recreate the widget
            self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection = QgsCheckableComboBoxFeaturesListPickerWidget(self.CONFIG_DATA, self)
            if self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection:
                layout.insertWidget(0, self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection, 1); layout.update()
                self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"] = {"TYPE": "CustomCheckableFeatureComboBox", "WIDGET": self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection,
                    "SIGNALS": [("updatingCheckedItemList", self.exploring_features_changed), ("filteringCheckedItemList", self.exploring_source_params_changed)]}
        except Exception: pass

    def _fix_toolbox_icons(self):
        """v4.0 S18: Fix toolBox_tabTools icons with absolute paths."""
        for idx, icon_file in {0: "filter_multi.png", 1: "save.png", 2: "parameters.png"}.items():
            p = os.path.join(self.plugin_dir, "icons", icon_file)
            if os.path.exists(p): self.toolBox_tabTools.setItemIcon(idx, get_themed_icon(p) if ICON_THEME_AVAILABLE else QtGui.QIcon(p))


    def setupUiCustom(self):
        """v4.0 Sprint 15: Setup custom UI - splitter, dimensions, tabs, icons, tooltips."""
        # CRITICAL: Create all custom widgets FIRST (before configure_widgets() references them)
        self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection = QgsCheckableComboBoxFeaturesListPickerWidget(self.CONFIG_DATA, self)
        self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection.setMinimumHeight(28)
        self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection.show()
        logger.debug(f"Created multiple selection widget: {self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection}")
        
        # Create custom combobox widgets early so configure_widgets() can reference them
        from .ui.widgets.custom_widgets import QgsCheckableComboBoxLayer
        self.checkableComboBoxLayer_filtering_layers_to_filter = QgsCheckableComboBoxLayer(self.dockWidgetContents)
        self.checkableComboBoxLayer_filtering_layers_to_filter.setMinimumHeight(26)
        self.checkableComboBoxLayer_filtering_layers_to_filter.show()
        logger.debug(f"Created filtering layers widget: {self.checkableComboBoxLayer_filtering_layers_to_filter}")
        
        self.checkableComboBoxLayer_exporting_layers = QgsCheckableComboBoxLayer(self.dockWidgetContents)
        self.checkableComboBoxLayer_exporting_layers.setMinimumHeight(26)
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
        self._setup_filtering_tab_widgets()
        self._setup_exporting_tab_widgets()
        if 'CURRENT_PROJECT' in self.CONFIG_DATA:
            self.project_props = self.CONFIG_DATA["CURRENT_PROJECT"]
        self.manage_configuration_model()
        self.dockwidget_widgets_configuration()
        self._load_all_pushbutton_icons()
        self._setup_truncation_tooltips()
    
    def _load_all_pushbutton_icons(self):
        """v4.0 S16: Load icons from config."""
        try:
            pb_cfg = self.CONFIG_DATA.get("APP", {}).get("DOCKWIDGET", {}).get("PushButton", {})
            icons, sizes = pb_cfg.get("ICONS", {}), pb_cfg.get("ICONS_SIZES", {})
            sz_act, sz_oth = sizes.get("ACTION", {}).get("value", 24), sizes.get("OTHERS", {}).get("value", 20)
            if not icons: return
            for grp in ["ACTION", "EXPLORING", "FILTERING", "EXPORTING"]:
                sz = sz_act if grp == "ACTION" else sz_oth
                for name, ico_file in icons.get(grp, {}).items():
                    attr = self._get_widget_attr_name(grp, name)
                    if hasattr(self, attr):
                        w, p = getattr(self, attr), os.path.join(self.plugin_dir, "icons", ico_file)
                        if os.path.exists(p):
                            w.setIcon(get_themed_icon(p) if ICON_THEME_AVAILABLE else QtGui.QIcon(p))
                            w.setIconSize(QtCore.QSize(sz, sz))
        except Exception: pass
    
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
            self.main_splitter.setStyleSheet(f"QSplitter::handle:vertical{{background-color:#d0d0d0;height:{hw-2}px;margin:2px {hm}px;border-radius:{(hw-2)//2}px;}}QSplitter::handle:vertical:hover{{background-color:#3498db;}}")
            self._apply_splitter_frame_policies()
            self.main_splitter.setStretchFactor(0, cfg.get('exploring_stretch', 2))
            self.main_splitter.setStretchFactor(1, cfg.get('toolset_stretch', 5))
            self._set_initial_splitter_sizes()
        except Exception: self.main_splitter = None
    
    def _apply_splitter_frame_policies(self):
        """v4.0 S16: Apply frame size policies."""
        from .ui.config import UIConfig
        from qgis.PyQt.QtWidgets import QSizePolicy as SP
        pm = {'Fixed':SP.Fixed,'Minimum':SP.Minimum,'Maximum':SP.Maximum,'Preferred':SP.Preferred,'Expanding':SP.Expanding,'MinimumExpanding':SP.MinimumExpanding,'Ignored':SP.Ignored}
        for fn, defs in [('frame_exploring',('Preferred','Minimum')), ('frame_toolset',('Preferred','Expanding'))]:
            if hasattr(self, fn):
                cfg = UIConfig.get_config(fn) or {}
                getattr(self, fn).setSizePolicy(pm.get(cfg.get('size_policy_h', defs[0]), SP.Preferred), pm.get(cfg.get('size_policy_v', defs[1]), SP.Preferred))
    
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
        """
        if self._dimensions_manager is not None:
            try: self._dimensions_manager.apply(); return
            except Exception: pass
        try:
            self._apply_dockwidget_dimensions(); self._apply_widget_dimensions(); self._apply_frame_dimensions(); self._harmonize_checkable_pushbuttons()
            if self._spacing_manager is not None:
                try: self._spacing_manager.apply()
                except Exception: self._apply_layout_spacing(); self._harmonize_spacers(); self._adjust_row_spacing()
            else: self._apply_layout_spacing(); self._harmonize_spacers(); self._adjust_row_spacing()
            self._apply_qgis_widget_dimensions(); self._align_key_layouts()
            logger.info("Successfully applied dynamic dimensions to all widgets")
        except Exception as e:
            logger.error(f"Error applying dynamic dimensions: {e}")
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
        min_w, min_h = UIConfig.get_config('dockwidget','min_width'), UIConfig.get_config('dockwidget','min_height')
        pref_w, pref_h = UIConfig.get_config('dockwidget','preferred_width'), UIConfig.get_config('dockwidget','preferred_height')
        if min_w and min_h:
            self.setMinimumSize(QSize(min_w, min_h))
            logger.debug(f"Applied dockwidget minimum size: {min_w}x{min_h}px")
        if pref_w and pref_h and (self.size().width() > pref_w or self.size().height() > pref_h):
            self.resize(pref_w, pref_h)
            logger.debug(f"Resized dockwidget to preferred size: {pref_w}x{pref_h}px")
    
    def _apply_widget_dimensions(self):
        """
        Apply dimensions to standard Qt widgets (ComboBox, LineEdit, SpinBox, GroupBox).
        
        Reads dimensions from UIConfig and applies them to all relevant widgets
        using findChildren() for batch processing.
        """
        from .ui.config import UIConfig
        from qgis.PyQt.QtWidgets import QComboBox, QLineEdit, QDoubleSpinBox, QSpinBox, QGroupBox
        combo_h = UIConfig.get_config('combobox', 'height')
        input_h = UIConfig.get_config('input', 'height')
        gb_min_h = UIConfig.get_config('groupbox', 'min_height')
        for combo in self.findChildren(QComboBox):
            combo.setMinimumHeight(combo_h)
            combo.setMaximumHeight(combo_h)
            combo.setSizePolicy(combo.sizePolicy().horizontalPolicy(), QtWidgets.QSizePolicy.Fixed)
        for le in self.findChildren(QLineEdit):
            le.setMinimumHeight(input_h)
            le.setMaximumHeight(input_h)
            le.setSizePolicy(le.sizePolicy().horizontalPolicy(), QtWidgets.QSizePolicy.Fixed)
        for spinbox in self.findChildren(QDoubleSpinBox) + self.findChildren(QSpinBox):
            spinbox.setMinimumHeight(input_h)
            spinbox.setMaximumHeight(input_h)
            spinbox.setSizePolicy(spinbox.sizePolicy().horizontalPolicy(), QtWidgets.QSizePolicy.Fixed)
        for gb in self.findChildren(QGroupBox):
            gb.setMinimumHeight(gb_min_h)
        logger.debug(f"Applied widget dimensions: ComboBox={combo_h}px, Input={input_h}px")
    
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
            key_cfg = UIConfig.get_config('key_button') or {}
            button_spacing = key_cfg.get('spacing', 2)
            # Apply spacing to exploring layouts
            for name in ['verticalLayout_exploring_single_selection', 'verticalLayout_exploring_multiple_selection', 'verticalLayout_exploring_custom_selection']:
                if hasattr(self, name): getattr(self, name).setSpacing(layout_spacing)
            # Apply button spacing to key layouts
            for name in ['verticalLayout_filtering_keys', 'verticalLayout_exporting_keys', 'verticalLayout_exploring_content']:
                if hasattr(self, name): getattr(self, name).setSpacing(button_spacing)
            # Apply content spacing
            for name in ['verticalLayout_filtering_values', 'verticalLayout_exporting_values']:
                if hasattr(self, name): getattr(self, name).setSpacing(content_spacing)
            logger.debug(f"Applied harmonized layout spacing: {layout_spacing}px")
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
        Apply dimensions to QGIS custom widgets.
        
        Sets heights for QgsFeaturePickerWidget, QgsFieldExpressionWidget, 
        QgsProjectionSelectionWidget, and forces QgsPropertyOverrideButton to exact 22px.
        """
        try:
            from qgis.PyQt.QtWidgets import QSizePolicy
            from qgis.gui import QgsPropertyOverrideButton
            from .ui.config import UIConfig
            cb_h = UIConfig.get_config('combobox', 'height') or 24
            for cls in [QgsFeaturePickerWidget, QgsFieldExpressionWidget, QgsProjectionSelectionWidget, QgsMapLayerComboBox, QgsFieldComboBox, QgsCheckableComboBox]:
                for w in self.findChildren(cls): w.setMinimumHeight(cb_h); w.setMaximumHeight(cb_h); w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            for w in self.findChildren(QgsPropertyOverrideButton): w.setFixedSize(22, 22); w.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            logger.debug(f"Applied QGIS widget dimensions: ComboBox={cb_h}px, Input={cb_h}px")
        except Exception as e:
            logger.debug(f"Could not apply dimensions to QGIS widgets: {e}")
    
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
            margins = UIConfig.get_config('layout', 'margins_frame') or {'left': 8, 'top': 8, 'right': 8, 'bottom': 10}
            left, top, right, bottom = margins.get('left', 8), margins.get('top', 8), margins.get('right', 8), margins.get('bottom', 10)
            key_cfg = UIConfig.get_config('key_button') or {}
            button_spacing = key_cfg.get('spacing', 2)
            widget_keys_config = UIConfig.get_config('widget_keys') or {}
            widget_keys_padding = widget_keys_config.get('padding', 2)
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
        self.frame_header.setMaximumHeight(22); self.frame_header.setMinimumHeight(18)
        hl = QtWidgets.QHBoxLayout(self.frame_header)
        hl.setContentsMargins(10,1,10,1); hl.setSpacing(8)
        hl.addSpacerItem(QtWidgets.QSpacerItem(40,10,QtWidgets.QSizePolicy.Expanding,QtWidgets.QSizePolicy.Minimum))
        self.plugin_title_label = None
        bb = "color:white;font-size:9pt;font-weight:600;padding:3px 10px;border-radius:12px;border:none;"
        self.favorites_indicator_label = self._create_indicator_label("label_favorites_indicator","★",bb+"background-color:#f39c12;",bb+"background-color:#d68910;","★ Favorites\nClick to manage",self._on_favorite_indicator_clicked,35)
        hl.addWidget(self.favorites_indicator_label)
        self.backend_indicator_label = self._create_indicator_label("label_backend_indicator","OGR" if self.has_loaded_layers else "...",bb+"background-color:#3498db;",bb+"background-color:#2980b9;","Click to change backend",self._on_backend_indicator_clicked,40)
        hl.addWidget(self.backend_indicator_label)
        self.forced_backends = {}
        if hasattr(self,'verticalLayout_8'): self.verticalLayout_8.insertWidget(0,self.frame_header)
    
    def _create_indicator_label(self, name, text, style, hover_style, tooltip, click_handler, min_width):
        """v4.0 S16: Create indicator label."""
        lbl = QtWidgets.QLabel(self.frame_header)
        lbl.setObjectName(name); lbl.setText(text); lbl.setStyleSheet(f"QLabel#{name}{{{style}}}QLabel#{name}:hover{{{hover_style}}}")
        lbl.setAlignment(Qt.AlignCenter); lbl.setMinimumWidth(min_width); lbl.setMaximumHeight(20)
        lbl.setCursor(Qt.PointingHandCursor); lbl.setToolTip(tooltip); lbl.mousePressEvent = click_handler
        return lbl
    
    def _on_backend_indicator_clicked(self, event):
        """v4.0 Sprint 19: → BackendController."""
        if self._controller_integration and self._controller_integration.backend_controller:
            self._controller_integration.delegate_handle_backend_click()
        else:
            logger.warning("Backend controller unavailable")

    def _on_favorite_indicator_clicked(self, event):
        """v4.0 S16: → FavoritesController."""
        if self._favorites_ctrl:
            self._favorites_ctrl.handle_indicator_clicked()
    
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
            show_warning("FilterMate", "Favorites manager not available")
    
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
            self.favorites_indicator_label.setToolTip(f"★ {cnt} Favorites saved\nClick to apply or manage")
            self.favorites_indicator_label.setStyleSheet("QLabel#label_favorites_indicator{color:white;font-size:9pt;font-weight:600;padding:3px 10px;border-radius:12px;border:none;background-color:#f39c12;}QLabel#label_favorites_indicator:hover{background-color:#d68910;}")
        else:
            self.favorites_indicator_label.setText("★")
            self.favorites_indicator_label.setToolTip("★ No favorites saved\nClick to add current filter")
            self.favorites_indicator_label.setStyleSheet("QLabel#label_favorites_indicator{color:#95a5a6;font-size:9pt;font-weight:600;padding:3px 10px;border-radius:12px;border:none;background-color:#ecf0f1;}QLabel#label_favorites_indicator:hover{background-color:#d5dbdb;}")
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
            show_success("FilterMate", f"Forced {backend_type.upper()} for {count} layers")
        else:
            show_warning("FilterMate", "Backend controller not available")

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
            msg = "PostgreSQL auto-cleanup enabled" if enabled else "PostgreSQL auto-cleanup disabled"
            (show_success if enabled else show_info)("FilterMate", msg)
    
    def _cleanup_postgresql_session_views(self):
        """Sprint 18: → BackendController via _backend_ctrl property."""
        if self._backend_ctrl:
            success = self._backend_ctrl.cleanup_postgresql_session_views()
            (show_success if success else show_warning)("FilterMate", "PostgreSQL session views cleaned up" if success else "No views to clean or cleanup failed")
        else:
            show_warning("FilterMate", "Backend controller not available")
    
    def _cleanup_postgresql_schema_if_empty(self):
        """Sprint 18: → BackendController via _backend_ctrl property."""
        from qgis.PyQt.QtWidgets import QMessageBox
        if self._backend_ctrl:
            info = self._backend_ctrl.get_postgresql_session_info()
            
            if not info.get('connection_available'):
                show_warning("FilterMate", "No PostgreSQL connection available")
                return
            
            # Check for other sessions' views
            other_count = info.get('total_views_count', 0) - info.get('our_views_count', 0)
            if other_count > 0:
                msg = f"Schema has {other_count} view(s) from other sessions.\nDrop anyway?"
                if QMessageBox.question(self, "Other Sessions Active", msg,
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                    show_info("FilterMate", "Schema cleanup cancelled")
                    return
            
            success = self._backend_ctrl.cleanup_postgresql_schema_if_empty(force=True)
            if success:
                show_success("FilterMate", f"Schema '{info.get('schema')}' dropped successfully")
            else:
                show_warning("FilterMate", "Schema cleanup failed")
        else:
            show_warning("FilterMate", "Backend controller not available")
    
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
            
            QMessageBox.information(self, "PostgreSQL Session Info", html)
        else:
            show_warning("FilterMate", "Backend controller not available")

    # ========================================
    # OPTIMIZATION SETTINGS METHODS
    # ========================================
    
    def _toggle_optimization_enabled(self):
        """v4.0 S16: → BackendController."""
        if self._backend_ctrl:
            enabled = self._backend_ctrl.toggle_optimization_enabled()
            (show_success if enabled else show_info)("FilterMate", f"Auto-optimization {'enabled' if enabled else 'disabled'}")
    
    def _toggle_centroid_auto(self):
        """v4.0 S16: → BackendController."""
        if self._backend_ctrl:
            enabled = self._backend_ctrl.toggle_centroid_auto()
            (show_success if enabled else show_info)("FilterMate", f"Auto-centroid {'enabled' if enabled else 'disabled'}")
    
    def _toggle_optimization_ask_before(self):
        """v4.0 S16: Toggle confirmation."""
        self._optimization_ask_before = not getattr(self, '_optimization_ask_before', True)
        (show_success if self._optimization_ask_before else show_info)("FilterMate", "Confirmation " + ("enabled" if self._optimization_ask_before else "disabled"))
    
    def _analyze_layer_optimizations(self):
        """v4.0 S16: Analyze layer optimizations."""
        if not self.current_layer: show_warning("FilterMate", "No layer selected. Please select a layer first."); return
        try:
            from .core.services.auto_optimizer import LayerAnalyzer, AutoOptimizer, AUTO_OPTIMIZER_AVAILABLE
            if not AUTO_OPTIMIZER_AVAILABLE: show_warning("FilterMate", "Auto-optimizer module not available"); return
            layer_analysis = LayerAnalyzer().analyze_layer(self.current_layer)
            if not layer_analysis: show_info("FilterMate", f"Could not analyze layer '{self.current_layer.name()}'"); return
            has_buf = getattr(self,'mQgsDoubleSpinBox_filtering_buffer_value',None) and self.mQgsDoubleSpinBox_filtering_buffer_value.value()!=0.0
            has_buf_type = getattr(self,'checkBox_filtering_buffer_type',None) and self.checkBox_filtering_buffer_type.isChecked()
            recommendations = AutoOptimizer().get_recommendations(layer_analysis, user_centroid_enabled=self._is_centroid_already_enabled(self.current_layer), has_buffer=has_buf, has_buffer_type=has_buf_type, is_source_layer=True)
            if not recommendations: show_success("FilterMate", f"Layer '{self.current_layer.name()}' is already optimally configured.\nType: {layer_analysis.location_type.value}\nFeatures: {layer_analysis.feature_count:,}"); return
            from .ui.dialogs.optimization_dialog import RecommendationDialog as OptimizationRecommendationDialog
            dialog = OptimizationRecommendationDialog(layer_name=self.current_layer.name(), recommendations=[r.to_dict() for r in recommendations],
                feature_count=layer_analysis.feature_count, location_type=layer_analysis.location_type.value, parent=self)
            if dialog.exec_():
                self._apply_optimization_selections(dialog.get_selected_optimizations(), self.current_layer)
        except ImportError as e:
            show_warning("FilterMate", f"Auto-optimizer not available: {e}")
        except Exception as e:
            show_warning("FilterMate", f"Error analyzing layer: {str(e)[:50]}")

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
            show_success("FilterMate", f"Applied to '{layer.name()}':\n" + "\n".join(f"• {a}" for a in applied))
        else:
            show_info("FilterMate", "No optimizations selected to apply.")
    
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
                show_warning("FilterMate", f"Dialog not available: {e}")
        except Exception as e:
            show_warning("FilterMate", f"Error: {str(e)[:50]}")
    
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
        except ImportError as e: show_warning("FilterMate", f"Dialog not available: {e}")
        except Exception as e: show_warning("FilterMate", f"Error: {str(e)[:50]}")
    
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
        except: return False
    
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
                (show_success if count > 0 else show_info)("FilterMate", f"Optimized {count} layer(s)" if count > 0 else "All layers using auto-selection")
                if self.current_layer:
                    _, _, layer_props = self._validate_and_prepare_layer(self.current_layer)
                    self._synchronize_layer_widgets(self.current_layer, layer_props)
            except Exception as e:
                logger.warning(f"auto_select_optimal_backends failed: {e}")
                show_warning("FilterMate", "Backend optimization unavailable")

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

    # v5.0: ActionBar wrapper methods removed - use self._action_bar_manager directly
    # Removed: _adjust_header_for_side_position, _restore_header_from_wrapper, _clear_action_bar_layout,
    # _create_horizontal_action_layout, _create_vertical_action_layout, _apply_action_bar_size_constraints,
    # _reposition_action_bar_in_main_layout, _create_horizontal_wrapper_for_side_action_bar,
    # _restore_side_action_bar_layout, _restore_original_layout (~30 lines)

    def _setup_exploring_tab_widgets(self):
        """v4.0 Sprint 16: Delegate to ConfigurationManager."""
        if self._configuration_manager:
            self._configuration_manager.setup_exploring_tab_widgets()

    def _setup_expression_widget_direct_connections(self):
        """v4.0 Sprint 16: Delegate to ConfigurationManager."""
        if self._configuration_manager:
            self._configuration_manager.setup_expression_widget_direct_connections()
    
    def _schedule_expression_change(self, groupbox: str, expression: str):
        """v4.0 Sprint 16: Schedule debounced expression change."""
        self._pending_expression_change = (groupbox, expression); self._set_expression_loading_state(True, groupbox); self._expression_debounce_timer.start()
    
    def _execute_debounced_expression_change(self):
        """v4.0 Sprint 16: Execute pending expression change after debounce."""
        if self._pending_expression_change is None:
            self._set_expression_loading_state(False); return
        groupbox, expression = self._pending_expression_change; self._pending_expression_change = None
        try:
            self.layer_property_changed(f"{groupbox}_expression", expression, {"ON_CHANGE": lambda x: self._execute_expression_params_change(groupbox)})
        except Exception:
            self._set_expression_loading_state(False)
    
    def _execute_expression_params_change(self, groupbox: str):
        """v4.0 Sprint 16: Execute expression params change with caching."""
        try:
            if groupbox in ("single_selection", "multiple_selection"): self._last_expression_change_source = groupbox
            if groupbox == "single_selection":
                try: self.mFeaturePickerWidget_exploring_single_selection.update()
                except Exception: pass
            elif groupbox == "multiple_selection":
                try:
                    w = self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection
                    if w and hasattr(w, 'list_widgets') and self.current_layer and self.current_layer.id() in w.list_widgets:
                        w.list_widgets[self.current_layer.id()].viewport().update()
                except Exception: pass
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
        except Exception: pass
    
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
        if self._controller_integration:
            try:
                if self._controller_integration.setup(): self._controller_integration.sync_from_dockwidget()
            except: pass
        if self.current_layer and not self.current_layer_selection_connection:
            try: self.current_layer.selectionChanged.connect(self.on_layer_selection_changed); self.current_layer_selection_connection = True
            except: pass
        self.widgetsInitialized.emit(); self._setup_keyboard_shortcuts()
        if self._pending_layers_update:
            self._pending_layers_update = False; pl, pr, weak_self = self.PROJECT_LAYERS, self.PROJECT, weakref.ref(self)
            QTimer.singleShot(100, lambda: weak_self() and weak_self().get_project_layers_from_app(pl, pr))

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
        """Cancel pending configuration changes."""
        if not self.config_changes_pending or not self.pending_config_changes: return
        try:
            with open(ENV_VARS.get('CONFIG_JSON_PATH', self.plugin_dir + '/config/config.json'), 'r') as f: self.CONFIG_DATA = json.load(f)
            self.config_model = JsonModel(data=self.CONFIG_DATA, editable_keys=False, editable_values=True, plugin_dir=self.plugin_dir)
            if hasattr(self, 'config_view') and self.config_view: self.config_view.setModel(self.config_model); self.config_view.model = self.config_model
            self.pending_config_changes, self.config_changes_pending = [], False
            if hasattr(self, 'buttonBox'): self.buttonBox.setEnabled(False)
        except Exception as e: show_error("FilterMate", f"Error cancelling changes: {str(e)}")

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

    def manage_configuration_model(self):
        """Setup config model, view, and signals."""
        try:
            self.config_model = JsonModel(data=self.CONFIG_DATA, editable_keys=False, editable_values=True, plugin_dir=self.plugin_dir)
            self.config_view = JsonView(self.config_model, self.plugin_dir)
            self.CONFIGURATION.layout().insertWidget(0, self.config_view); self.config_view.setAnimated(True); self.config_view.setEnabled(True); self.config_view.show()
            self.config_model.itemChanged.connect(self.data_changed_configuration_model); self._setup_reload_button()
            if hasattr(self, 'buttonBox'):
                self.buttonBox.setEnabled(False); self.buttonBox.accepted.connect(self.on_config_buttonbox_accepted); self.buttonBox.rejected.connect(self.on_config_buttonbox_rejected)
        except Exception as e: logger.error(f"Error creating configuration model: {e}")

    def _setup_reload_button(self):
        """Setup Reload Plugin button in config panel."""
        try:
            self.pushButton_reload_plugin = QtWidgets.QPushButton("🔄 Reload Plugin"); self.pushButton_reload_plugin.setObjectName("pushButton_reload_plugin")
            self.pushButton_reload_plugin.setToolTip(QCoreApplication.translate("FilterMate", "Reload the plugin to apply layout changes (action bar position)"))
            self.pushButton_reload_plugin.setCursor(QtGui.QCursor(Qt.PointingHandCursor)); self.pushButton_reload_plugin.setMinimumHeight(30)
            self.pushButton_reload_plugin.clicked.connect(self._on_reload_button_clicked)
            if self.CONFIGURATION.layout(): self.CONFIGURATION.layout().insertWidget(self.CONFIGURATION.layout().count() - 1, self.pushButton_reload_plugin)
        except Exception as e: logger.error(f"Error setting up reload button: {e}")

    def _on_reload_button_clicked(self):
        """v4.0 S18: Reload plugin after saving config."""
        from qgis.PyQt.QtWidgets import QMessageBox
        if self.config_changes_pending and self.pending_config_changes: self.apply_pending_config_changes()
        self.save_configuration_model()
        if QMessageBox.question(self, "Reload Plugin", "Do you want to reload FilterMate to apply all configuration changes?",
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
        icon = icon_map.get(geometry_type, QgsLayerItem.iconDefault)()
        self._icon_cache[geometry_type] = icon
        return icon
        
    def filtering_populate_predicates_chekableCombobox(self):
        """v4.0 S18: Populate geometric predicates combobox."""
        predicates = self._controller_integration.delegate_filtering_get_available_predicates() if self._controller_integration else None
        self.predicates = predicates or ["Intersect","Contain","Disjoint","Equal","Touch","Overlap","Are within","Cross"]
        w = self.widgets["FILTERING"]["GEOMETRIC_PREDICATES"]["WIDGET"]; w.clear(); w.addItems(self.predicates)

    def filtering_populate_buffer_type_combobox(self):
        """v4.0 S18: Populate buffer type combobox."""
        buffer_types = self._controller_integration.delegate_filtering_get_available_buffer_types() if self._controller_integration else None
        w = self.widgets["FILTERING"]["BUFFER_TYPE"]["WIDGET"]; w.clear(); w.addItems(buffer_types or ["Round", "Flat", "Square"])
        if not w.currentText(): w.setCurrentIndex(0)

    def filtering_populate_layers_chekableCombobox(self, layer=None):
        """Populate layers-to-filter combobox."""
        if self.widgets_initialized and self._controller_integration: self._controller_integration.delegate_populate_layers_checkable_combobox(layer)

    def exporting_populate_combobox(self):
        """Populate export layers combobox."""
        if self._controller_integration: self._controller_integration.delegate_populate_export_combobox()

    def _apply_auto_configuration(self):
        """Apply auto-configuration from environment."""
        return ui_utils.auto_configure_from_environment(self.CONFIG_DATA) if UI_CONFIG_AVAILABLE else {}

    def _apply_stylesheet(self):
        """Apply stylesheet using StyleLoader."""
        StyleLoader.set_theme_from_config(self.dockWidgetContents, self.CONFIG_DATA)

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
        """v4.0 Sprint 19: Apply stylesheet, icons, and styling via managers."""
        if self._theme_manager:
            self._theme_manager.setup()
        else:
            self._apply_auto_configuration()
            self._apply_stylesheet()
            self._setup_theme_watcher()
        
        if self._icon_manager:
            self._icon_manager.setup()
        elif ICON_THEME_AVAILABLE:
            IconThemeManager.set_theme(StyleLoader.detect_qgis_theme())
        
        if self._button_styler:
            self._button_styler.setup()
    
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
            show_info("FilterMate", f"Thème adapté: {'Mode sombre' if new_theme == 'dark' else 'Mode clair'}")
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
        except: pass

    def set_widgets_enabled_state(self, state):
        """v4.0 S18: Enable/disable all plugin widgets."""
        skip_types = ("JsonTreeView","LayerTreeView","JsonModel","ToolBox")
        for wg in self.widgets:
            for wn in self.widgets[wg]:
                wt, w = self.widgets[wg][wn]["TYPE"], self.widgets[wg][wn]["WIDGET"]
                if wt in skip_types: continue
                w.blockSignals(True)
                if wt in ("PushButton", "GroupBox") and w.isCheckable() and not state: w.setChecked(False); (w.setCollapsed(True) if wt == "GroupBox" else None)
                w.setEnabled(state); w.blockSignals(False)

    def connect_widgets_signals(self):
        """v4.0 Sprint 7: Ultra-simplified - connect all widget signals."""
        for grp in [g for g in self.widgets if g != 'QGIS']:
            for w in self.widgets[grp]:
                try: self.manageSignal([grp, w], 'connect')
                except: pass

    def disconnect_widgets_signals(self):
        """v4.0 Sprint 7: Ultra-simplified - safely disconnect all widget signals."""
        if not self.widgets: return
        for grp in [g for g in self.widgets if g != 'QGIS']:
            for w in self.widgets[grp]:
                try: self.manageSignal([grp, w], 'disconnect')
                except: pass

    def force_reconnect_action_signals(self):
        """v4.0 Sprint 8: Ultra-simplified - force reconnect ACTION signals bypassing cache."""
        if 'ACTION' not in self.widgets: return
        
        for w in ['FILTER', 'UNFILTER', 'UNDO_FILTER', 'REDO_FILTER', 'EXPORT']:
            if w not in self.widgets['ACTION']: continue
            for s_tuple in self.widgets['ACTION'][w].get("SIGNALS", []):
                if not s_tuple[-1]: continue
                key = f"ACTION.{w}.{s_tuple[0]}"
                self._signal_connection_states.pop(key, None)
                try:
                    state = self.changeSignalState(['ACTION', w], s_tuple[0], s_tuple[-1], 'connect')
                    self._signal_connection_states[key] = state
                except: pass

    def force_reconnect_exploring_signals(self):
        """v4.0 S18: Force reconnect EXPLORING signals bypassing cache."""
        if 'EXPLORING' not in self.widgets: return
        # REGRESSION FIX 2026-01-13: IS_SELECTING, IS_TRACKING, IS_LINKING use 'toggled' not 'clicked'
        ws = {'SINGLE_SELECTION_FEATURES': ['featureChanged'], 'SINGLE_SELECTION_EXPRESSION': ['fieldChanged'], 'MULTIPLE_SELECTION_FEATURES': ['updatingCheckedItemList', 'filteringCheckedItemList'],
              'MULTIPLE_SELECTION_EXPRESSION': ['fieldChanged'], 'CUSTOM_SELECTION_EXPRESSION': ['fieldChanged'], 'IDENTIFY': ['clicked'], 'ZOOM': ['clicked'],
              'IS_SELECTING': ['toggled'], 'IS_TRACKING': ['toggled'], 'IS_LINKING': ['toggled'], 'RESET_ALL_LAYER_PROPERTIES': ['clicked']}
        for w, signals in ws.items():
            if w not in self.widgets['EXPLORING']: continue
            for s_tuple in self.widgets['EXPLORING'][w].get("SIGNALS", []):
                if not s_tuple[-1] or s_tuple[0] not in signals: continue
                key = f"EXPLORING.{w}.{s_tuple[0]}"; self._signal_connection_states.pop(key, None)
                try: self._signal_connection_states[key] = self.changeSignalState(['EXPLORING', w], s_tuple[0], s_tuple[-1], 'connect')
                except: pass

    def manage_interactions(self):
        """v4.0 Sprint 8: Optimized - initialize widget interactions and default values."""
        self.coordinateReferenceSystem = QgsCoordinateReferenceSystem()
        
        self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"].setExpressionsEnabled(True)
        self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"].setClearValue(0.0)
        
        if self.PROJECT:
            self.widgets["EXPORTING"]["PROJECTION_TO_EXPORT"]["WIDGET"].setCrs(self.PROJECT.crs())
        
        if self.has_loaded_layers and self.PROJECT_LAYERS:
            self.set_widgets_enabled_state(True)
            self.connect_widgets_signals()
        else:
            self.set_widgets_enabled_state(False)
            for sp in [["DOCK", "SINGLE_SELECTION"], ["DOCK", "MULTIPLE_SELECTION"], ["DOCK", "CUSTOM_SELECTION"]]:
                try: self.manageSignal(sp, 'connect')
                except: pass
        
        self._connect_groupbox_signals_directly()
        self.filtering_populate_predicates_chekableCombobox()
        self.filtering_populate_buffer_type_combobox()

        if self.init_layer and isinstance(self.init_layer, QgsVectorLayer):
            self.manage_output_name()
            self.manageSignal(["EXPORTING","LAYERS_TO_EXPORT"], 'disconnect')
            self.exporting_populate_combobox()
            self.manageSignal(["EXPORTING","LAYERS_TO_EXPORT"], 'connect', 'checkedItemsChanged')
            self.set_exporting_properties()
            self.exploring_groupbox_init()
            self.current_layer_changed(self.init_layer)
            self.filtering_auto_current_layer_changed()
    def select_tabTools_index(self):
        """v4.0 S18: Update action buttons based on active tab."""
        if not self.widgets_initialized: return
        self.tabTools_current_index = self.widgets["DOCK"]["TOOLS"]["WIDGET"].currentIndex()
        states = {0: (True,True,True,True,False), 1: (False,False,False,False,True), 2: (False,)*5}
        s = states.get(self.tabTools_current_index, (False,)*5)
        for i, name in enumerate(['FILTER','UNDO_FILTER','REDO_FILTER','UNFILTER','EXPORT']): self.widgets["ACTION"][name]["WIDGET"].setEnabled(s[i])
        self.widgets["ACTION"]["ABOUT"]["WIDGET"].setEnabled(True)
        self.set_exporting_properties()

    def _connect_groupbox_signals_directly(self):
        """v4.0 S18: Connect groupbox signals for exclusive behavior."""
        try:
            gbs = [(self.mGroupBox_exploring_single_selection, 'single_selection'), (self.mGroupBox_exploring_multiple_selection, 'multiple_selection'), (self.mGroupBox_exploring_custom_selection, 'custom_selection')]
            for gb, _ in gbs:
                gb.blockSignals(True)
                try: gb.toggled.disconnect(); gb.collapsedStateChanged.disconnect()
                except: pass
                gb.blockSignals(False)
            for gb, name in gbs: gb.toggled.connect(lambda c, n=name: self._on_groupbox_clicked(n, c)); gb.collapsedStateChanged.connect(lambda col, n=name: self._on_groupbox_collapse_changed(n, col))
        except: pass

    def _force_exploring_groupbox_exclusive(self, active_groupbox):
        """v4.0 S18: Force exclusive state for exploring groupboxes."""
        if self._updating_groupbox: return
        self._updating_groupbox = True
        try:
            gbs = {"single": self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"], "multiple": self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"], "custom": self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"]}
            active_key = active_groupbox.split("_")[0]
            for gb in gbs.values(): gb.blockSignals(True)
            for key, gb in gbs.items(): gb.setChecked(key == active_key); gb.setCollapsed(key != active_key)
            for gb in gbs.values(): gb.blockSignals(False)
        finally:
            self._updating_groupbox = False

    def _on_groupbox_clicked(self, groupbox, state):
        """v4.0 S18: Handle groupbox toggle for exclusive behavior."""
        if self._updating_groupbox or not self.widgets_initialized: return
        if state: self.exploring_groupbox_changed(groupbox); return
        try: gbs = {"single_selection": self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"], "multiple_selection": self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"], "custom_selection": self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"]}
        except: return
        if not any(gbs[k].isChecked() for k in gbs if k != groupbox): gbs[groupbox].blockSignals(True); gbs[groupbox].setChecked(True); gbs[groupbox].setCollapsed(False); gbs[groupbox].blockSignals(False)
        else:
            for name, gb in gbs.items():
                if gb.isChecked(): self.exploring_groupbox_changed(name); break

    def _on_groupbox_collapse_changed(self, groupbox, collapsed):
        """v3.1 Sprint 10: Handle groupbox expand - make it the active one."""
        if self._updating_groupbox or not self.widgets_initialized or collapsed:
            return
        self.exploring_groupbox_changed(groupbox)

    def exploring_groupbox_init(self):
        """v4.0 Sprint 18: Initialize exploring groupbox to default or saved state."""
        if not self.widgets_initialized: return
        self.properties_group_state_enabler(self.layer_properties_tuples_dict["selection_expression"])
        groupbox = self.PROJECT_LAYERS.get(self.current_layer.id(), {}).get("exploring", {}).get("current_exploring_groupbox", "single_selection") if self.current_layer and self.current_layer.id() in self.PROJECT_LAYERS else "single_selection"
        self.exploring_groupbox_changed(groupbox)

    def _update_exploring_buttons_state(self):
        """v4.0 S18: Update identify/zoom buttons based on selection."""
        if not self.widgets_initialized or not self.current_layer:
            self.pushButton_exploring_identify.setEnabled(False); self.pushButton_exploring_zoom.setEnabled(False); return
        has_features = False
        try:
            w = self.widgets.get("EXPLORING", {})
            if self.current_exploring_groupbox == "single_selection" and (picker := w.get("SINGLE_SELECTION_FEATURES", {}).get("WIDGET")):
                f = picker.feature(); has_features = f is not None and (not hasattr(f, 'isValid') or f.isValid())
            elif self.current_exploring_groupbox == "multiple_selection" and (combo := w.get("MULTIPLE_SELECTION_FEATURES", {}).get("WIDGET")):
                has_features = bool(combo.checkedItems())
            elif self.current_exploring_groupbox == "custom_selection" and (expr := w.get("CUSTOM_SELECTION_EXPRESSION", {}).get("WIDGET")):
                has_features = bool(expr.expression() and expr.expression().strip())
        except: pass
        self.pushButton_exploring_identify.setEnabled(has_features); self.pushButton_exploring_zoom.setEnabled(has_features)

    def _configure_groupbox_common(self, groupbox_name):
        """v4.0 Sprint 17: Common groupbox configuration logic."""
        self.current_exploring_groupbox = groupbox_name
        self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
        self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')
        if not self.current_layer or self.current_layer.id() not in self.PROJECT_LAYERS:
            self._update_exploring_buttons_state(); return None
        self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["current_exploring_groupbox"] = groupbox_name
        layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
        if self._controller_integration:
            self._controller_integration.delegate_exploring_configure_groupbox(groupbox_name, self.current_layer, layer_props)
        return layer_props

    def _configure_single_selection_groupbox(self):
        """v4.0 Sprint 17: Configure single selection groupbox."""
        layer_props = self._configure_groupbox_common("single_selection")
        if layer_props is None: return True
        self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'filteringCheckedItemList')
        self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'updatingCheckedItemList')
        self.exploring_link_widgets()
        if not self._syncing_from_qgis:
            f = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].feature()
            if f and f.isValid(): self.exploring_features_changed(f)
        self._update_exploring_buttons_state(); return True

    def _configure_multiple_selection_groupbox(self):
        """v4.0 Sprint 17: Configure multiple selection groupbox."""
        layer_props = self._configure_groupbox_common("multiple_selection")
        if layer_props is None: return True
        self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect')
        self.exploring_link_widgets()
        if not self._syncing_from_qgis:
            features = self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].currentSelectedFeatures()
            if features: self.exploring_features_changed(features, True)
        self._update_exploring_buttons_state(); return True

    def _configure_custom_selection_groupbox(self):
        """v4.0 Sprint 17: Configure custom selection groupbox."""
        layer_props = self._configure_groupbox_common("custom_selection")
        if layer_props is None: return True
        self.manageSignal(["EXPLORING","CUSTOM_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
        self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'filteringCheckedItemList')
        self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'updatingCheckedItemList')
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
        """v4.0 Sprint 18: Flash selected features on map - delegates to ExploringController."""
        if not self._is_layer_valid(): return
        if self._controller_integration:
            features, _ = self.get_current_features()
            if features: self._controller_integration.delegate_flash_features([f.id() for f in features], self.current_layer)


    def get_current_features(self, use_cache: bool = True):
        """v4.0 Sprint 18: Get selected features based on active groupbox - delegates to ExploringController."""
        return self._controller_integration.delegate_get_current_features(use_cache) if self._controller_integration else ([], '')

    def exploring_zoom_clicked(self, features=[], expression=None):
        """v4.0 Sprint 18: Zoom to selected features - delegates to ExploringController."""
        if not self._is_layer_valid(): return
        if not features: features, expression = self.get_current_features()
        self.zooming_to_features(features, expression)


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
        except: return layer.extent()

    def _compute_zoom_extent_for_mode(self):
        """v4.0 Sprint 18: Compute zoom extent - delegates to ExploringController."""
        return self._exploring_ctrl._compute_zoom_extent_for_mode() if self._exploring_ctrl else self.get_filtered_layer_extent(self.current_layer) if self.current_layer else None

    def zooming_to_features(self, features, expression=None):
        """v4.0 Sprint 18: Zoom to features - delegates to ExploringController."""
        if not self._is_layer_valid(): return
        if self._exploring_ctrl:
            self._exploring_ctrl.zooming_to_features(features, expression)
        elif features: self.iface.mapCanvas().zoomToFeatureIds(self.current_layer, [f.id() for f in features]); self.iface.mapCanvas().refresh()


    def on_layer_selection_changed(self, selected, deselected, clearAndSelect):
        """v4.0 Sprint 18: Handle layer selection change - delegates to ExploringController."""
        if not (self._controller_integration and self._controller_integration.delegate_handle_layer_selection_changed(selected, deselected, clearAndSelect)):
            logger.debug("on_layer_selection_changed: Controller not available")
    
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
        """v4.0 S18: Get features matching custom expression."""
        if not self.widgets_initialized or not self.current_layer or self.current_layer.id() not in self.PROJECT_LAYERS: return [], ''
        expression = self.PROJECT_LAYERS[self.current_layer.id()]["exploring"].get("custom_selection_expression", "")
        if not expression: return [], expression
        qgs_expr = QgsExpression(expression)
        if qgs_expr.isField() and not any(op in expression.upper() for op in ['=','>','<','!','IN','LIKE','AND','OR']): return [], expression
        layer_id, cached = self.current_layer.id(), self._get_cached_expression_result(self.current_layer.id(), expression)
        if cached is not None: return cached, expression
        features = self.exploring_features_changed([], False, expression)
        if features: self._set_cached_expression_result(layer_id, expression, features)
        return features, expression

    def exploring_deselect_features(self):
        """v4.0 Sprint 18: Deselect all features - delegates to ExploringController."""
        if not self._is_layer_valid(): return
        if not (self._controller_integration and self._controller_integration.delegate_exploring_clear_selection()): self.current_layer.removeSelection()

    def exploring_select_features(self):
        """v4.0 Sprint 18: Select features from active groupbox - delegates to ExploringController."""
        if not self._is_layer_valid(): return
        if self._controller_integration:
            if self._controller_integration.delegate_exploring_activate_selection_tool(self.current_layer):
                features, _ = self.get_current_features()
                if features and self._controller_integration.delegate_exploring_select_layer_features([f.id() for f in features], self.current_layer): return
        try: self.iface.actionSelectRectangle().trigger(); self.iface.setActiveLayer(self.current_layer)
        except: pass
        features, _ = self.get_current_features()
        if features: self.current_layer.removeSelection(); self.current_layer.select([f.id() for f in features])

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
        layer_id = self.current_layer.id()
        
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

    def get_layers_to_filter(self):
        """v4.0 S18: Get checked layer IDs from filtering combobox."""
        if not self.widgets_initialized or not self.current_layer: return []
        checked = []
        w = self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"]
        for i in range(w.count()):
            if w.itemCheckState(i) == Qt.Checked:
                d = w.itemData(i, Qt.UserRole)
                checked.append(d["layer_id"] if isinstance(d, dict) and "layer_id" in d else d if isinstance(d, str) else None)
        checked = [c for c in checked if c]
        if self._controller_integration: self._controller_integration.delegate_filtering_set_target_layer_ids(checked)
        return checked


    def get_layers_to_export(self):
        """v4.0 S18: Get checked layer IDs for export."""
        if not self.widgets_initialized or not self.current_layer: return None
        w, checked = self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"], []
        for i in range(w.count()):
            if w.itemCheckState(i) == Qt.Checked:
                d = w.itemData(i, Qt.UserRole)
                if isinstance(d, str): checked.append(d)
        if self._controller_integration: self._controller_integration.delegate_export_set_layers_to_export(checked)
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
                show_warning("FilterMate", "La couche sélectionnée est invalide ou sa source est introuvable.")
                return (False, None, None)
        except: return (False, None, None)
        if self.current_layer is not None and self.current_layer_selection_connection is not None:
            try:
                self.current_layer.selectionChanged.disconnect(self.on_layer_selection_changed)
            except (TypeError, RuntimeError):
                pass
            self.current_layer_selection_connection = None
        
        self.current_layer = layer
        
        if self.current_layer.id() not in self.PROJECT_LAYERS:
            return (False, None, None)
        
        self.currentLayerChanged.emit()
        return (True, layer, self.PROJECT_LAYERS[self.current_layer.id()])
    
    def _reset_layer_expressions(self, layer_props):
        """v4.0 S18: → ExploringController."""
        if self._exploring_ctrl: self._controller_integration.delegate_reset_layer_expressions(layer_props)
    
    def _disconnect_layer_signals(self):
        """v3.1 Sprint 17: Disconnect all layer-related widget signals before updating."""
        exploring = ["SINGLE_SELECTION_FEATURES", "SINGLE_SELECTION_EXPRESSION", "MULTIPLE_SELECTION_FEATURES", "MULTIPLE_SELECTION_EXPRESSION", "CUSTOM_SELECTION_EXPRESSION", "IDENTIFY", "ZOOM", "IS_SELECTING", "IS_TRACKING", "IS_LINKING", "RESET_ALL_LAYER_PROPERTIES"]
        filtering = ["CURRENT_LAYER", "HAS_LAYERS_TO_FILTER", "LAYERS_TO_FILTER", "HAS_COMBINE_OPERATOR", "SOURCE_LAYER_COMBINE_OPERATOR", "OTHER_LAYERS_COMBINE_OPERATOR", "HAS_GEOMETRIC_PREDICATES", "GEOMETRIC_PREDICATES", "HAS_BUFFER_VALUE", "BUFFER_VALUE", "BUFFER_VALUE_PROPERTY", "HAS_BUFFER_TYPE", "BUFFER_TYPE"]
        widgets_to_stop = [["EXPLORING", w] for w in exploring] + [["FILTERING", w] for w in filtering]
        
        for wp in widgets_to_stop: self.manageSignal(wp, 'disconnect')
        
        for expr_key in ["SINGLE_SELECTION_EXPRESSION", "MULTIPLE_SELECTION_EXPRESSION", "CUSTOM_SELECTION_EXPRESSION"]:
            try: self.widgets.get("EXPLORING", {}).get(expr_key, {}).get("WIDGET", type('', (), {'setExpression': lambda s, x: None})()).setExpression("")
            except: pass
        
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
    
    def _synchronize_layer_widgets(self, layer, layer_props):
        """v4.0 S18: → LayerSyncController with fallback for controller unavailable."""
        # Try delegation first
        if self._layer_sync_ctrl:
            if self._controller_integration.delegate_synchronize_layer_widgets(layer, layer_props):
                return
        
        # Fallback: Minimal inline logic when controller unavailable (v4.0 Migration Fix)
        if not self._is_ui_ready() or not layer:
            return
        
        # Detect multi-step filter
        self._detect_multi_step_filter(layer, layer_props)
        
        # Sync current layer combo
        last_layer = self.widgets["FILTERING"]["CURRENT_LAYER"]["WIDGET"].currentLayer()
        if last_layer is None or last_layer.id() != layer.id():
            self.manageSignal(["FILTERING", "CURRENT_LAYER"], 'disconnect')
            self.widgets["FILTERING"]["CURRENT_LAYER"]["WIDGET"].setLayer(layer)
            self.manageSignal(["FILTERING", "CURRENT_LAYER"], 'connect', 'layerChanged')
        
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
        self.filtering_populate_layers_chekableCombobox()
        self.manageSignal(["FILTERING", "LAYERS_TO_FILTER"], 'connect', 'checkedItemsChanged')
        
        # Synchronize checkable button associated widgets enabled state
        self.filtering_layers_to_filter_state_changed()
        self.filtering_combine_operator_state_changed()
        self.filtering_geometric_predicates_state_changed()
    
    def _reload_exploration_widgets(self, layer, layer_props):
        """v4.0 S18: → ExploringController."""
        if self._exploring_ctrl: self._exploring_ctrl._reload_exploration_widgets(layer, layer_props)

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
            for i, gb in enumerate(gbs): gb.setChecked(s[i*2]); gb.setCollapsed(s[i*2+1]); gb.update()
        finally:
            for gb in gbs: gb.blockSignals(False)
    
    def _reconnect_layer_signals(self, widgets_to_reconnect, layer_props):
        """v4.0 S18: → LayerSyncController."""
        if self._layer_sync_ctrl: self._controller_integration.delegate_reconnect_layer_signals(widgets_to_reconnect, layer_props)

    
    def _ensure_valid_current_layer(self, requested_layer):
        """v4.0 Sprint 18: Ensure valid layer - delegates to LayerSyncController."""
        if self._layer_sync_ctrl:
            try: 
                result = self._controller_integration.delegate_ensure_valid_current_layer(requested_layer)
                if result is not None: return result
            except: pass
        if requested_layer:
            try: _ = requested_layer.id(); return requested_layer
            except: pass
        return None

    def _is_layer_truly_deleted(self, layer):
        """v4.0 Sprint 18: Check if layer is truly deleted - delegates to LayerSyncController."""
        if layer is None: return True
        try:
            if self._layer_sync_ctrl: return self._controller_integration.delegate_is_layer_truly_deleted(layer)
            import sip
            return sip.isdeleted(layer)
        except: return True

    def current_layer_changed(self, layer):
        """v4.0 Sprint 18: Handle current layer change event."""
        if self._updating_current_layer: return
        if self._controller_integration and not self._controller_integration.delegate_current_layer_changed(layer): return
        layer = self._ensure_valid_current_layer(layer)
        if layer is None: return
        if self._plugin_busy: self._defer_layer_change(layer); return
        try: _ = layer.id()
        except: return
        self._updating_current_layer = True
        self._reset_selection_tracking_for_layer(layer)
        try:
            should_continue, validated_layer, layer_props = self._validate_and_prepare_layer(layer)
            if not should_continue: return
            self._reset_layer_expressions(layer_props); widgets = self._disconnect_layer_signals()
            self._synchronize_layer_widgets(validated_layer, layer_props); self._reload_exploration_widgets(validated_layer, layer_props)
            self._update_exploring_buttons_state(); self._reconnect_layer_signals(widgets, layer_props)
        except Exception as e: logger.error(f"Error in current_layer_changed: {e}")
        finally: self._updating_current_layer = False
    
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
        if not self.widgets_initialized or not self.current_layer:
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
            except: pass
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
            if t[1] in ['has_output_folder_to_export', 'has_zip_to_export']:
                has_layers = any(self.checkableComboBoxLayer_exporting_layers.itemCheckState(i) == Qt.Checked for i in range(self.checkableComboBoxLayer_exporting_layers.count())) if hasattr(self, 'checkableComboBoxLayer_exporting_layers') else False
                we["WIDGET"].setEnabled(has_layers)
            else: we["WIDGET"].setEnabled(True)
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
            widget_type = widget_info.get("TYPE")
            
            if widget is None:
                continue
            
            # Handle enabled state: first widget (HAS_xxx) stays enabled, others disabled
            if i == 0 and property_path[1].upper().find('HAS') >= 0:
                widget.setEnabled(True)
            else:
                widget.setEnabled(state)

    def filtering_init_buffer_property(self):
        """v4.0 S18: Init buffer property override widget."""
        if not self.widgets_initialized or not self.has_loaded_layers or not self.current_layer or self.current_layer.id() not in self.PROJECT_LAYERS: return
        lp, lid = self.PROJECT_LAYERS[self.current_layer.id()], self.current_layer.id()
        prop_def = QgsPropertyDefinition(f"{lid}_buffer_property_definition", QgsPropertyDefinition.DataTypeNumeric, f"Replace buffer with expression for {lid}", 'Expression must return numeric values (meters)')
        buf_expr = lp["filtering"]["buffer_value_expression"]
        if not isinstance(buf_expr, str): buf_expr = str(buf_expr) if buf_expr else ''; lp["filtering"]["buffer_value_expression"] = buf_expr
        prop = QgsProperty.fromExpression(buf_expr) if buf_expr and buf_expr.strip() else QgsProperty()
        self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].init(0, prop, prop_def, self.current_layer)
        has_buf, is_active, has_expr = lp["filtering"].get("has_buffer_value", False), lp["filtering"]["buffer_value_property"], bool(buf_expr and buf_expr.strip())
        self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"].setEnabled(has_buf and not (is_active and has_expr))
        self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].setEnabled(has_buf)


    def filtering_buffer_property_changed(self):
        """v4.0 Sprint 8: Optimized - handle buffer property override button changes."""
        if not self._is_ui_ready(): return

        self.manageSignal(["FILTERING","BUFFER_VALUE_PROPERTY"], 'disconnect')

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

        self.manageSignal(["FILTERING","BUFFER_VALUE_PROPERTY"], 'connect')


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
        """
        # CRITICAL: Use original condition - _is_ui_ready() was too restrictive and blocked state changes
        if self.widgets_initialized is True and self.has_loaded_layers is True:
            is_checked = self.widgets["FILTERING"]["HAS_LAYERS_TO_FILTER"]["WIDGET"].isChecked()
            
            # CRITICAL: ALWAYS enable/disable the associated widgets directly
            # This must happen BEFORE controller delegation to ensure UI is updated
            self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].setEnabled(is_checked)
            self.widgets["FILTERING"]["USE_CENTROIDS_DISTANT_LAYERS"]["WIDGET"].setEnabled(is_checked)
            
            # Optional controller delegation for additional logic
            if self._controller_integration:
                self._controller_integration.delegate_filtering_layers_to_filter_state_changed(is_checked)
            
            logger.debug(f"filtering_layers_to_filter_state_changed: is_checked={is_checked}")


    def filtering_combine_operator_state_changed(self):
        """Handle changes to the has_combine_operator checkable button.
        
        When checked (True): Enable combine operator comboboxes
        When unchecked (False): Disable these widgets
        
        v4.0.1: REGRESSION FIX - Restored original condition from v2.3.8
        """
        # CRITICAL: Use original condition - _is_ui_ready() was too restrictive
        if self.widgets_initialized is True and self.has_loaded_layers is True:
            is_checked = self.widgets["FILTERING"]["HAS_COMBINE_OPERATOR"]["WIDGET"].isChecked()
            
            # CRITICAL: ALWAYS enable/disable the associated widgets directly FIRST
            self.widgets["FILTERING"]["SOURCE_LAYER_COMBINE_OPERATOR"]["WIDGET"].setEnabled(is_checked)
            self.widgets["FILTERING"]["OTHER_LAYERS_COMBINE_OPERATOR"]["WIDGET"].setEnabled(is_checked)
            
            # Optional controller delegation
            if self._controller_integration:
                self._controller_integration.delegate_filtering_combine_operator_state_changed(is_checked)
            
            logger.debug(f"filtering_combine_operator_state_changed: is_checked={is_checked}")


    def filtering_geometric_predicates_state_changed(self):
        """Handle changes to the has_geometric_predicates checkable button.
        
        When checked (True): Enable geometric predicates combobox
        When unchecked (False): Disable this widget
        
        v4.0.1: REGRESSION FIX - Restored original condition from v2.3.8
        """
        # CRITICAL: Use original condition - _is_ui_ready() was too restrictive
        if self.widgets_initialized is True and self.has_loaded_layers is True:
            is_checked = self.widgets["FILTERING"]["HAS_GEOMETRIC_PREDICATES"]["WIDGET"].isChecked()
            
            # CRITICAL: ALWAYS enable/disable the associated widgets directly FIRST
            self.widgets["FILTERING"]["GEOMETRIC_PREDICATES"]["WIDGET"].setEnabled(is_checked)
            
            # Optional controller delegation
            if self._controller_integration:
                self._controller_integration.delegate_filtering_geometric_predicates_state_changed(is_checked)
            
            logger.debug(f"filtering_geometric_predicates_state_changed: is_checked={is_checked}")


    def filtering_buffer_type_state_changed(self):
        """Handle changes to the has_buffer_type checkable button.
        
        When checked (True): Enable buffer type and segments widgets
        When unchecked (False): Disable these widgets
        
        v4.0.1: REGRESSION FIX - Restored original condition from v2.3.8
        """
        # CRITICAL: Use original condition - _is_ui_ready() was too restrictive
        if self.widgets_initialized is True and self.has_loaded_layers is True:
            is_checked = self.widgets["FILTERING"]["HAS_BUFFER_TYPE"]["WIDGET"].isChecked()
            
            # CRITICAL: ALWAYS enable/disable the associated widgets directly FIRST
            self.widgets["FILTERING"]["BUFFER_TYPE"]["WIDGET"].setEnabled(is_checked)
            self.widgets["FILTERING"]["BUFFER_SEGMENTS"]["WIDGET"].setEnabled(is_checked)
            
            # Optional controller delegation
            if self._controller_integration:
                self._controller_integration.delegate_filtering_buffer_type_state_changed(is_checked)
            
            logger.debug(f"filtering_buffer_type_state_changed: is_checked={is_checked}")

    def _update_centroids_source_checkbox_state(self):
        """v4.0 Sprint 8: Optimized - update centroids checkbox enabled state."""
        if not self.widgets_initialized: return
        if (combo := self.widgets.get("FILTERING", {}).get("CURRENT_LAYER", {}).get("WIDGET")) and \
           (checkbox := self.widgets.get("FILTERING", {}).get("USE_CENTROIDS_SOURCE_LAYER", {}).get("WIDGET")):
            checkbox.setEnabled(combo.currentLayer() is not None and combo.isEnabled())

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
        """v3.1 Sprint 12: Simplified - handle auto current layer toggle."""
        if not self._is_ui_ready(): return
        if state is None:
            state = self.project_props["OPTIONS"]["LAYERS"]["LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"]
        self.widgets["FILTERING"]["AUTO_CURRENT_LAYER"]["WIDGET"].setChecked(state)
        self.project_props["OPTIONS"]["LAYERS"]["LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"] = state
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
        
        self.manageSignal(["EXPORTING","LAYERS_TO_EXPORT"], 'disconnect')
        self.exporting_populate_combobox()
        self.manageSignal(["EXPORTING","LAYERS_TO_EXPORT"], 'connect', 'checkedItemsChanged')
        self.set_exporting_properties()
        
        if not self._signals_connected:
            self.connect_widgets_signals()
            self._signals_connected = True
        
        # Update backend indicator
        if self.PROJECT_LAYERS:
            first_layer_id = list(self.PROJECT_LAYERS.keys())[0]
            layer_props = self.PROJECT_LAYERS.get(first_layer_id, {})
            infos = layer_props.get('infos', {})
            if 'layer_provider_type' in infos:
                forced = self.forced_backends.get(first_layer_id) if hasattr(self, 'forced_backends') else None
                self._update_backend_indicator(infos['layer_provider_type'], infos.get('postgresql_connection_available'), actual_backend=forced)
        
        if was_empty and self.PROJECT_LAYERS:
            show_success("FilterMate", f"Plugin activé avec {len(self.PROJECT_LAYERS)} couche(s) vectorielle(s)")

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
        self.current_layer_changed(layer)
        
        if self.current_layer and self.current_layer.id() in self.PROJECT_LAYERS:
            self.exploring_groupbox_init()
        
        self.filtering_auto_current_layer_changed()
        
        if self.current_layer and isinstance(self.current_layer, QgsVectorLayer):
            self.manageSignal(["FILTERING","LAYERS_TO_FILTER"], 'disconnect')
            self.filtering_populate_layers_chekableCombobox(self.current_layer)
            self.manageSignal(["FILTERING","LAYERS_TO_FILTER"], 'connect', 'checkedItemsChanged')

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
                layer = self._determine_active_layer()
                self._activate_layer_ui()
                if layer: self._refresh_layer_specific_widgets(layer)
                return
            if self.current_layer and self.current_layer.isValid():
                if not self._signals_connected: self.connect_widgets_signals(); self._signals_connected = True
                return
            # No layers - disable UI
            self.has_loaded_layers, self.current_layer = False, None
            self.disconnect_widgets_signals()
            self._signals_connected = False
            self.set_widgets_enabled_state(False)
            if self.backend_indicator_label:
                self.backend_indicator_label.setText("...")
                self.backend_indicator_label.setStyleSheet("QLabel#label_backend_indicator { color: #7f8c8d; font-size: 9pt; font-weight: 600; padding: 3px 10px; border-radius: 12px; border: none; background-color: #ecf0f1; }")
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
            if 'filter_mate' not in plugins: show_warning("FilterMate", "Could not reload plugin automatically."); return
            fm = plugins['filter_mate']; self.close(); fm.pluginIsActive, fm.app = False, None; QTimer.singleShot(100, fm.run)
        except Exception as e: show_error("FilterMate", f"Error reloading plugin: {str(e)}")


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
            except: pass


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
        except: pass

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
        
        # Backend styling configuration (same as BackendController.BACKEND_STYLES)
        BACKEND_STYLES = {
            'postgresql': {'text': 'PostgreSQL', 'color': 'white', 'background': '#27ae60'},
            'spatialite': {'text': 'Spatialite', 'color': 'white', 'background': '#9b59b6'},
            'ogr': {'text': 'OGR', 'color': 'white', 'background': '#3498db'},
            'ogr_fallback': {'text': 'OGR*', 'color': 'white', 'background': '#e67e22'},
            'unknown': {'text': '...', 'color': '#7f8c8d', 'background': '#ecf0f1'}
        }
        
        style = BACKEND_STYLES.get(backend_type, BACKEND_STYLES['unknown'])
        self.backend_indicator_label.setText(style['text'])
        
        base_style = f"""
            QLabel#label_backend_indicator {{
                color: {style['color']};
                background-color: {style['background']};
                font-size: 9pt;
                font-weight: 600;
                padding: 3px 10px;
                border-radius: 12px;
                border: none;
            }}
            QLabel#label_backend_indicator:hover {{
                opacity: 0.85;
            }}
        """
        self.backend_indicator_label.setStyleSheet(base_style)
        self.backend_indicator_label.adjustSize()
    
    def getProjectLayersEvent(self, event):
        if self.widgets_initialized: self.gettingProjectLayers.emit()

    def closeEvent(self, event):
        """v3.1 Sprint 17: Clean up resources before closing."""
        if not self.widgets_initialized:
            event.accept()
            return
        
        try: self.comboBox_filtering_current_layer.setLayer(None) if hasattr(self, 'comboBox_filtering_current_layer') else None
        except: pass
        try: self.mFeaturePickerWidget_exploring_single_selection.setLayer(None) if hasattr(self, 'mFeaturePickerWidget_exploring_single_selection') else None
        except: pass
        try: self._exploring_cache.invalidate_all() if hasattr(self, '_exploring_cache') else None
        except: pass
        try: self._theme_watcher.remove_callback(self._on_qgis_theme_changed) if self._theme_watcher else None
        except: pass
        try: self._controller_integration.teardown() if self._controller_integration else None
        except: pass
        
        self.closingPlugin.emit()
        event.accept()

    def get_exploring_cache_stats(self):
        """v4.0 Sprint 18: Get cache statistics."""
        return (self._controller_integration.delegate_exploring_get_cache_stats() if self._controller_integration else None) or (self._exploring_cache.get_stats() if hasattr(self, '_exploring_cache') else {})
    
    def invalidate_exploring_cache(self, layer_id=None, groupbox_type=None):
        """v4.0 Sprint 18: Invalidate exploring cache."""
        if layer_id is None and groupbox_type is None and self._controller_integration and self._controller_integration.delegate_exploring_clear_cache(): return
        if hasattr(self, '_exploring_cache'):
            self._exploring_cache.invalidate_all() if layer_id is None else (self._exploring_cache.invalidate_layer(layer_id) if groupbox_type is None else self._exploring_cache.invalidate(layer_id, groupbox_type))

    def launchTaskEvent(self, state, task_name):
        """v4.0 S18: Emit signal to launch a task."""
        if not self.widgets_initialized or not self.current_layer or self.current_layer.id() not in self.PROJECT_LAYERS: return
        self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["layers_to_filter"] = self.get_layers_to_filter()
        self.setLayerVariableEvent(self.current_layer, [("filtering", "layers_to_filter")]); self.launchingTask.emit(task_name)
    
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
                except: pass
    
    def _update_combo_tooltip(self, combo):
        """v4.0 Sprint 17: Update tooltip for combo widget."""
        if not combo or not hasattr(combo, 'currentText'): return
        try:
            t = combo.currentText()
            combo.setToolTip(t if t and len(t) > 30 else QCoreApplication.translate("FilterMate", "Current layer: {0}").format(t) if t else QCoreApplication.translate("FilterMate", "No layer selected"))
        except: pass
    
    def _update_checkable_combo_tooltip(self, combo):
        """v4.0 Sprint 17: Update tooltip for checkable combo showing selected items."""
        if not combo or not hasattr(combo, 'checkedItems'): return
        try:
            items = combo.checkedItems()
            t = "\n".join([i.text() for i in items if hasattr(i, 'text')]) if items else ""
            combo.setToolTip(QCoreApplication.translate("FilterMate", "Selected layers:\n{0}").format(t) if t else QCoreApplication.translate("FilterMate", "No layers selected"))
        except: pass
    
    def _update_export_buttons_state(self):
        """v4.0 Sprint 17: Update export buttons based on layer selection."""
        try:
            has_layers = any(self.checkableComboBoxLayer_exporting_layers.itemCheckState(i) == Qt.Checked 
                           for i in range(self.checkableComboBoxLayer_exporting_layers.count())) if hasattr(self, 'checkableComboBoxLayer_exporting_layers') else False
            for btn in ['pushButton_checkable_exporting_output_folder', 'pushButton_checkable_exporting_zip']:
                if hasattr(self, btn): getattr(self, btn).setEnabled(has_layers)
        except: pass
    
    def _update_expression_tooltip(self, expr_widget):
        """v4.0 Sprint 17: Update tooltip for expression widget."""
        if not expr_widget or not hasattr(expr_widget, 'expression'): return
        try:
            e = expr_widget.expression()
            if e and len(e) > 40: e = e.replace(' AND ', '\nAND ').replace(' OR ', '\nOR ')
            expr_widget.setToolTip(QCoreApplication.translate("FilterMate", "Expression:\n{0}" if e and len(e) > 40 else "Expression: {0}").format(e) if e else QCoreApplication.translate("FilterMate", "No expression defined"))
        except: pass
    
    def _update_feature_picker_tooltip(self, picker):
        """v4.0 Sprint 17: Update tooltip for feature picker widget."""
        if not picker: return
        try:
            if hasattr(picker, 'displayExpression'):
                de = picker.displayExpression()
                if de and len(de) > 30: picker.setToolTip(QCoreApplication.translate("FilterMate", "Display expression: {0}").format(de)); return
            if hasattr(picker, 'feature'):
                f = picker.feature()
                if f and f.isValid() and f.attributes():
                    picker.setToolTip(QCoreApplication.translate("FilterMate", "Feature ID: {0}\nFirst attribute: {1}").format(f.id(), f.attributes()[0]))
        except: pass

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

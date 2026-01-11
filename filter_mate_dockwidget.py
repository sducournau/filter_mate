# -*- coding: utf-8 -*-
"""
/***************************************************************************
 FilterMateDockWidget
                                 A QGIS plugin
 FilterMate is a Qgis plugin, an everyday companion that allows you to easily filter your vector layers
                             -------------------
        begin                : 2023-10-26
        git sha              : $Format:%H$
        copyright            : (C) 2023 by imagodata
        email                : imagodata+filter_mate@skiff.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/

.. deprecated:: 3.0.0
    This module is a legacy God Class (12,000+ lines) and will be progressively
    refactored in future versions. New code should use the hexagonal architecture:
    
    - For UI logic: ui/controllers/ (FilteringController, ExploringController, ExportingController)
    - For filtering: core/services/filter_service.py
    - For domain objects: core/domain/
    
    This module is kept for backward compatibility and will delegate to new
    controllers progressively. See docs/architecture.md for migration guide.
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

# Compatibility layer for proxy model classes that may be in different modules
# depending on QGIS version. These classes moved from qgis.core to qgis.gui
# in newer QGIS versions (3.30+)

# QgsMapLayerProxyModel: Used for filtering layer types (e.g., VectorLayer only)
try:
    from qgis.gui import QgsMapLayerProxyModel
except ImportError:
    try:
        from qgis.core import QgsMapLayerProxyModel
    except ImportError:
        # Fallback for versions where QgsMapLayerProxyModel is not available
        class QgsMapLayerProxyModel:
            """Fallback class for QGIS versions without QgsMapLayerProxyModel"""
            VectorLayer = 1  # Filter to show only vector layers

# QgsFieldProxyModel: Used for filtering field types in QgsFieldExpressionWidget
try:
    from qgis.gui import QgsFieldProxyModel
except ImportError:
    try:
        from qgis.core import QgsFieldProxyModel
    except ImportError:
        # Fallback for versions where QgsFieldProxyModel is not available
        class QgsFieldProxyModel:
            """Fallback class for QGIS versions without QgsFieldProxyModel"""
            AllTypes = 0  # No filtering (all field types accepted)
from qgis.utils import iface

import webbrowser
from .modules.widgets import QgsCheckableComboBoxFeaturesListPickerWidget, QgsCheckableComboBoxLayer
from .modules.qt_json_view.model import JsonModel
from .modules.qt_json_view.view import JsonView
from .modules.object_safety import is_valid_layer
from .modules.appUtils import (
    get_best_display_field,
    is_layer_source_available
)
from .modules.customExceptions import SignalStateChangeError
from .modules.constants import PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR, get_geometry_type_string
from .ui.styles import StyleLoader, QGISThemeWatcher
from .infrastructure.feedback import show_info, show_warning, show_error, show_success
from .modules.config_helpers import set_config_value, get_optimization_thresholds
from .infrastructure.cache import ExploringFeaturesCache
from .filter_mate_dockwidget_base import Ui_FilterMateDockWidgetBase

# Import async expression evaluation for large layers (v2.5.10)
# EPIC-1: Migrated to core/tasks/
try:
    from core.tasks import get_expression_manager
    ASYNC_EXPRESSION_AVAILABLE = True
except ImportError:
    ASYNC_EXPRESSION_AVAILABLE = False
    get_expression_manager = None

# Import CRS utilities for improved CRS compatibility (v2.5.7)
try:
    from .modules.crs_utils import (
        is_geographic_crs,
        get_optimal_metric_crs,
        DEFAULT_METRIC_CRS
    )
    CRS_UTILS_AVAILABLE = True
except ImportError:
    CRS_UTILS_AVAILABLE = False
    DEFAULT_METRIC_CRS = "EPSG:3857"

# Import icon utilities for dark mode support
try:
    from .modules.icon_utils import IconThemeManager, get_themed_icon
    ICON_THEME_AVAILABLE = True
except ImportError:
    ICON_THEME_AVAILABLE = False

# Import UI configuration system for dynamic dimensions
try:
    from .ui.config import UIConfig
    from .modules import ui_widget_utils as ui_utils
    UI_CONFIG_AVAILABLE = True
except ImportError:
    UI_CONFIG_AVAILABLE = False

# Import MVC Controllers for gradual migration (v3.0)
try:
    from .ui.controllers.integration import ControllerIntegration
    from .adapters.app_bridge import get_filter_service, is_initialized as is_hexagonal_initialized
    CONTROLLERS_AVAILABLE = True
except ImportError as e:
    CONTROLLERS_AVAILABLE = False
    get_filter_service = None
    is_hexagonal_initialized = lambda: False
    logger.debug(f"Controllers not available: {e}")

# Import Layout Managers for God Class refactoring (v3.1 - Phase 6)
try:
    from .ui.layout import SplitterManager, DimensionsManager, SpacingManager, ActionBarManager
    LAYOUT_MANAGERS_AVAILABLE = True
except ImportError as e:
    LAYOUT_MANAGERS_AVAILABLE = False
    SplitterManager = None
    DimensionsManager = None
    SpacingManager = None
    ActionBarManager = None
    logger.debug(f"Layout managers not available: {e}")

# Import Style Managers for God Class refactoring (v3.1 - Phase 6)
try:
    from .ui.styles import ThemeManager, IconManager, ButtonStyler
    STYLE_MANAGERS_AVAILABLE = True
except ImportError as e:
    STYLE_MANAGERS_AVAILABLE = False
    ThemeManager = None
    IconManager = None
    ButtonStyler = None
    logger.debug(f"Style managers not available: {e}")


class FilterMateDockWidget(QtWidgets.QDockWidget, Ui_FilterMateDockWidgetBase):

    closingPlugin = pyqtSignal()
    launchingTask = pyqtSignal(str)
    currentLayerChanged = pyqtSignal()
    widgetsInitialized = pyqtSignal()  # NEW: Signal emitted when widgets are fully initialized

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
        """v4.0 Sprint 15: Initialize dockwidget with state, managers, and performance optimizations."""
        super(FilterMateDockWidget, self).__init__(parent)
        self.exception, self.iface = None, iface
        self.plugin_dir, self.CONFIG_DATA, self.PROJECT_LAYERS, self.PROJECT = plugin_dir, config_data, project_layers, project
        self.current_layer, self.current_layer_selection_connection = None, None
        
        # Protection flags
        self._updating_layers = self._updating_current_layer = self._updating_groupbox = self._signals_connected = False
        self._pending_layers_update = self._plugin_busy = self._syncing_from_qgis = False
        self._filtering_in_progress, self._filter_completed_time, self._saved_layer_id_before_filter = False, 0, None
        self._layer_tree_view_signal_connected = False
        self._signal_connection_states = {}
        self._theme_watcher = None
        
        # Expression debounce (450ms)
        self._expression_debounce_timer = QTimer()
        self._expression_debounce_timer.setSingleShot(True)
        self._expression_debounce_timer.setInterval(450)
        self._expression_debounce_timer.timeout.connect(self._execute_debounced_expression_change)
        self._pending_expression_change = self._last_expression_change_source = None
        
        # Expression cache (60s TTL, 100 max entries)
        self._expression_cache = {}
        self._expression_cache_max_age, self._expression_cache_max_size = 60.0, 100
        
        # Async expression eval
        thresholds = get_optimization_thresholds(ENV_VARS)
        self._async_expression_threshold = thresholds['async_expression_threshold']
        self._expression_manager = get_expression_manager() if ASYNC_EXPRESSION_AVAILABLE else None
        self._pending_async_evaluation, self._expression_loading = None, False
        self._configuration_manager = None
        self._initialize_layer_state()
    
    def _safe_get_layer_props(self, layer):
        """
        Safely get layer properties from PROJECT_LAYERS with validation.
        
        Args:
            layer (QgsVectorLayer): The layer to get properties for
            
        Returns:
            dict or None: Layer properties if found, None otherwise
        """
        if layer is None:
            return None
        
        if not isinstance(layer, QgsVectorLayer):
            return None
            
        layer_id = layer.id()
        if layer_id not in self.PROJECT_LAYERS:
            logger.warning(f"Layer {layer.name()} (ID: {layer_id}) not found in PROJECT_LAYERS")
            return None
            
        return self.PROJECT_LAYERS[layer_id]
    
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
        """v3.1 Sprint 14: Get signal from QObject by name with caching."""
        class_name = oObject.metaObject().className()
        cache_key = f"{class_name}.{strSignalName}"
        if cache_key in FilterMateDockWidget._signal_cache:
            return FilterMateDockWidget._signal_cache[cache_key]
        oMetaObj = oObject.metaObject()
        for i in range(oMetaObj.methodCount()):
            oMetaMethod = oMetaObj.method(i)
            if oMetaMethod.isValid() and oMetaMethod.methodType() == QMetaMethod.Signal and \
               oMetaMethod.name() == strSignalName:
                FilterMateDockWidget._signal_cache[cache_key] = oMetaMethod
                return oMetaMethod
        FilterMateDockWidget._signal_cache[cache_key] = None
        return None

    def manageSignal(self, widget_path, custom_action=None, custom_signal_name=None):
        """v3.1 Sprint 15: Manage signal connection/disconnection."""
        if not isinstance(widget_path, list) or len(widget_path) != 2:
            raise SignalStateChangeError(None, widget_path, 'Incorrect input parameters')
        
        widget_object = self.widgets[widget_path[0]][widget_path[1]]
        state = None
        
        signals_to_process = [(s[0], s[-1]) for s in widget_object["SIGNALS"] 
                              if s[-1] is not None and (custom_signal_name is None or s[0] == custom_signal_name)]
        
        for signal_name, func in signals_to_process:
            state_key = f"{widget_path[0]}.{widget_path[1]}.{signal_name}"
            cached = self._signal_connection_states.get(state_key)
            if (custom_action == 'connect' and cached is True) or (custom_action == 'disconnect' and cached is False):
                state = cached
                continue
            state = self.changeSignalState(widget_path, signal_name, func, custom_action)
            self._signal_connection_states[state_key] = state
        
        return True if state is None and widget_object["SIGNALS"] else state
        if state is None:
            raise SignalStateChangeError(state, widget_path)

    def changeSignalState(self, widget_path, signal_name, func, custom_action=None):
        """v3.1 Sprint 15: Change signal connection state."""
        if not isinstance(widget_path, list) or len(widget_path) != 2:
            raise SignalStateChangeError(None, widget_path)
        
        widget = self.widgets[widget_path[0]][widget_path[1]]["WIDGET"]
        if not hasattr(widget, signal_name):
            raise SignalStateChangeError(None, widget_path)
        
        is_ltv = widget_path == ["QGIS", "LAYER_TREE_VIEW"]
        state = self._layer_tree_view_signal_connected if is_ltv else widget.isSignalConnected(self.getSignal(widget, signal_name))
        signal = getattr(widget, signal_name)
        
        should_connect = (custom_action == 'connect' and not state) or (custom_action is None and not state)
        should_disconnect = (custom_action == 'disconnect' and state) or (custom_action is None and state)
        
        try:
            if should_disconnect: signal.disconnect(func)
            elif should_connect: signal.connect(func)
        except TypeError: pass
        
        if is_ltv: self._layer_tree_view_signal_connected = should_connect
        return self._layer_tree_view_signal_connected if is_ltv else widget.isSignalConnected(self.getSignal(widget, signal_name))

    def reset_multiple_checkable_combobox(self):
        """v3.1 Sprint 14: Reset and recreate multiple checkable combobox widget."""
        try:
            layout = self.horizontalLayout_exploring_multiple_feature_picker
            if layout.count() > 0:
                item = layout.itemAt(0)
                if item and item.widget():
                    old_widget = item.widget()
                    layout.removeWidget(old_widget)
                    old_widget.deleteLater()
            if hasattr(self, 'checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection') and \
               self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection is not None:
                try:
                    self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection.reset()
                    self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection.close()
                    self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection.deleteLater()
                except (RuntimeError, AttributeError):
                    pass
            self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection = None
            self.set_multiple_checkable_combobox()
            if self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection is not None:
                layout.insertWidget(0, self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection, 1)
                layout.update()
                self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"] = {
                    "TYPE": "CustomCheckableFeatureComboBox",
                    "WIDGET": self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection,
                    "SIGNALS": [("updatingCheckedItemList", self.exploring_features_changed),
                                ("filteringCheckedItemList", self.exploring_source_params_changed)]}
        except Exception:
            pass


    def _fix_toolbox_icons(self):
        """v3.1 Sprint 14: Fix toolBox_tabTools icons with absolute paths."""
        icons = {0: "filter_multi.png", 1: "save.png", 2: "parameters.png"}
        for index, icon_file in icons.items():
            icon_path = os.path.join(self.plugin_dir, "icons", icon_file)
            if os.path.exists(icon_path):
                icon = get_themed_icon(icon_path) if ICON_THEME_AVAILABLE else QtGui.QIcon(icon_path)
                self.toolBox_tabTools.setItemIcon(index, icon)


    def setupUiCustom(self):
        """v4.0 Sprint 15: Setup custom UI - splitter, dimensions, tabs, icons, tooltips."""
        self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection = QgsCheckableComboBoxFeaturesListPickerWidget(self.CONFIG_DATA, self)
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
        """v3.1 Sprint 14: Load icons for all PushButton widgets from config."""
        try:
            pb_config = self.CONFIG_DATA.get("APP", {}).get("DOCKWIDGET", {}).get("PushButton", {})
            icons_config = pb_config.get("ICONS", {})
            sizes = pb_config.get("ICONS_SIZES", {})
            action_size = sizes.get("ACTION", {}).get("value", 24)
            other_size = sizes.get("OTHERS", {}).get("value", 20)
            if not icons_config:
                return
            for widget_group in ["ACTION", "EXPLORING", "FILTERING", "EXPORTING"]:
                icon_size = action_size if widget_group == "ACTION" else other_size
                for widget_name, icon_file in icons_config.get(widget_group, {}).items():
                    widget_attr = self._get_widget_attr_name(widget_group, widget_name)
                    if hasattr(self, widget_attr):
                        widget = getattr(self, widget_attr)
                        icon_path = os.path.join(self.plugin_dir, "icons", icon_file)
                        if os.path.exists(icon_path):
                            icon = get_themed_icon(icon_path) if ICON_THEME_AVAILABLE else QtGui.QIcon(icon_path)
                            widget.setIcon(icon)
                            widget.setIconSize(QtCore.QSize(icon_size, icon_size))
        except Exception:
            pass
    
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
        """v3.1 Sprint 14: Setup main splitter between frames."""
        from .ui.config import UIConfig
        try:
            self.main_splitter = self.splitter_main
            cfg = UIConfig.get_config('splitter')
            handle_width = cfg.get('handle_width', 6)
            handle_margin = cfg.get('handle_margin', 40)
            self.main_splitter.setChildrenCollapsible(cfg.get('collapsible', False))
            self.main_splitter.setHandleWidth(handle_width)
            self.main_splitter.setOpaqueResize(cfg.get('opaque_resize', True))
            self.main_splitter.setStyleSheet(f"""
                QSplitter::handle:vertical {{
                    background-color: #d0d0d0; height: {handle_width - 2}px;
                    margin: 2px {handle_margin}px; border-radius: {(handle_width - 2) // 2}px;
                }}
                QSplitter::handle:vertical:hover {{ background-color: #3498db; }}""")
            self._apply_splitter_frame_policies()
            self.main_splitter.setStretchFactor(0, cfg.get('exploring_stretch', 2))
            self.main_splitter.setStretchFactor(1, cfg.get('toolset_stretch', 5))
            self._set_initial_splitter_sizes()
        except Exception:
            self.main_splitter = None
    
    def _apply_splitter_frame_policies(self):
        """v3.1 Sprint 14: Apply size policies to splitter frames."""
        from .ui.config import UIConfig
        from qgis.PyQt.QtWidgets import QSizePolicy
        policy_map = {'Fixed': QSizePolicy.Fixed, 'Minimum': QSizePolicy.Minimum,
                      'Maximum': QSizePolicy.Maximum, 'Preferred': QSizePolicy.Preferred,
                      'Expanding': QSizePolicy.Expanding, 'MinimumExpanding': QSizePolicy.MinimumExpanding,
                      'Ignored': QSizePolicy.Ignored}
        for frame_name, defaults in [('frame_exploring', ('Preferred', 'Minimum')),
                                      ('frame_toolset', ('Preferred', 'Expanding'))]:
            if hasattr(self, frame_name):
                cfg = UIConfig.get_config(frame_name) or {}
                h = policy_map.get(cfg.get('size_policy_h', defaults[0]), QSizePolicy.Preferred)
                v = policy_map.get(cfg.get('size_policy_v', defaults[1]), QSizePolicy.Preferred)
                getattr(self, frame_name).setSizePolicy(h, v)
    
    def _set_initial_splitter_sizes(self):
        """v3.1 Sprint 14: Set initial splitter sizes based on ratios."""
        from .ui.config import UIConfig
        cfg = UIConfig.get_config('splitter')
        exp_ratio = cfg.get('initial_exploring_ratio', 0.50)
        tool_ratio = cfg.get('initial_toolset_ratio', 0.50)
        total = self.main_splitter.height() if self.main_splitter.height() >= 100 else 600
        self.main_splitter.setSizes([int(total * exp_ratio), int(total * tool_ratio)])


    def apply_dynamic_dimensions(self):
        """v3.1 Sprint 14: Apply dynamic dimensions to widgets."""
        if self._dimensions_manager is not None:
            try:
                self._dimensions_manager.apply()
                return
            except Exception:
                pass
        try:
            self._apply_dockwidget_dimensions()
            self._apply_widget_dimensions()
            self._apply_frame_dimensions()
            self._harmonize_checkable_pushbuttons()
            if self._spacing_manager is not None:
                try:
                    self._spacing_manager.apply()
                except Exception:
                    self._apply_layout_spacing()
                    self._harmonize_spacers()
                    self._adjust_row_spacing()
            else:
                self._apply_layout_spacing()
                self._harmonize_spacers()
                self._adjust_row_spacing()
            self._apply_qgis_widget_dimensions()
            self._align_key_layouts()
        except Exception:
            pass
    
    def _apply_dockwidget_dimensions(self):
        """v3.1 Sprint 14: Apply minimum size to dockwidget based on profile."""
        from .ui.config import UIConfig
        from qgis.PyQt.QtCore import QSize
        min_w, min_h = UIConfig.get_config('dockwidget', 'min_width'), UIConfig.get_config('dockwidget', 'min_height')
        pref_w, pref_h = UIConfig.get_config('dockwidget', 'preferred_width'), UIConfig.get_config('dockwidget', 'preferred_height')
        if min_w and min_h:
            self.setMinimumSize(QSize(min_w, min_h))
        if pref_w and pref_h:
            if self.size().width() > pref_w or self.size().height() > pref_h:
                self.resize(pref_w, pref_h)
    
    def _apply_widget_dimensions(self):
        """v3.1 Sprint 14: Apply dimensions to standard Qt widgets."""
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
    
    def _apply_frame_dimensions(self):
        """v3.1 Sprint 14: Apply dimensions to frames and containers."""
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
        if hasattr(self, 'frame_exploring'):
            self.frame_exploring.setMinimumHeight(exp_cfg.get('min_height', 120))
            self.frame_exploring.setMaximumHeight(exp_cfg.get('max_height', 350))
            self.frame_exploring.setSizePolicy(policy_map.get(exp_cfg.get('size_policy_h', 'Preferred'), QSizePolicy.Preferred),
                                               policy_map.get(exp_cfg.get('size_policy_v', 'Minimum'), QSizePolicy.Minimum))
        ts_cfg = UIConfig.get_config('frame_toolset') or {}
        if hasattr(self, 'frame_toolset'):
            self.frame_toolset.setMinimumHeight(ts_cfg.get('min_height', 200))
            self.frame_toolset.setMaximumHeight(ts_cfg.get('max_height', 16777215))
            self.frame_toolset.setSizePolicy(policy_map.get(ts_cfg.get('size_policy_h', 'Preferred'), QSizePolicy.Preferred),
                                             policy_map.get(ts_cfg.get('size_policy_v', 'Expanding'), QSizePolicy.Expanding))
        flt_cfg = UIConfig.get_config('frame_filtering') or {}
        if hasattr(self, 'frame_filtering'):
            self.frame_filtering.setMinimumHeight(flt_cfg.get('min_height', 180))
    
    def _harmonize_checkable_pushbuttons(self):
        """v3.1 Sprint 14: Delegate to UILayoutController."""
        if self._controller_integration and self._controller_integration.delegate_harmonize_checkable_pushbuttons():
            return
    
    def _apply_layout_spacing(self):
        """v3.1 Sprint 14: Delegate to UILayoutController."""
        if self._controller_integration and self._controller_integration.delegate_apply_layout_spacing():
            return
    
    def _harmonize_spacers(self):
        """v3.1 Sprint 13: Simplified - harmonize vertical spacers across key widgets."""
        try:
            from qgis.PyQt.QtWidgets import QSpacerItem
            from .ui.elements import get_spacer_size
            from .ui.config import UIConfig, DisplayProfile
            
            is_compact = UIConfig._active_profile == DisplayProfile.COMPACT
            spacer_sizes = {
                'exploring': get_spacer_size('verticalSpacer_exploring_tab_top', is_compact),
                'filtering': get_spacer_size('verticalSpacer_filtering_keys_field_top', is_compact),
                'exporting': get_spacer_size('verticalSpacer_exporting_keys_field_top', is_compact)
            }
            sections = {'exploring': 'widget_exploring_keys', 'filtering': 'widget_filtering_keys', 'exporting': 'widget_exporting_keys'}
            
            for section_name, widget_name in sections.items():
                target_h = spacer_sizes.get(section_name, 4)
                if hasattr(self, widget_name):
                    layout = getattr(self, widget_name).layout()
                    if layout:
                        for i in range(layout.count()):
                            item = layout.itemAt(i)
                            if item and hasattr(item, 'layout') and item.layout():
                                for j in range(item.layout().count()):
                                    nested = item.layout().itemAt(j)
                                    if nested and isinstance(nested, QSpacerItem):
                                        nested.changeSize(20, target_h, nested.sizePolicy().horizontalPolicy(), nested.sizePolicy().verticalPolicy())
        except Exception:
            pass
    
    def _apply_qgis_widget_dimensions(self):
        """v3.1 Sprint 13: Simplified - apply dimensions to QGIS custom widgets."""
        try:
            from qgis.PyQt.QtWidgets import QSizePolicy
            from qgis.gui import QgsPropertyOverrideButton
            from .ui.config import UIConfig
            
            cb_h = UIConfig.get_config('combobox', 'height') or 24
            in_h = UIConfig.get_config('input', 'height') or 24
            
            # Apply to standard QGIS widgets
            for cls in [QgsFeaturePickerWidget, QgsFieldExpressionWidget, QgsProjectionSelectionWidget, QgsMapLayerComboBox, QgsFieldComboBox, QgsCheckableComboBox]:
                for w in self.findChildren(cls):
                    w.setMinimumHeight(cb_h)
                    w.setMaximumHeight(cb_h)
                    w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            # QgsPropertyOverrideButton - fixed 22px
            for w in self.findChildren(QgsPropertyOverrideButton):
                w.setFixedSize(22, 22)
                w.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        except Exception:
            pass
    
    def _align_key_layouts(self):
        """v3.1 Sprint 14: Delegate to UILayoutController."""
        if self._controller_integration and self._controller_integration.delegate_align_key_layouts():
            return
    
    def _adjust_row_spacing(self):
        """v3.1 Sprint 14: Adjust row spacing for filtering/exporting alignment."""
        try:
            from qgis.PyQt.QtWidgets import QSpacerItem
            from .ui.elements import get_spacer_size
            from .ui.config import UIConfig, DisplayProfile
            is_compact = UIConfig._active_profile == DisplayProfile.COMPACT
            spacing = UIConfig.get_config('layout', 'spacing_frame') or 4
            spacers = {'filtering': get_spacer_size('verticalSpacer_filtering_keys_field_top', is_compact),
                       'exporting': get_spacer_size('verticalSpacer_exporting_keys_field_top', is_compact)}
            for name, layout_attr in [('filtering', 'verticalLayout_filtering_values'),
                                       ('exporting', 'verticalLayout_exporting_values')]:
                if hasattr(self, layout_attr):
                    layout = getattr(self, layout_attr)
                    target = spacers.get(name, 4)
                    for i in range(layout.count()):
                        item = layout.itemAt(i)
                        if item and isinstance(item, QSpacerItem):
                            item.changeSize(item.sizeHint().width(), target,
                                          item.sizePolicy().horizontalPolicy(), item.sizePolicy().verticalPolicy())
                    layout.setSpacing(spacing)
        except Exception:
            pass

    def _setup_backend_indicator(self):
        """v3.1 Sprint 15: Create header bar with favorites and backend indicators."""
        self.frame_header = QtWidgets.QFrame(self.dockWidgetContents)
        self.frame_header.setObjectName("frame_header")
        self.frame_header.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.frame_header.setMaximumHeight(22)
        self.frame_header.setMinimumHeight(18)
        
        header_layout = QtWidgets.QHBoxLayout(self.frame_header)
        header_layout.setContentsMargins(10, 1, 10, 1)
        header_layout.setSpacing(8)
        header_layout.addSpacerItem(QtWidgets.QSpacerItem(40, 10, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))
        
        self.plugin_title_label = None
        
        # Favorites and backend indicators with common badge style
        badge_base = "color:white;font-size:9pt;font-weight:600;padding:3px 10px;border-radius:12px;border:none;"
        
        self.favorites_indicator_label = self._create_indicator_label("label_favorites_indicator", "★", 
            badge_base + "background-color:#f39c12;", badge_base + "background-color:#d68910;",
            "★ Favorites\nClick to manage", self._on_favorite_indicator_clicked, 35)
        header_layout.addWidget(self.favorites_indicator_label)
        
        self.backend_indicator_label = self._create_indicator_label("label_backend_indicator", 
            "OGR" if self.has_loaded_layers else "...",
            badge_base + "background-color:#3498db;", badge_base + "background-color:#2980b9;",
            "Click to change backend", self._on_backend_indicator_clicked, 40)
        header_layout.addWidget(self.backend_indicator_label)
        
        self.forced_backends = {}
        if hasattr(self, 'verticalLayout_8'):
            self.verticalLayout_8.insertWidget(0, self.frame_header)
    
    def _create_indicator_label(self, name, text, style, hover_style, tooltip, click_handler, min_width):
        """v3.1 Sprint 15: Create styled indicator label."""
        label = QtWidgets.QLabel(self.frame_header)
        label.setObjectName(name)
        label.setText(text)
        label.setStyleSheet(f"QLabel#{name}{{{style}}}QLabel#{name}:hover{{{hover_style}}}")
        label.setAlignment(Qt.AlignCenter)
        label.setMinimumWidth(min_width)
        label.setMaximumHeight(20)
        label.setCursor(Qt.PointingHandCursor)
        label.setToolTip(tooltip)
        label.mousePressEvent = click_handler
        return label
    
    def _on_backend_indicator_clicked(self, event):
        """v4.0 Sprint 13: Simplified - delegates to BackendController."""
        if self._controller_integration and self._controller_integration.backend_controller:
            if self._controller_integration.delegate_handle_backend_click():
                return
        self._on_backend_indicator_clicked_legacy(event)
    
    def _on_backend_indicator_clicked_legacy(self, event):
        """v4.0 Sprint 13: Simplified legacy fallback - just logs warning."""
        logger.warning("_on_backend_indicator_clicked_legacy called - controller may not be working")
        show_warning("FilterMate", "Backend controller not available - please report this issue")

    def _on_favorite_indicator_clicked(self, event):
        """v4.0 Sprint 7: One-liner wrapper."""
        if self._controller_integration and self._controller_integration._favorites_controller:
            self._controller_integration._favorites_controller.handle_indicator_clicked()
    
    def _add_current_to_favorites(self):
        """v4.0 Sprint 7: One-liner wrapper."""
        if self._controller_integration and self._controller_integration._favorites_controller:
            self._controller_integration._favorites_controller.add_current_to_favorites()
    
    def _apply_favorite(self, favorite_id: str):
        """v4.0 Sprint 7: One-liner wrapper."""
        if self._controller_integration and self._controller_integration._favorites_controller:
            self._controller_integration._favorites_controller.apply_favorite(favorite_id)

    def _show_favorites_manager_dialog(self):
        """v4.0 Sprint 13: Delegate to FavoritesController."""
        if not (self._controller_integration and self._controller_integration.delegate_favorites_show_manager_dialog()):
            show_warning("FilterMate", "Favorites manager not available")
    
    def _export_favorites(self):
        """v4.0 Sprint 12: Delegate to FavoritesController."""
        if self._controller_integration and self._controller_integration._favorites_controller:
            self._controller_integration._favorites_controller.export_favorites()
    
    def _import_favorites(self):
        """v4.0 Sprint 12: Delegate to FavoritesController."""
        if self._controller_integration and self._controller_integration._favorites_controller:
            result = self._controller_integration._favorites_controller.import_favorites()
            if result:
                self._update_favorite_indicator()
    
    def _update_favorite_indicator(self):
        """v3.1 Sprint 17: Update the favorites indicator badge with current count."""
        if not hasattr(self, 'favorites_indicator_label') or not self.favorites_indicator_label: return
        fm = getattr(self, '_favorites_manager', None)
        count = fm.count if fm else 0
        
        if count > 0:
            self.favorites_indicator_label.setText(f"★ {count}")
            self.favorites_indicator_label.setToolTip(f"★ {count} Favorites saved\nClick to apply or manage")
            self.favorites_indicator_label.setStyleSheet("QLabel#label_favorites_indicator { color: white; font-size: 9pt; font-weight: 600; padding: 3px 10px; border-radius: 12px; border: none; background-color: #f39c12; } QLabel#label_favorites_indicator:hover { background-color: #d68910; }")
        else:
            self.favorites_indicator_label.setText("★")
            self.favorites_indicator_label.setToolTip("★ No favorites saved\nClick to add current filter")
            self.favorites_indicator_label.setStyleSheet("QLabel#label_favorites_indicator { color: #95a5a6; font-size: 9pt; font-weight: 600; padding: 3px 10px; border-radius: 12px; border: none; background-color: #ecf0f1; } QLabel#label_favorites_indicator:hover { background-color: #d5dbdb; }")
        self.favorites_indicator_label.adjustSize()

    def _get_available_backends_for_layer(self, layer):
        """v4.0 Sprint 12: Delegate to BackendController."""
        if self._controller_integration and self._controller_integration._backend_controller:
            return self._controller_integration._backend_controller.get_available_backends_for_layer(layer)
        return [('ogr', 'OGR', '📁')]  # Fallback
    
    def _detect_current_backend(self, layer):
        """v4.0 Sprint 12: Delegate to BackendController."""
        if self._controller_integration and self._controller_integration._backend_controller:
            return self._controller_integration._backend_controller.get_current_backend(layer)
        return 'ogr'  # Fallback

    def _set_forced_backend(self, layer_id, backend_type):
        """v4.0 Sprint 12: Delegate to BackendController."""
        if self._controller_integration and self._controller_integration._backend_controller:
            self._controller_integration._backend_controller.set_forced_backend(layer_id, backend_type)

    def _force_backend_for_all_layers(self, backend_type):
        """v4.0 Sprint 12: Delegate to BackendController."""
        if self._controller_integration and self._controller_integration._backend_controller:
            count = self._controller_integration._backend_controller.force_backend_for_all_layers(backend_type)
            show_success("FilterMate", f"Forced {backend_type.upper()} for {count} layers")
        else:
            show_warning("FilterMate", "Backend controller not available")

    def get_forced_backend_for_layer(self, layer_id):
        """v4.0 Sprint 12: Delegate to BackendController."""
        if self._controller_integration and self._controller_integration._backend_controller:
            return self._controller_integration._backend_controller.forced_backends.get(layer_id)
        return None
    
    def _get_optimal_backend_for_layer(self, layer):
        """v4.0 Sprint 12: Delegate to BackendController."""
        if self._controller_integration and self._controller_integration._backend_controller:
            return self._controller_integration._backend_controller._get_optimal_backend_for_layer(layer)
        return 'ogr'  # Fallback

    # ========================================
    # POSTGRESQL MAINTENANCE METHODS
    # ========================================
    
    def _get_pg_session_context(self):
        """v4.0 Sprint 13: WRAPPER - delegate to BackendController."""
        if self._controller_integration and self._controller_integration._backend_controller:
            return self._controller_integration._backend_controller.get_pg_session_context()
        return None, None, None, None
    
    def _toggle_pg_auto_cleanup(self):
        """v4.0 Sprint 13: WRAPPER - delegate to BackendController."""
        if self._controller_integration and self._controller_integration._backend_controller:
            enabled = self._controller_integration._backend_controller.toggle_pg_auto_cleanup()
            msg = "PostgreSQL auto-cleanup enabled" if enabled else "PostgreSQL auto-cleanup disabled"
            (show_success if enabled else show_info)("FilterMate", msg)
    
    def _cleanup_postgresql_session_views(self):
        """v4.0 Sprint 13: WRAPPER - delegate to BackendController."""
        if self._controller_integration and self._controller_integration._backend_controller:
            success = self._controller_integration._backend_controller.cleanup_postgresql_session_views()
            if success:
                show_success("FilterMate", "PostgreSQL session views cleaned up")
            else:
                show_warning("FilterMate", "No views to clean or cleanup failed")
        else:
            show_warning("FilterMate", "Backend controller not available")
    
    def _cleanup_postgresql_schema_if_empty(self):
        """v4.0 Sprint 13: WRAPPER - delegate to BackendController."""
        from qgis.PyQt.QtWidgets import QMessageBox
        if self._controller_integration and self._controller_integration._backend_controller:
            ctrl = self._controller_integration._backend_controller
            info = ctrl.get_postgresql_session_info()
            
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
            
            success = ctrl.cleanup_postgresql_schema_if_empty(force=True)
            if success:
                show_success("FilterMate", f"Schema '{info.get('schema')}' dropped successfully")
            else:
                show_warning("FilterMate", "Schema cleanup failed")
        else:
            show_warning("FilterMate", "Backend controller not available")
    
    def _show_postgresql_session_info(self):
        """v4.0 Sprint 13: WRAPPER - delegate to BackendController."""
        from qgis.PyQt.QtWidgets import QMessageBox
        if self._controller_integration and self._controller_integration._backend_controller:
            info = self._controller_integration._backend_controller.get_postgresql_session_info()
            
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
        """v4.0 Sprint 12: Delegate to BackendController."""
        if self._controller_integration and self._controller_integration._backend_controller:
            enabled = self._controller_integration._backend_controller.toggle_optimization_enabled()
            (show_success if enabled else show_info)("FilterMate", f"Auto-optimization {'enabled' if enabled else 'disabled'}")
    
    def _toggle_centroid_auto(self):
        """v4.0 Sprint 12: Delegate to BackendController."""
        if self._controller_integration and self._controller_integration._backend_controller:
            enabled = self._controller_integration._backend_controller.toggle_centroid_auto()
            (show_success if enabled else show_info)("FilterMate", f"Auto-centroid {'enabled' if enabled else 'disabled'}")
    
    def _toggle_optimization_ask_before(self):
        """v3.1 Sprint 15: Toggle confirmation dialog."""
        self._optimization_ask_before = not getattr(self, '_optimization_ask_before', True)
        (show_success if self._optimization_ask_before else show_info)("FilterMate", "Confirmation " + ("enabled" if self._optimization_ask_before else "disabled"))
    
    def _analyze_layer_optimizations(self):
        """v3.1 Sprint 15: Analyze layer and show optimization recommendations."""
        if not self.current_layer:
            show_warning("FilterMate", "No layer selected. Please select a layer first.")
            return
        
        try:
            from .core.services.auto_optimizer import LayerAnalyzer, AutoOptimizer, AUTO_OPTIMIZER_AVAILABLE
            if not AUTO_OPTIMIZER_AVAILABLE:
                show_warning("FilterMate", "Auto-optimizer module not available")
                return
            
            layer_analysis = LayerAnalyzer().analyze_layer(self.current_layer)
            if not layer_analysis:
                show_info("FilterMate", f"Could not analyze layer '{self.current_layer.name()}'")
                return
            
            # Get buffer and centroid status
            has_buffer = getattr(self, 'mQgsDoubleSpinBox_filtering_buffer_value', None) and self.mQgsDoubleSpinBox_filtering_buffer_value.value() != 0.0
            has_buffer_type = getattr(self, 'checkBox_filtering_buffer_type', None) and self.checkBox_filtering_buffer_type.isChecked()
            
            recommendations = AutoOptimizer().get_recommendations(
                layer_analysis, user_centroid_enabled=self._is_centroid_already_enabled(self.current_layer),
                has_buffer=has_buffer, has_buffer_type=has_buffer_type, is_source_layer=True)
            
            if not recommendations:
                show_success("FilterMate", f"Layer '{self.current_layer.name()}' is already optimally configured.\nType: {layer_analysis.location_type.value}\nFeatures: {layer_analysis.feature_count:,}")
                return
            
            from .modules.optimization_dialogs import OptimizationRecommendationDialog
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
            from .modules.backend_optimization_widget import BackendOptimizationDialog
            dialog = BackendOptimizationDialog(self)
            if dialog.exec_():
                self._apply_optimization_dialog_settings(dialog.get_settings())
        except ImportError:
            try:
                from .modules.optimization_dialogs import OptimizationSettingsDialog
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
        """v3.1 Sprint 15: Show backend optimization dialog."""
        try:
            from .modules.backend_optimization_widget import BackendOptimizationDialog
            dialog = BackendOptimizationDialog(self)
            if not dialog.exec_():
                return
            
            all_settings = dialog.get_settings()
            self._backend_optimization_settings = all_settings
            
            global_s = all_settings.get('global', {})
            self._optimization_enabled = global_s.get('auto_optimization_enabled', True)
            self._centroid_auto_enabled = global_s.get('auto_centroid', {}).get('enabled', True)
            self._optimization_ask_before = global_s.get('ask_before_apply', True)
            
            pg_mv = all_settings.get('postgresql', {}).get('materialized_views', {})
            self._pg_auto_cleanup_enabled = pg_mv.get('auto_cleanup', True)
            
            if not hasattr(self, '_optimization_thresholds'): self._optimization_thresholds = {}
            self._optimization_thresholds['centroid_distant'] = global_s.get('auto_centroid', {}).get('distant_threshold', 5000)
            self._optimization_thresholds['mv_threshold'] = pg_mv.get('threshold', 10000)
            
            show_success("FilterMate", self.tr("Backend optimizations configured"))
        except ImportError as e:
            show_warning("FilterMate", f"Dialog not available: {e}")
        except Exception as e:
            show_warning("FilterMate", f"Error: {str(e)[:50]}")
    
    def get_backend_optimization_setting(self, backend: str, setting_path: str, default=None):
        """v3.1 Sprint 15: Get backend optimization setting by path."""
        current = getattr(self, '_backend_optimization_settings', {}).get(backend, {})
        for part in setting_path.split('.'):
            current = current.get(part, default) if isinstance(current, dict) else default
        return current
    
    def _is_centroid_already_enabled(self, layer) -> bool:
        """v4.0 Sprint 14: Check if centroid optimization is already enabled."""
        layer_id = layer.id() if layer else None
        if hasattr(self, '_layer_centroid_overrides') and layer_id:
            if self._layer_centroid_overrides.get(layer_id, False):
                return True
        if hasattr(self, 'checkBox_filtering_use_centroids_distant_layers') and self.checkBox_filtering_use_centroids_distant_layers.isChecked():
            return True
        if hasattr(self, 'checkBox_filtering_use_centroids_source_layer') and self.checkBox_filtering_use_centroids_source_layer.isChecked():
            return True
        return False
    
    def should_use_centroid_for_layer(self, layer) -> bool:
        """v3.1 Sprint 17: Check if centroid optimization should be used for a layer."""
        if hasattr(self, '_layer_centroid_overrides'):
            override = self._layer_centroid_overrides.get(layer.id() if layer else None)
            if override is not None: return override
        if not getattr(self, '_optimization_enabled', True) or not getattr(self, '_centroid_auto_enabled', True): return False
        try:
            from .core.services.auto_optimizer import LayerAnalyzer, LayerLocationType, AUTO_OPTIMIZER_AVAILABLE
            if not AUTO_OPTIMIZER_AVAILABLE: return False
            analysis = LayerAnalyzer().analyze_layer(layer)
            if not analysis: return False
            threshold = get_optimization_thresholds(ENV_VARS).get('centroid_optimization_threshold', 1000)
            if hasattr(self, '_optimization_thresholds'): threshold = self._optimization_thresholds.get('centroid_distant', threshold)
            return analysis.location_type in (LayerLocationType.REMOTE_SERVICE, LayerLocationType.REMOTE_DATABASE) and analysis.feature_count >= threshold
        except: return False
    
    def get_optimization_state(self) -> dict:
        """v4.0 Sprint 14: Get current optimization state for storage/restore."""
        return {
            'enabled': getattr(self, '_optimization_enabled', True),
            'centroid_auto': getattr(self, '_centroid_auto_enabled', True),
            'ask_before': getattr(self, '_optimization_ask_before', True),
            'thresholds': getattr(self, '_optimization_thresholds', {}),
            'layer_overrides': getattr(self, '_layer_centroid_overrides', {}),
        }
    
    def restore_optimization_state(self, state: dict):
        """v4.0 Sprint 14: Restore optimization state from saved settings."""
        self._optimization_enabled = state.get('enabled', True)
        self._centroid_auto_enabled = state.get('centroid_auto', True)
        self._optimization_ask_before = state.get('ask_before', True)
        self._optimization_thresholds = state.get('thresholds', {})
        self._layer_centroid_overrides = state.get('layer_overrides', {})
        logger.info(f"Restored optimization state: enabled={self._optimization_enabled}")

    def auto_select_optimal_backends(self):
        """v4.0 Sprint 12: Delegate to BackendController."""
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
        """v4.0 Sprint 14: Delegate to ActionBarManager."""
        if not hasattr(self, 'frame_actions'):
            return
        if self._action_bar_manager:
            self._action_bar_manager.setup()
        else:
            self.frame_actions.show()

    def _get_action_bar_position(self):
        """v4.0 Sprint 10: WRAPPER - delegate to ActionBarManager."""
        if self._action_bar_manager:
            return self._action_bar_manager.get_position()
        return 'top'

    def _get_action_bar_vertical_alignment(self):
        """v4.0 Sprint 10: WRAPPER - delegate to ActionBarManager."""
        if self._action_bar_manager:
            return self._action_bar_manager._read_alignment_from_config()
        return 'top'

    def _apply_action_bar_position(self, position):
        """v4.0 Sprint 10: WRAPPER - delegate to ActionBarManager."""
        if self._action_bar_manager:
            self._action_bar_manager.set_position(position)
            self._action_bar_manager.apply_position()

    def _adjust_header_for_side_position(self, position):
        """v4.0 Sprint 10: WRAPPER - delegate to ActionBarManager."""
        if self._action_bar_manager:
            self._action_bar_manager.adjust_header_for_side_position()

    def _restore_header_from_wrapper(self):
        """v4.0 Sprint 10: WRAPPER - delegate to ActionBarManager."""
        if self._action_bar_manager:
            self._action_bar_manager.restore_header_from_wrapper()


    def _clear_action_bar_layout(self):
        """v4.0 Sprint 10: WRAPPER - delegate to ActionBarManager."""
        if self._action_bar_manager:
            self._action_bar_manager.clear_layout()

    def _create_horizontal_action_layout(self, action_buttons):
        """v4.0 Sprint 10: WRAPPER - delegate to ActionBarManager."""
        if self._action_bar_manager:
            self._action_bar_manager.create_horizontal_layout(action_buttons)

    def _create_vertical_action_layout(self, action_buttons):
        """v4.0 Sprint 10: WRAPPER - delegate to ActionBarManager."""
        if self._action_bar_manager:
            self._action_bar_manager.create_vertical_layout(action_buttons)

    def _apply_action_bar_size_constraints(self, position):
        """v4.0 Sprint 10: WRAPPER - delegate to ActionBarManager."""
        if self._action_bar_manager:
            self._action_bar_manager.apply_size_constraints()

    def _reposition_action_bar_in_main_layout(self, position):
        """v4.0 Sprint 10: WRAPPER - delegate to ActionBarManager."""
        if self._action_bar_manager:
            self._action_bar_manager.reposition_in_main_layout()

    def _create_horizontal_wrapper_for_side_action_bar(self, position):
        """v4.0 Sprint 10: WRAPPER - delegate to ActionBarManager."""
        if self._action_bar_manager:
            self._action_bar_manager._create_side_wrapper()

    def _restore_side_action_bar_layout(self):
        """v4.0 Sprint 10: WRAPPER - delegate to ActionBarManager."""
        if self._action_bar_manager:
            self._action_bar_manager.restore_side_action_bar_layout()

    def _restore_original_layout(self):
        """v4.0 Sprint 10: WRAPPER - delegate to ActionBarManager."""
        if self._action_bar_manager:
            self._action_bar_manager.restore_original_layout()

    def _setup_exploring_tab_widgets(self):
        """v3.1 Sprint 13: Configure Exploring tab widgets."""
        self.horizontalLayout_exploring_multiple_feature_picker.insertWidget(
            0, self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection, 1)
        field_filters = QgsFieldProxyModel.AllTypes
        for widget in [self.mFieldExpressionWidget_exploring_single_selection,
                       self.mFieldExpressionWidget_exploring_multiple_selection,
                       self.mFieldExpressionWidget_exploring_custom_selection]:
            widget.setFilters(field_filters)
        self._setup_expression_widget_direct_connections()

    def _setup_expression_widget_direct_connections(self):
        """v3.1 Sprint 13: Connect fieldChanged signals for expression widgets."""
        connections = [
            (self.mFieldExpressionWidget_exploring_single_selection, "single_selection"),
            (self.mFieldExpressionWidget_exploring_multiple_selection, "multiple_selection"),
            (self.mFieldExpressionWidget_exploring_custom_selection, "custom_selection")
        ]
        for widget, groupbox in connections:
            widget.fieldChanged.connect(lambda f, g=groupbox: self._schedule_expression_change(g, f))
    
    def _schedule_expression_change(self, groupbox: str, expression: str):
        """v3.1 Sprint 14: Schedule debounced expression change."""
        self._pending_expression_change = (groupbox, expression)
        self._set_expression_loading_state(True, groupbox)
        self._expression_debounce_timer.start()
    
    def _execute_debounced_expression_change(self):
        """v3.1 Sprint 14: Execute pending expression change after debounce."""
        if self._pending_expression_change is None:
            self._set_expression_loading_state(False)
            return
        groupbox, expression = self._pending_expression_change
        self._pending_expression_change = None
        try:
            property_key = f"{groupbox}_expression"
            custom_functions = {"ON_CHANGE": lambda x: self._execute_expression_params_change(groupbox)}
            self.layer_property_changed(property_key, expression, custom_functions)
        except Exception:
            self._set_expression_loading_state(False)
    
    def _execute_expression_params_change(self, groupbox: str):
        """v3.1 Sprint 14: Execute expression params change with caching."""
        try:
            if groupbox in ("single_selection", "multiple_selection"):
                self._last_expression_change_source = groupbox
            if groupbox == "single_selection":
                try:
                    self.mFeaturePickerWidget_exploring_single_selection.update()
                except Exception:
                    pass
            elif groupbox == "multiple_selection":
                try:
                    widget = self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection
                    if widget and hasattr(widget, 'list_widgets') and self.current_layer:
                        layer_id = self.current_layer.id()
                        if layer_id in widget.list_widgets:
                            widget.list_widgets[layer_id].viewport().update()
                except Exception:
                    pass
            self.exploring_source_params_changed(groupbox_override=groupbox, change_source=groupbox)
        finally:
            self._set_expression_loading_state(False, groupbox)
    
    def _set_expression_loading_state(self, loading: bool, groupbox: str = None):
        """v3.1 Sprint 14: Update loading state for expression widgets."""
        self._expression_loading = loading
        try:
            cursor = Qt.WaitCursor if loading else Qt.PointingHandCursor
            widgets = []
            if groupbox in ("single_selection", None):
                widgets.extend([self.mFieldExpressionWidget_exploring_single_selection,
                              self.mFeaturePickerWidget_exploring_single_selection])
            if groupbox in ("multiple_selection", None):
                widgets.extend([self.mFieldExpressionWidget_exploring_multiple_selection,
                              self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection])
            if groupbox in ("custom_selection", None):
                widgets.append(self.mFieldExpressionWidget_exploring_custom_selection)
            for widget in widgets:
                if widget and hasattr(widget, 'setCursor'):
                    widget.setCursor(cursor)
        except Exception:
            pass
    
    def _get_cached_expression_result(self, layer_id: str, expression: str):
        """v4.0 Sprint 14: Get cached expression result (includes subsetString in key for multi-step filtering)."""
        import time
        layer = QgsProject.instance().mapLayer(layer_id)
        subset_string = layer.subsetString() if layer else ""
        cache_key = (layer_id, expression, subset_string)
        
        if cache_key not in self._expression_cache:
            return None
        
        features, timestamp = self._expression_cache[cache_key]
        current_time = time.time()
        
        # Check if cache entry has expired
        if current_time - timestamp > self._expression_cache_max_age:
            del self._expression_cache[cache_key]
            return None
        
        return features
    
    def _set_cached_expression_result(self, layer_id: str, expression: str, features):
        """v4.0 Sprint 14: Cache expression result with LRU eviction."""
        import time
        # Enforce cache size limit (LRU eviction)
        if len(self._expression_cache) >= self._expression_cache_max_size:
            # Remove oldest entry
            oldest_key = min(self._expression_cache.keys(), 
                           key=lambda k: self._expression_cache[k][1])
            del self._expression_cache[oldest_key]
        
        # v2.8.13: Include subsetString in cache key for multi-step filtering support
        layer = QgsProject.instance().mapLayer(layer_id)
        subset_string = layer.subsetString() if layer else ""
        cache_key = (layer_id, expression, subset_string)
        self._expression_cache[cache_key] = (features, time.time())
    
    def invalidate_expression_cache(self, layer_id: str = None):
        """v4.0 Sprint 14: Invalidate expression cache (layer_id=None clears all)."""
        if layer_id is None:
            self._expression_cache.clear()
            logger.debug("Cleared entire expression cache")
        else:
            keys_to_remove = [k for k in self._expression_cache.keys() if k[0] == layer_id]
            for key in keys_to_remove:
                del self._expression_cache[key]
            if keys_to_remove:
                logger.debug(f"Cleared {len(keys_to_remove)} cache entries for layer {layer_id}")

    def _setup_filtering_tab_widgets(self):
        """v3.1 Sprint 13: Simplified - configure widgets for Filtering tab."""
        self.comboBox_filtering_current_layer.setFilters(QgsMapLayerProxyModel.VectorLayer)
        
        icon_path = os.path.join(os.path.dirname(__file__), "icons", "centroid.png")
        if os.path.exists(icon_path) and hasattr(self, 'checkBox_filtering_use_centroids_source_layer'):
            self.checkBox_filtering_use_centroids_source_layer.setIcon(QtGui.QIcon(icon_path))
            self.checkBox_filtering_use_centroids_source_layer.setText("")
            self.checkBox_filtering_use_centroids_source_layer.setLayoutDirection(QtCore.Qt.RightToLeft)

        self.checkableComboBoxLayer_filtering_layers_to_filter = QgsCheckableComboBoxLayer(self.dockWidgetContents)
        
        self.checkBox_filtering_use_centroids_distant_layers = QtWidgets.QCheckBox(self.dockWidgetContents)
        self.checkBox_filtering_use_centroids_distant_layers.setText("")
        self.checkBox_filtering_use_centroids_distant_layers.setToolTip(self.tr("Use centroids instead of full geometries for distant layers"))
        self.checkBox_filtering_use_centroids_distant_layers.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        if os.path.exists(icon_path):
            self.checkBox_filtering_use_centroids_distant_layers.setIcon(QtGui.QIcon(icon_path))
        self.checkBox_filtering_use_centroids_distant_layers.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.checkBox_filtering_use_centroids_distant_layers.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        
        self.horizontalLayout_filtering_distant_layers = QtWidgets.QHBoxLayout()
        self.horizontalLayout_filtering_distant_layers.setSpacing(4)
        self.horizontalLayout_filtering_distant_layers.addWidget(self.checkableComboBoxLayer_filtering_layers_to_filter)
        self.horizontalLayout_filtering_distant_layers.addWidget(self.checkBox_filtering_use_centroids_distant_layers)
        self.verticalLayout_filtering_values.insertLayout(2, self.horizontalLayout_filtering_distant_layers)
        
        try:
            from .ui.config import UIConfig
            h = UIConfig.get_config('combobox', 'height')
            self.checkableComboBoxLayer_filtering_layers_to_filter.setMinimumHeight(h)
            self.checkableComboBoxLayer_filtering_layers_to_filter.setMaximumHeight(h)
        except Exception:
            pass

    def _setup_exporting_tab_widgets(self):
        """v3.1 Sprint 13: Simplified - configure widgets for Exporting tab."""
        self.checkableComboBoxLayer_exporting_layers = QgsCheckableComboBoxLayer(self.EXPORTING)
        
        if hasattr(self, 'verticalLayout_exporting_values'):
            self.verticalLayout_exporting_values.insertWidget(0, self.checkableComboBoxLayer_exporting_layers)
            self.verticalLayout_exporting_values.insertItem(1, QtWidgets.QSpacerItem(20, 4, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding))
        
        try:
            from .ui.config import UIConfig
            h = UIConfig.get_config('combobox', 'height')
            self.checkableComboBoxLayer_exporting_layers.setMinimumHeight(h)
            self.checkableComboBoxLayer_exporting_layers.setMaximumHeight(h)
        except Exception:
            pass
        
        for btn in ['pushButton_checkable_exporting_layers', 'pushButton_checkable_exporting_projection',
                    'pushButton_checkable_exporting_styles', 'pushButton_checkable_exporting_datatype',
                    'pushButton_checkable_exporting_output_folder', 'pushButton_checkable_exporting_zip']:
            if hasattr(self, btn):
                getattr(self, btn).setEnabled(False)
        
        self.iface.mapCanvas().setSelectionColor(QColor(237, 97, 62, 75))

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
        """v4.0 Sprint 15: Configure widgets via ConfigurationManager and setup controllers."""
        if self._configuration_manager is None:
            self._configuration_manager = ConfigurationManager(self)
        self.layer_properties_tuples_dict = self._configuration_manager.get_layer_properties_tuples_dict()
        self.export_properties_tuples_dict = self._configuration_manager.get_export_properties_tuples_dict()
        self.widgets = self._configuration_manager.configure_widgets()
        self.widgets_initialized = True
        logger.info(f"✓ Widgets fully initialized with {len(self.PROJECT_LAYERS)} layers")
        
        # Setup controllers
        if self._controller_integration:
            try:
                if self._controller_integration.setup():
                    self._controller_integration.sync_from_dockwidget()
                    logger.info("✓ Controller integration setup complete")
                else:
                    logger.debug("Controller integration setup returned False")
            except Exception as e:
                logger.warning(f"Controller integration setup failed: {e}")
        
        # Connect selectionChanged for initial layer
        if self.current_layer and not self.current_layer_selection_connection:
            try:
                self.current_layer.selectionChanged.connect(self.on_layer_selection_changed)
                self.current_layer_selection_connection = True
                logger.info(f"Connected selectionChanged signal for initial layer '{self.current_layer.name()}'")
            except (TypeError, RuntimeError) as e:
                logger.warning(f"Could not connect selectionChanged for initial layer: {e}")
        
        logger.debug("Emitting widgetsInitialized signal")
        self.widgetsInitialized.emit()
        self._setup_keyboard_shortcuts()
        
        # Process pending layers update
        if self._pending_layers_update:
            logger.debug(f"Pending layers update detected - refreshing UI with {len(self.PROJECT_LAYERS)} layers")
            self._pending_layers_update = False
            # Use QTimer with increased delay to ensure event loop has processed widgets_initialized
            # STABILITY FIX: Use weakref to prevent access violations
            pl = self.PROJECT_LAYERS
            pr = self.PROJECT
            weak_self = weakref.ref(self)
            def safe_layers_update():
                strong_self = weak_self()
                if strong_self is not None:
                    strong_self.get_project_layers_from_app(pl, pr)
            QTimer.singleShot(100, safe_layers_update)

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
        """v3.1 Sprint 17: Cancel pending configuration changes."""
        if not self.config_changes_pending or not self.pending_config_changes: return
        
        try:
            config_path = ENV_VARS.get('CONFIG_JSON_PATH', self.plugin_dir + '/config/config.json')
            with open(config_path, 'r') as f: self.CONFIG_DATA = json.load(f)
            
            self.config_model = JsonModel(data=self.CONFIG_DATA, editable_keys=False, editable_values=True, plugin_dir=self.plugin_dir)
            if hasattr(self, 'config_view') and self.config_view:
                self.config_view.setModel(self.config_model)
                self.config_view.model = self.config_model
            
            self.pending_config_changes, self.config_changes_pending = [], False
            if hasattr(self, 'buttonBox'): self.buttonBox.setEnabled(False)
        except Exception as e:
            show_error("FilterMate", f"Error cancelling changes: {str(e)}")


    def on_config_buttonbox_accepted(self):
        """Called when OK button is clicked.
        
        v3.1 STORY-2.5: Delegates to ConfigController if available.
        """
        logger.info("Configuration OK button clicked")
        # v3.1 STORY-2.5: Try controller delegation first
        if self._controller_integration is not None:
            if self._controller_integration.delegate_config_apply_pending_changes():
                return
        # Fallback to legacy
        self.apply_pending_config_changes()


    def on_config_buttonbox_rejected(self):
        """Called when Cancel button is clicked.
        
        v3.1 STORY-2.5: Delegates to ConfigController if available.
        """
        logger.info("Configuration Cancel button clicked")
        # v3.1 STORY-2.5: Try controller delegation first
        if self._controller_integration is not None:
            if self._controller_integration.delegate_config_cancel_pending_changes():
                return
        # Fallback to legacy
        self.cancel_pending_config_changes()


    def reload_configuration_model(self):

        if self.widgets_initialized is True:
            try:
                # Create new model
                self.config_model = JsonModel(data=self.CONFIG_DATA, editable_keys=False, editable_values=True, plugin_dir=self.plugin_dir)
                
                # Update view model - safe to call here since view already exists
                if hasattr(self, 'config_view') and self.config_view is not None:
                    self.config_view.setModel(self.config_model)
                    self.config_view.model = self.config_model
                
                # Save to file
                json_object = json.dumps(self.CONFIG_DATA, indent=4)
                config_json_path = ENV_VARS.get('CONFIG_JSON_PATH', self.plugin_dir + '/config/config.json')
                with open(config_json_path, 'w') as outfile:
                    outfile.write(json_object)
            except Exception as e:
                logger.error(f"Error reloading configuration model: {e}")
                import traceback
                logger.error(traceback.format_exc())


    def save_configuration_model(self):

        if self.widgets_initialized is True:

            self.CONFIG_DATA = self.config_model.serialize()
            json_object = json.dumps(self.CONFIG_DATA, indent=4)

            config_json_path = ENV_VARS.get('CONFIG_JSON_PATH', self.plugin_dir + '/config/config.json')
            with open(config_json_path, 'w') as outfile:
                outfile.write(json_object)


    def manage_configuration_model(self):
        """v4.0 Sprint 15: Setup config model, view, and signals."""
        try:
            self.config_model = JsonModel(data=self.CONFIG_DATA, editable_keys=False, editable_values=True, plugin_dir=self.plugin_dir)
            self.config_view = JsonView(self.config_model, self.plugin_dir)
            self.CONFIGURATION.layout().insertWidget(0, self.config_view)
            self.config_view.setAnimated(True)
            self.config_view.setEnabled(True)
            self.config_view.show()
            self.config_model.itemChanged.connect(self.data_changed_configuration_model)
            logger.info("Configuration model itemChanged signal connected")
            self._setup_reload_button()
            if hasattr(self, 'buttonBox'):
                self.buttonBox.setEnabled(False)
                logger.info("Configuration buttons disabled (no pending changes)")
                self.buttonBox.accepted.connect(self.on_config_buttonbox_accepted)
                self.buttonBox.rejected.connect(self.on_config_buttonbox_rejected)
                logger.info("Configuration button signals connected")
        except Exception as e:
            logger.error(f"Error creating configuration model: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _setup_reload_button(self):
        """v4.0 Sprint 15: Setup Reload Plugin button in config panel."""
        try:
            self.pushButton_reload_plugin = QtWidgets.QPushButton("🔄 Reload Plugin")
            self.pushButton_reload_plugin.setObjectName("pushButton_reload_plugin")
            self.pushButton_reload_plugin.setToolTip(QCoreApplication.translate("FilterMate", "Reload the plugin to apply layout changes (action bar position)"))
            self.pushButton_reload_plugin.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
            self.pushButton_reload_plugin.setMinimumHeight(30)
            self.pushButton_reload_plugin.clicked.connect(self._on_reload_button_clicked)
            config_layout = self.CONFIGURATION.layout()
            if config_layout:
                # Insert before the last widget (buttonBox)
                insert_index = config_layout.count() - 1  # Before buttonBox
                config_layout.insertWidget(insert_index, self.pushButton_reload_plugin)
                logger.info("Reload button added to configuration panel")
        except Exception as e:
            logger.error(f"Error setting up reload button: {e}")

    def _on_reload_button_clicked(self):
        """
        Handle reload button click - save configuration and reload plugin.
        """
        
        # First, apply any pending changes
        if self.config_changes_pending and self.pending_config_changes:
            self.apply_pending_config_changes()
        
        # Save configuration
        self.save_configuration_model()
        
        # Confirm reload
        from qgis.PyQt.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Reload Plugin",
            "Do you want to reload FilterMate to apply all configuration changes?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            self.reload_plugin()

        
    def manage_output_name(self):
        self.output_name = 'export'
        self.current_project_title = self.PROJECT.fileName().split('.')[0]
        self.current_project_path = self.PROJECT.homePath()
        if self.current_project_title is not None:
            self.output_name = 'export' + '_' + str(self.current_project_title)


    def set_widget_icon(self, config_widget_path):

        if self.widgets_initialized is True:

            if len(config_widget_path) == 6:

                config_path = self.CONFIG_DATA[config_widget_path[0]][config_widget_path[1]][config_widget_path[2]][config_widget_path[3]][config_widget_path[4]][config_widget_path[5]]

                if isinstance(config_path, dict):
                    if "ICON_ON_FALSE" in config_path:    
                        file = config_path["ICON_ON_FALSE"]
                        file_path = os.path.join(self.plugin_dir, "icons", file)
                        self.widgets[config_widget_path[4]][config_widget_path[5]]["ICON_ON_FALSE"] = file_path

                    if "ICON_ON_TRUE" in config_path:
                        file = config_path["ICON_ON_TRUE"]
                        file_path = os.path.join(self.plugin_dir, "icons", file)
                        self.widgets[config_widget_path[4]][config_widget_path[5]]["ICON_ON_TRUE"] = file_path

                elif isinstance(config_path, str):
                    file_path = os.path.join(self.plugin_dir, "icons", config_path)
                    self.widgets[config_widget_path[4]][config_widget_path[5]]["ICON"] = file_path

                # Use themed icon for dark mode support
                if ICON_THEME_AVAILABLE:
                    icon = get_themed_icon(file_path)
                else:
                    icon = QtGui.QIcon(file_path)
                self.widgets[config_widget_path[4]][config_widget_path[5]]["WIDGET"].setIcon(icon)


    def switch_widget_icon(self, widget_path, state):
        if state is True:
            icon_path = self.widgets[widget_path[0].upper()][widget_path[1].upper()]["ICON_ON_TRUE"]
        else:
            icon_path = self.widgets[widget_path[0].upper()][widget_path[1].upper()]["ICON_ON_FALSE"]
        
        # Use themed icon for dark mode support
        if ICON_THEME_AVAILABLE:
            icon = get_themed_icon(icon_path)
        else:
            icon = QtGui.QIcon(icon_path)
        self.widgets[widget_path[0].upper()][widget_path[1].upper()]["WIDGET"].setIcon(icon)


    def icon_per_geometry_type(self, geometry_type):
        """
        Get icon for geometry type with caching.
        
        Icons are cached statically to avoid repeated QgsLayerItem calls,
        improving performance when displaying multiple layers.
        
        Args:
            geometry_type (str): Geometry type string (e.g., 'GeometryType.Point')
        
        Returns:
            QIcon: Icon for the geometry type
        """
        # Check cache first
        if geometry_type in self._icon_cache:
            return self._icon_cache[geometry_type]
        
        # Calculate and cache the icon
        if geometry_type == 'GeometryType.Line':
            icon = QgsLayerItem.iconLine()
        elif geometry_type == 'GeometryType.Point':
            icon = QgsLayerItem.iconPoint()
        elif geometry_type == 'GeometryType.Polygon':
            icon = QgsLayerItem.iconPolygon()
        elif geometry_type == 'GeometryType.UnknownGeometry':
            icon = QgsLayerItem.iconTable()
        else:
            icon = QgsLayerItem.iconDefault()
        
        # Cache for future use
        self._icon_cache[geometry_type] = icon
        return icon
        
    def filtering_populate_predicates_chekableCombobox(self):
        """v3.1 Sprint 12: Simplified - populate geometric predicates combobox."""
        predicates = None
        if self._controller_integration:
            predicates = self._controller_integration.delegate_filtering_get_available_predicates()
        self.predicates = predicates or ["Intersect","Contain","Disjoint","Equal","Touch","Overlap","Are within","Cross"]
        self.widgets["FILTERING"]["GEOMETRIC_PREDICATES"]["WIDGET"].clear()
        self.widgets["FILTERING"]["GEOMETRIC_PREDICATES"]["WIDGET"].addItems(self.predicates)

    def filtering_populate_buffer_type_combobox(self):
        """v3.1 Sprint 12: Simplified - populate buffer type combobox."""
        buffer_types = None
        if self._controller_integration:
            buffer_types = self._controller_integration.delegate_filtering_get_available_buffer_types()
        self.widgets["FILTERING"]["BUFFER_TYPE"]["WIDGET"].clear()
        self.widgets["FILTERING"]["BUFFER_TYPE"]["WIDGET"].addItems(buffer_types or ["Round", "Flat", "Square"])
        if not self.widgets["FILTERING"]["BUFFER_TYPE"]["WIDGET"].currentText():
            self.widgets["FILTERING"]["BUFFER_TYPE"]["WIDGET"].setCurrentIndex(0)


    def filtering_populate_layers_chekableCombobox(self, layer=None):
        """v3.1 Sprint 12: Simplified - populate layers-to-filter combobox via controller."""
        if not self.widgets_initialized:
            return
        if self._controller_integration:
            self._controller_integration.delegate_populate_layers_checkable_combobox(layer)

    def exporting_populate_combobox(self):
        """v4.0 Sprint 7: One-liner wrapper."""
        if self._controller_integration: self._controller_integration.delegate_populate_export_combobox()

    def _apply_auto_configuration(self):
        """v4.0 Sprint 7: One-liner wrapper."""
        return ui_utils.auto_configure_from_environment(self.CONFIG_DATA) if UI_CONFIG_AVAILABLE else {}

    def _apply_stylesheet(self):
        """v3.1 Sprint 12: Simplified - apply stylesheet using StyleLoader."""
        StyleLoader.set_theme_from_config(self.dockWidgetContents, self.CONFIG_DATA)

    def _configure_pushbuttons(self, pushButton_config, icons_sizes, font):
        """v3.1 Sprint 15: Configure push buttons with icons, sizes, and cursors."""
        icons_config = pushButton_config.get("ICONS", {})
        exploring_tooltips = {"IDENTIFY": self.tr("Identify selected feature"), "ZOOM": self.tr("Zoom to selected feature"),
            "IS_SELECTING": self.tr("Toggle feature selection on map"), "IS_TRACKING": self.tr("Auto-zoom when feature changes"),
            "IS_LINKING": self.tr("Link exploring widgets together"), "RESET_ALL_LAYER_PROPERTIES": self.tr("Reset all layer exploring properties")}
        
        for widget_group in self.widgets:
            for widget_name, widget_data in self.widgets[widget_group].items():
                if widget_data["TYPE"] != "PushButton":
                    continue
                widget_obj = widget_data["WIDGET"]
                
                # Load icon
                icon_file = icons_config.get(widget_group, {}).get(widget_name)
                if icon_file:
                    icon_path = os.path.join(self.plugin_dir, "icons", icon_file)
                    if os.path.exists(icon_path):
                        widget_obj.setIcon(get_themed_icon(icon_path) if ICON_THEME_AVAILABLE else QtGui.QIcon(icon_path))
                        widget_data["ICON"] = icon_path
                
                widget_obj.setCursor(Qt.PointingHandCursor)
                if widget_group == "EXPLORING" and widget_name in exploring_tooltips:
                    widget_obj.setToolTip(exploring_tooltips[widget_name])
                
                # Apply dimensions
                icon_size = icons_sizes.get(widget_group, icons_sizes["OTHERS"])
                if UI_CONFIG_AVAILABLE:
                    btn_type = "action_button" if widget_group == "ACTION" else ("tool_button" if widget_group in ["EXPLORING", "FILTERING", "EXPORTING"] else "button")
                    h, s = UIConfig.get_button_height(btn_type), UIConfig.get_icon_size(btn_type)
                else:
                    h = 36 if widget_group in ["EXPLORING", "FILTERING", "EXPORTING"] else icon_size * 2
                    s = icon_size
                
                widget_obj.setMinimumSize(h, h)
                widget_obj.setMaximumSize(h, h)
                widget_obj.setIconSize(QtCore.QSize(s, s))
                widget_obj.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
                widget_obj.setFont(font)

    def _configure_other_widgets(self, font):
        """v4.0 Sprint 14: Configure non-button widgets (cursors and fonts)."""
        for widget_group in self.widgets:
            for widget_name in self.widgets[widget_group]:
                widget_type = self.widgets[widget_group][widget_name]["TYPE"]
                widget_obj = self.widgets[widget_group][widget_name]["WIDGET"]
                
                # Skip certain widget types
                if widget_type in ("JsonTreeView", "LayerTreeView", "JsonModel", "ToolBox", "PushButton"):
                    continue
                
                # Configure comboboxes and field widgets
                if any(keyword in widget_type for keyword in ["ComboBox", "QgsFieldExpressionWidget", "QgsProjectionSelectionWidget"]):
                    widget_obj.setCursor(Qt.PointingHandCursor)
                    widget_obj.setFont(font)
                
                # Configure text inputs
                elif "LineEdit" in widget_type or "QgsDoubleSpinBox" in widget_type:
                    widget_obj.setCursor(Qt.IBeamCursor)
                    widget_obj.setFont(font)
                
                # Configure property override buttons
                elif "PropertyOverrideButton" in widget_type:
                    widget_obj.setCursor(Qt.PointingHandCursor)
                    widget_obj.setFont(font)

    def _configure_key_widgets_sizes(self, icons_sizes):
        """v4.0 Sprint 14: Configure sizes for widget_keys and frame_actions."""
        if UI_CONFIG_AVAILABLE:
            # Get widget_keys width directly from config
            widget_keys_width = UIConfig.get_config('widget_keys', 'max_width') or 56
            
            for widget in [self.widget_exploring_keys, self.widget_filtering_keys, self.widget_exporting_keys]:
                widget.setMinimumWidth(widget_keys_width)
                widget.setMaximumWidth(widget_keys_width)
                widget.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)
            
            # Set frame actions size (convert to int to avoid float)
            action_button_height = UIConfig.get_button_height("action_button")
            frame_height = max(int(action_button_height * 1.8), 56)  # Minimum 56px to prevent clipping
            self.frame_actions.setMinimumHeight(frame_height)
            self.frame_actions.setMaximumHeight(frame_height + 15)  # Allow flexibility
        else:
            # Fallback to hardcoded values
            icon_size = icons_sizes["OTHERS"]
            for widget in [self.widget_exploring_keys, self.widget_filtering_keys, self.widget_exporting_keys]:
                widget.setMinimumWidth(80)
                widget.setMaximumWidth(80)
                widget.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)
            
            # Set frame actions size
            icon_size = icons_sizes["ACTION"]
            self.frame_actions.setMinimumHeight(max(icon_size * 2, 56))
            self.frame_actions.setMaximumHeight(max(icon_size * 2, 56) + 15)

    def manage_ui_style(self):
        """v4.0 Sprint 15: Apply stylesheet, icons, and button styling via managers."""
        if self._theme_manager:
            try: self._theme_manager.setup()
            except: self._apply_auto_configuration(); self._apply_stylesheet(); self._setup_theme_watcher()
        else:
            self._apply_auto_configuration(); self._apply_stylesheet(); self._setup_theme_watcher()
        if self._icon_manager:
            try: self._icon_manager.setup()
            except: self._init_icon_theme()
        else:
            self._init_icon_theme()
        if self._button_styler:
            try: self._button_styler.setup()
            except: self._legacy_configure_widgets()
        else:
            self._legacy_configure_widgets()
    
    def _init_icon_theme(self):
        """v3.1 Sprint 15: Initialize icon theme."""
        if ICON_THEME_AVAILABLE:
            IconThemeManager.set_theme(StyleLoader.detect_qgis_theme())
    
    def _legacy_configure_widgets(self):
        """v4.0 Sprint 15: Legacy widget config fallback for ButtonStyler."""
        if not self.widgets:
            logger.warning("_legacy_configure_widgets called but widgets not initialized yet")
            return
        pb_cfg = self.CONFIG_DATA['APP']['DOCKWIDGET']['PushButton']
        icons_sizes = {"ACTION": pb_cfg.get("ICONS_SIZES", {}).get("ACTION", {}).get("value", 20),
                       "OTHERS": pb_cfg.get("ICONS_SIZES", {}).get("OTHERS", {}).get("value", 20)}
        font = QFont("Segoe UI Semibold", 8)
        font.setBold(True)
        self._configure_pushbuttons(pb_cfg, icons_sizes, font)
        self._configure_other_widgets(font)
        self._configure_key_widgets_sizes(icons_sizes)
    
    def _setup_theme_watcher(self):
        """v4.0 Sprint 14: Setup QGIS theme watcher for dark/light mode switching."""
        try:
            self._theme_watcher = QGISThemeWatcher.get_instance()
            current_theme = StyleLoader.detect_qgis_theme()
            if ICON_THEME_AVAILABLE:
                IconThemeManager.set_theme(current_theme)
            self._theme_watcher.add_callback(self._on_qgis_theme_changed)
            if not self._theme_watcher.is_watching:
                self._theme_watcher.start_watching()
            if current_theme == 'dark':
                self._refresh_icons_for_theme()
        except Exception as e:
            logger.warning(f"Could not setup theme watcher: {e}")
    
    def _on_qgis_theme_changed(self, new_theme: str):
        """v4.0 Sprint 14: Handle QGIS theme change event."""
        try:
            if ICON_THEME_AVAILABLE:
                IconThemeManager.set_theme(new_theme)
            StyleLoader.set_theme_from_config(self.dockWidgetContents, self.CONFIG_DATA, new_theme)
            self._refresh_icons_for_theme()
            if hasattr(self, 'config_view') and self.config_view:
                self.config_view.refresh_theme_stylesheet(force_dark=(new_theme == 'dark'))
            show_info("FilterMate", f"Thème adapté: {'Mode sombre' if new_theme == 'dark' else 'Mode clair'}")
        except Exception as e:
            logger.error(f"Error applying theme change: {e}")
    
    def _refresh_icons_for_theme(self):
        """v3.1 Sprint 16: Refresh all button icons for the current theme."""
        if not ICON_THEME_AVAILABLE or not self.widgets_initialized: return
        
        try:
            # Refresh toolbox icons
            for idx, icon in enumerate(["filter_multi.png", "save.png", "parameters.png"]):
                path = os.path.join(self.plugin_dir, "icons", icon)
                if os.path.exists(path): self.toolBox_tabTools.setItemIcon(idx, get_themed_icon(path))
            
            # Refresh pushbutton icons
            for wg in self.widgets:
                for wn in self.widgets[wg]:
                    wi = self.widgets[wg][wn]
                    if wi.get("TYPE") != "PushButton": continue
                    icon_path = wi.get("ICON") or wi.get("ICON_ON_FALSE")
                    if icon_path and os.path.exists(icon_path):
                        wi.get("WIDGET").setIcon(get_themed_icon(icon_path))
                        wi.get("WIDGET").setProperty('icon_path', icon_path)
        except Exception: pass


    def set_widgets_enabled_state(self, state):
        """v3.1 Sprint 12: Simplified - enable or disable all plugin widgets."""
        for widget_group in self.widgets:
            for widget_name in self.widgets[widget_group]:
                if self.widgets[widget_group][widget_name]["TYPE"] not in ("JsonTreeView","LayerTreeView","JsonModel","ToolBox"):
                    widget = self.widgets[widget_group][widget_name]["WIDGET"]
                    was_blocked = widget.blockSignals(True)
                    try:
                        if self.widgets[widget_group][widget_name]["TYPE"] in ("PushButton", "GroupBox"):
                            if widget.isCheckable() and not state:
                                widget.setChecked(False)
                                if self.widgets[widget_group][widget_name]["TYPE"] == "GroupBox":
                                    widget.setCollapsed(True)
                        widget.setEnabled(state)
                    finally:
                        widget.blockSignals(was_blocked)


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
        """
        v4.0 Sprint 8: Ultra-simplified - force reconnect EXPLORING signals bypassing cache.
        """
        if 'EXPLORING' not in self.widgets:
            return
        
        # Widget → expected signals mapping
        ws = {
            'SINGLE_SELECTION_FEATURES': ['featureChanged'], 'SINGLE_SELECTION_EXPRESSION': ['fieldChanged'],
            'MULTIPLE_SELECTION_FEATURES': ['updatingCheckedItemList', 'filteringCheckedItemList'],
            'MULTIPLE_SELECTION_EXPRESSION': ['fieldChanged'], 'CUSTOM_SELECTION_EXPRESSION': ['fieldChanged'],
            'IDENTIFY': ['clicked'], 'ZOOM': ['clicked'], 'IS_SELECTING': ['clicked'],
            'IS_TRACKING': ['clicked'], 'IS_LINKING': ['clicked'], 'RESET_ALL_LAYER_PROPERTIES': ['clicked']
        }
        
        for w, signals in ws.items():
            if w not in self.widgets['EXPLORING']: continue
            for s_tuple in self.widgets['EXPLORING'][w].get("SIGNALS", []):
                if not s_tuple[-1] or s_tuple[0] not in signals: continue
                key = f"EXPLORING.{w}.{s_tuple[0]}"
                self._signal_connection_states.pop(key, None)
                try:
                    state = self.changeSignalState(['EXPLORING', w], s_tuple[0], s_tuple[-1], 'connect')
                    self._signal_connection_states[key] = state
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
        """v3.1 Sprint 12: Simplified - update action buttons based on active tab."""
        if not self.widgets_initialized:
            return
        self.tabTools_current_index = self.widgets["DOCK"]["TOOLS"]["WIDGET"].currentIndex()
        
        # Button states: (FILTER, UNDO, REDO, UNFILTER, EXPORT)
        states = {
            0: (True, True, True, True, False),   # Filtering tab
            1: (False, False, False, False, True), # Exporting tab
            2: (False, False, False, False, False) # Configuration tab
        }
        s = states.get(self.tabTools_current_index, (False, False, False, False, False))
        self.widgets["ACTION"]["FILTER"]["WIDGET"].setEnabled(s[0])
        self.widgets["ACTION"]["UNDO_FILTER"]["WIDGET"].setEnabled(s[1])
        self.widgets["ACTION"]["REDO_FILTER"]["WIDGET"].setEnabled(s[2])
        self.widgets["ACTION"]["UNFILTER"]["WIDGET"].setEnabled(s[3])
        self.widgets["ACTION"]["EXPORT"]["WIDGET"].setEnabled(s[4])
        self.widgets["ACTION"]["ABOUT"]["WIDGET"].setEnabled(True)
        self.set_exporting_properties()

    def _connect_groupbox_signals_directly(self):
        """v4.0 Sprint 7: Simplified - connect groupbox signals for exclusive behavior."""
        try:
            gbs = [(self.mGroupBox_exploring_single_selection, 'single_selection'),
                   (self.mGroupBox_exploring_multiple_selection, 'multiple_selection'),
                   (self.mGroupBox_exploring_custom_selection, 'custom_selection')]
            
            for gb, _ in gbs:
                gb.blockSignals(True)
                try: gb.toggled.disconnect(); gb.collapsedStateChanged.disconnect()
                except: pass
                gb.blockSignals(False)
            
            for gb, name in gbs:
                gb.toggled.connect(lambda checked, n=name: self._on_groupbox_clicked(n, checked))
                gb.collapsedStateChanged.connect(lambda collapsed, n=name: self._on_groupbox_collapse_changed(n, collapsed))
        except: pass

    def _force_exploring_groupbox_exclusive(self, active_groupbox):
        """v3.1 Sprint 16: Force exclusive state for exploring groupboxes."""
        if self._updating_groupbox: return
        self._updating_groupbox = True
        
        try:
            gbs = {
                "single": self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"],
                "multiple": self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"],
                "custom": self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"]
            }
            active_key = active_groupbox.split("_")[0]  # single, multiple, custom
            
            for gb in gbs.values(): gb.blockSignals(True)
            for key, gb in gbs.items():
                gb.setChecked(key == active_key)
                gb.setCollapsed(key != active_key)
            for gb in gbs.values(): gb.blockSignals(False)
        finally:
            self._updating_groupbox = False

    def _on_groupbox_clicked(self, groupbox, state):
        """v3.1 Sprint 10: Simplified - handle groupbox checkbox toggle for exclusive behavior."""
        if self._updating_groupbox or not self.widgets_initialized:
            return
        
        if state:
            self.exploring_groupbox_changed(groupbox)
            return
        
        # User unchecked - ensure at least one remains checked
        try:
            gbs = {
                "single_selection": self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"],
                "multiple_selection": self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"],
                "custom_selection": self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"],
            }
        except (KeyError, AttributeError):
            return
        
        # Check if any other is checked
        other_checked = any(gbs[k].isChecked() for k in gbs if k != groupbox)
        
        if not other_checked:
            # Force this one to stay checked
            gbs[groupbox].blockSignals(True)
            gbs[groupbox].setChecked(True)
            gbs[groupbox].setCollapsed(False)
            gbs[groupbox].blockSignals(False)
        else:
            # Activate the checked one
            for name, gb in gbs.items():
                if gb.isChecked():
                    self.exploring_groupbox_changed(name)
                    break

    def _on_groupbox_collapse_changed(self, groupbox, collapsed):
        """v3.1 Sprint 10: Handle groupbox expand - make it the active one."""
        if self._updating_groupbox or not self.widgets_initialized or collapsed:
            return
        self.exploring_groupbox_changed(groupbox)

    def exploring_groupbox_init(self):
        """
        Initialize exploring groupbox to default or saved state.
        
        v4.0 Sprint 6: Simplified - reduced conditional checks.
        """
        if not self.widgets_initialized:
            return
        
        self.properties_group_state_enabler(self.layer_properties_tuples_dict["selection_expression"])
        
        # Restore saved groupbox or use default
        groupbox = "single_selection"
        if self.current_layer and self.current_layer.id() in self.PROJECT_LAYERS:
            groupbox = self.PROJECT_LAYERS[self.current_layer.id()].get("exploring", {}).get(
                "current_exploring_groupbox", "single_selection"
            )
        
        self.exploring_groupbox_changed(groupbox)

    def _update_exploring_buttons_state(self):
        """v4.0 Sprint 8: Optimized - update identify/zoom buttons based on selection."""
        if not self.widgets_initialized or not self.current_layer:
            self.pushButton_exploring_identify.setEnabled(False)
            self.pushButton_exploring_zoom.setEnabled(False)
            return
        
        has_features = False
        try:
            w = self.widgets.get("EXPLORING", {})
            if self.current_exploring_groupbox == "single_selection":
                if picker := w.get("SINGLE_SELECTION_FEATURES", {}).get("WIDGET"):
                    f = picker.feature()
                    has_features = f is not None and (not hasattr(f, 'isValid') or f.isValid())
            elif self.current_exploring_groupbox == "multiple_selection":
                if combo := w.get("MULTIPLE_SELECTION_FEATURES", {}).get("WIDGET"):
                    has_features = bool(combo.checkedItems())
            elif self.current_exploring_groupbox == "custom_selection":
                if expr := w.get("CUSTOM_SELECTION_EXPRESSION", {}).get("WIDGET"):
                    has_features = bool(expr.expression() and expr.expression().strip())
        except: pass
        
        self.pushButton_exploring_identify.setEnabled(has_features)
        self.pushButton_exploring_zoom.setEnabled(has_features)

    def _configure_single_selection_groupbox(self):
        """v4.0 Sprint 5: Simplified - delegates to ExploringController."""
        self.current_exploring_groupbox = "single_selection"
        
        if not self.current_layer or self.current_layer.id() not in self.PROJECT_LAYERS:
            self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')
            self._update_exploring_buttons_state()
            return True
        
        self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["current_exploring_groupbox"] = "single_selection"
        layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
        
        # Delegate widget configuration to controller
        if self._controller_integration:
            self._controller_integration.delegate_exploring_configure_groupbox(
                "single_selection", self.current_layer, layer_props)
        
        # Signal management and linking
        self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
        self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')
        self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'filteringCheckedItemList')
        self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'updatingCheckedItemList')
        
        self.exploring_link_widgets()
        
        if not self._syncing_from_qgis:
            feature = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].feature()
            if feature and feature.isValid():
                self.exploring_features_changed(feature)
        
        self._update_exploring_buttons_state()
        return True

    def _configure_multiple_selection_groupbox(self):
        """v4.0 Sprint 5: Simplified - delegates to ExploringController."""
        self.current_exploring_groupbox = "multiple_selection"
        
        if not self.current_layer or self.current_layer.id() not in self.PROJECT_LAYERS:
            self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')
            self._update_exploring_buttons_state()
            return True
        
        self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["current_exploring_groupbox"] = "multiple_selection"
        layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
        
        # Delegate widget configuration to controller
        if self._controller_integration:
            self._controller_integration.delegate_exploring_configure_groupbox(
                "multiple_selection", self.current_layer, layer_props)
        
        # Signal management
        self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
        self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')
        self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect')
        
        self.exploring_link_widgets()
        
        if not self._syncing_from_qgis:
            features = self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].currentSelectedFeatures()
            if features:
                self.exploring_features_changed(features, True)
        
        self._update_exploring_buttons_state()
        return True

    def _configure_custom_selection_groupbox(self):
        """v4.0 Sprint 5: Simplified - delegates to ExploringController."""
        self.current_exploring_groupbox = "custom_selection"
        
        if not self.current_layer or self.current_layer.id() not in self.PROJECT_LAYERS:
            self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')
            self._update_exploring_buttons_state()
            return True
        
        self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["current_exploring_groupbox"] = "custom_selection"
        layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
        
        # Delegate widget configuration to controller
        if self._controller_integration:
            self._controller_integration.delegate_exploring_configure_groupbox(
                "custom_selection", self.current_layer, layer_props)
        
        # Signal management
        self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
        self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')
        self.manageSignal(["EXPLORING","CUSTOM_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
        self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'filteringCheckedItemList')
        self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'updatingCheckedItemList')
        
        self.exploring_link_widgets()
        
        # Only apply custom expression if set, or if no existing filter
        custom_expr = layer_props["exploring"].get("custom_selection_expression", "")
        if custom_expr or not self.current_layer.subsetString():
            self.exploring_custom_selection()
        
        self._update_exploring_buttons_state()
        return True

    def exploring_groupbox_changed(self, groupbox):
        """v3.1 Sprint 11: Simplified - handle groupbox change with exclusive behavior."""
        if not self.widgets_initialized:
            return
        
        # Delegate cache invalidation to controller
        if self._controller_integration:
            self._controller_integration.delegate_exploring_set_groupbox_mode(groupbox)
        elif hasattr(self, '_exploring_cache') and self.current_layer:
            old = self.current_exploring_groupbox
            if old and old != groupbox:
                self._exploring_cache.invalidate(self.current_layer.id(), old)
        
        # Force exclusive and configure
        self._force_exploring_groupbox_exclusive(groupbox)
        
        if groupbox == "single_selection":
            self._configure_single_selection_groupbox()
        elif groupbox == "multiple_selection":
            self._configure_multiple_selection_groupbox()
        elif groupbox == "custom_selection":
            self._configure_custom_selection_groupbox()


    def exploring_identify_clicked(self):
        """
        Flash the currently selected features on the map canvas.
        
        v4.0 Sprint 6: Simplified to pure wrapper - delegates to ExploringController.
        Reduced from 34 lines to ~10 lines.
        """
        if not self.widgets_initialized or self.current_layer is None:
            return

        if self._is_layer_truly_deleted(self.current_layer):
            self.current_layer = None
            return
        
        # Delegate to controller
        if self._controller_integration:
            features, _ = self.get_current_features()
            if features:
                self._controller_integration.delegate_flash_features(
                    [f.id() for f in features], self.current_layer
                )


    def get_current_features(self, use_cache: bool = True):
        """
        Get the currently selected features based on the active exploring groupbox.
        
        v3.1 Sprint 6: Simplified - delegates to ExploringController.
        
        Args:
            use_cache: If True, return cached features if available (default: True).
        
        Returns:
            tuple: (features, expression)
        """
        # Delegate to controller
        if self._controller_integration:
            result = self._controller_integration.delegate_get_current_features(use_cache)
            if result != ([], ''):
                return result
        
        # No fallback - controller handles all logic
        return [], ''
        

    def exploring_zoom_clicked(self, features=[], expression=None):
        """
        Zoom the map canvas to the currently selected features.
        
        v4.0 Sprint 6: Simplified to pure wrapper - delegates to zooming_to_features.
        Reduced from 24 lines to ~8 lines.
        """
        if not self.widgets_initialized or self.current_layer is None:
            return

        if self._is_layer_truly_deleted(self.current_layer):
            self.current_layer = None
            return

        # Get features if not provided, then delegate
        if not features:
            features, expression = self.get_current_features()
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
        """
        WRAPPER: Delegates to ExploringController.
        
        Compute the appropriate zoom extent based on the current exploring mode.
        Migrated to ExploringController in v4.0 Sprint 2.
        """
        if self._controller_integration and self._controller_integration.exploring_controller:
            return self._controller_integration.exploring_controller._compute_zoom_extent_for_mode()
        # Fallback during init: use filtered layer extent
        return self.get_filtered_layer_extent(self.current_layer) if self.current_layer else None

    def zooming_to_features(self, features, expression=None):
        """
        v3.1 Sprint 8: Simplified - delegates to ExploringController.
        Zoom to provided features on the map canvas.
        """
        if not self.widgets_initialized or self.current_layer is None:
            return

        if self._is_layer_truly_deleted(self.current_layer):
            self.current_layer = None
            return

        # Delegate to controller
        if self._controller_integration and self._controller_integration.exploring_controller:
            self._controller_integration.exploring_controller.zooming_to_features(features, expression)
            return

        # Minimal fallback
        if features and len(features) > 0:
            self.iface.mapCanvas().zoomToFeatureIds(self.current_layer, [f.id() for f in features])
            self.iface.mapCanvas().refresh()


    def on_layer_selection_changed(self, selected, deselected, clearAndSelect):
        """
        Handle layer selection change from QGIS.
        
        v3.1 Sprint 7: Simplified - delegates to ExploringController.
        Synchronizes QGIS selection with FilterMate widgets when is_selecting is active.
        If is_tracking is active, zooms to selected features.
        """
        # Delegate to controller
        if self._controller_integration:
            if self._controller_integration.delegate_handle_layer_selection_changed(
                selected, deselected, clearAndSelect
            ):
                return
        
        # Minimal fallback - no-op if controller not available
        logger.debug("on_layer_selection_changed: Controller not available")

    
    def _sync_widgets_from_qgis_selection(self):
        """
        v3.1 Sprint 7: Simplified - delegates to ExploringController.
        Synchronizes single and multiple selection widgets with QGIS selection.
        """
        if self._controller_integration and self._controller_integration.exploring_controller:
            self._controller_integration.exploring_controller._sync_widgets_from_qgis_selection()
            return
        logger.debug("_sync_widgets_from_qgis_selection: Controller not available")

    
    def _sync_single_selection_from_qgis(self, selected_features, selected_count):
        """
        v3.1 Sprint 7: Simplified - delegates to ExploringController.
        """
        if self._controller_integration and self._controller_integration.exploring_controller:
            self._controller_integration.exploring_controller._sync_single_selection_from_qgis(
                selected_features, selected_count
            )
            return
        logger.debug("_sync_single_selection_from_qgis: Controller not available")

    
    def _sync_multiple_selection_from_qgis(self, selected_features, selected_count):
        """
        Synchronise AUTOMATIQUEMENT le widget multiple selection avec la sélection QGIS.
        Appelé automatiquement quand la groupbox multiple_selection est active.
        
        Comportement de synchronisation COMPLÈTE (v2.5.6+):
        - COCHE les features sélectionnées dans QGIS
        - DÉCOCHE les features NON sélectionnées dans QGIS
        - Synchronisation bidirectionnelle complète pour refléter exactement l'état QGIS
        
        v3.0.5: Handles async loading - if feature list not ready yet, stores pending
        selection to be applied when loadFeaturesList task completes.
        
        v4.0 Sprint 4: Delegation to UILayoutController with fallback.
        
        Note:
            Contrairement aux versions précédentes qui étaient additives,
            cette synchronisation reflète maintenant EXACTEMENT la sélection QGIS.
        """
        # v4.0 Sprint 4: Delegated to UILayoutController
        if (hasattr(self, '_controller_integration') and 
            self._controller_integration and
            self._controller_integration.delegate_sync_multiple_selection_from_qgis()):
            logger.debug("_sync_multiple_selection_from_qgis: Delegated to UILayoutController")
            return
        
        # No fallback - controller handles all logic
        logger.warning("_sync_multiple_selection_from_qgis: Controller delegation failed")


    def exploring_source_params_changed(self, expression=None, groupbox_override=None, change_source=None):
        """
        WRAPPER: Delegates to ExploringController.
        
        Handle changes to source parameters for exploring features.
        Migrated to ExploringController in v4.0 Sprint 2.
        """
        if self._controller_integration and self._controller_integration.exploring_controller:
            self._controller_integration.exploring_controller.exploring_source_params_changed(
                expression, groupbox_override, change_source
            )


    def exploring_custom_selection(self):
        """v3.1 Sprint 17: Get features matching custom expression."""
        if not self.widgets_initialized or not self.current_layer: return [], ''
        if self.current_layer.id() not in self.PROJECT_LAYERS: return [], ''

        expression = self.PROJECT_LAYERS[self.current_layer.id()]["exploring"].get("custom_selection_expression", "")
        if not expression: return [], expression
        
        # Check if field-only expression (no operators) - used for field-based geometric filtering
        qgs_expr = QgsExpression(expression)
        if qgs_expr.isField() and not any(op in expression.upper() for op in ['=', '>', '<', '!', 'IN', 'LIKE', 'AND', 'OR']):
            return [], expression
        
        # Check cache
        layer_id = self.current_layer.id()
        cached = self._get_cached_expression_result(layer_id, expression)
        if cached is not None: return cached, expression
        
        # Get matching features
        features = self.exploring_features_changed([], False, expression)
        if features: self._set_cached_expression_result(layer_id, expression, features)
        return features, expression
    

    def exploring_deselect_features(self):
        """
        Deselect all features on the current layer.
        
        v4.0 Sprint 5: Simplified - delegates to ExploringController.
        """
        if not self.widgets_initialized or self.current_layer is None:
            return

        # CRITICAL - Use centralized deletion check
        if self._is_layer_truly_deleted(self.current_layer):
            logger.debug("exploring_deselect_features: current_layer C++ object truly deleted")
            self.current_layer = None
            return

        # Delegate to ExploringController
        if self._controller_integration is not None:
            if self._controller_integration.delegate_exploring_clear_selection():
                return
        
        # Minimal fallback
        self.current_layer.removeSelection()
        

    def exploring_select_features(self):
        """v3.1 Sprint 17: Activate QGIS selection tool and select features from active groupbox."""
        if not self.widgets_initialized or not self.current_layer: return
        if self._is_layer_truly_deleted(self.current_layer):
            self.current_layer = None
            return

        if self._controller_integration:
            if self._controller_integration.delegate_exploring_activate_selection_tool(self.current_layer):
                features, _ = self.get_current_features()
                if features and self._controller_integration.delegate_exploring_select_layer_features([f.id() for f in features], self.current_layer): return
        
        try: self.iface.actionSelectRectangle().trigger()
        except: pass
        try: self.iface.setActiveLayer(self.current_layer)
        except: pass
        features, _ = self.get_current_features()
        if features:
            self.current_layer.removeSelection()
            self.current_layer.select([f.id() for f in features])

    def exploring_features_changed(self, input=[], identify_by_primary_key_name=False, custom_expression=None, preserve_filter_if_empty=False):
        """
        WRAPPER: Delegates to ExploringController.
        
        Handle feature selection changes in exploration widgets.
        Migrated to ExploringController in v4.0 Sprint 2.
        """
        if self._controller_integration and self._controller_integration.exploring_controller:
            return self._controller_integration.exploring_controller.exploring_features_changed(
                input, identify_by_primary_key_name, custom_expression, preserve_filter_if_empty
            )
        return []
    
    def _handle_exploring_features_result(
        self, 
        features, 
        expression, 
        layer_props,
        identify_by_primary_key_name=False
    ):
        """
        v3.1 Sprint 8: Simplified - delegates to ExploringController.
        Handle the result of get_exploring_features (sync or async).
        """
        if self._controller_integration and self._controller_integration.exploring_controller:
            return self._controller_integration.exploring_controller.handle_exploring_features_result(
                features, expression, layer_props, identify_by_primary_key_name
            )
        return []


    def get_exploring_features(self, input, identify_by_primary_key_name=False, custom_expression=None):
        """
        WRAPPER: Delegates to ExploringController.
        
        Get features based on input (QgsFeature, list, or expression).
        Migrated to ExploringController in v4.0 Sprint 2.
        """
        if self._controller_integration and self._controller_integration.exploring_controller:
            return self._controller_integration.exploring_controller.get_exploring_features(
                input, identify_by_primary_key_name, custom_expression
            )
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
        """Cancel any pending async expression evaluation."""
        if self._pending_async_evaluation:
            self._pending_async_evaluation.cancel()
            self._pending_async_evaluation = None
            self._set_expression_loading_state(False)
        
        # Also cancel via manager for current layer
        if self._expression_manager and self.current_layer:
            self._expression_manager.cancel(self.current_layer.id())
    
    def should_use_async_expression(self, custom_expression: str = None) -> bool:
        """
        Check if async expression evaluation should be used.
        
        Args:
            custom_expression: The custom expression being evaluated
            
        Returns:
            True if async evaluation should be used
        """
        if not ASYNC_EXPRESSION_AVAILABLE or self._expression_manager is None:
            return False
        
        if self.current_layer is None:
            return False
        
        if custom_expression is None:
            return False
        
        feature_count = self.current_layer.featureCount()
        return feature_count > self._async_expression_threshold
        
    
    def exploring_link_widgets(self, expression=None, change_source=None):
        """
        WRAPPER: Delegates to ExploringController.
        
        Link single and multiple selection widgets based on IS_LINKING state.
        Migrated to ExploringController in v4.0 Sprint 2.
        """
        if self._controller_integration and self._controller_integration.exploring_controller:
            self._controller_integration.exploring_controller.exploring_link_widgets(
                expression, change_source
            )


    def get_layers_to_filter(self):
        """v3.1 Sprint 9: Simplified - reduced verbose logging."""
        if not self.widgets_initialized or self.current_layer is None:
            return []

        checked_list_data = []
        widget = self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"]
        
        for i in range(widget.count()):
            if widget.itemCheckState(i) == Qt.Checked:
                data = widget.itemData(i, Qt.UserRole)
                if isinstance(data, dict) and "layer_id" in data:
                    checked_list_data.append(data["layer_id"])
                elif isinstance(data, str):
                    checked_list_data.append(data)
        
        # Sync to controller
        if self._controller_integration is not None:
            self._controller_integration.delegate_filtering_set_target_layer_ids(checked_list_data)
        
        return checked_list_data


    def get_layers_to_export(self):
        # v3.1 STORY-2.5: Sync with export controller
        if self.widgets_initialized is True and self.current_layer is not None:

            checked_list_data = []
            for i in range(self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].count()):
                if self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].itemCheckState(i) == Qt.Checked:
                    data = self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].itemData(i, Qt.UserRole)
                    if isinstance(data, str):
                        checked_list_data.append(data)
            
            # v3.1 STORY-2.5: Sync to controller
            if self._controller_integration is not None:
                self._controller_integration.delegate_export_set_layers_to_export(checked_list_data)
            
            return checked_list_data


    def get_current_crs_authid(self):
        
        if self.widgets_initialized is True and self.has_loaded_layers is True:

            return self.widgets["EXPORTING"]["PROJECTION_TO_EXPORT"]["WIDGET"].crs().authid()
    
    def _validate_and_prepare_layer(self, layer):
        """
        v3.1 Sprint 10: Simplified validation and preparation for layer change.
        Returns: (should_continue, layer, layer_props)
        """
        # Quick guards
        if self._plugin_busy or not self.PROJECT_LAYERS or not self.widgets_initialized:
            return (False, None, None)
        
        # Skip raster layers and None
        if layer is None or not isinstance(layer, QgsVectorLayer):
            return (False, None, None)
        
        # Verify C++ object validity
        try:
            _ = layer.id()
        except RuntimeError:
            return (False, None, None)
        
        # Verify layer source is available
        try:
            if not is_layer_source_available(layer):
                show_warning("FilterMate", "La couche sélectionnée est invalide ou sa source est introuvable.")
                return (False, None, None)
        except Exception:
            return (False, None, None)
        
        # Disconnect selectionChanged from previous layer
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
        """
        Reset exploring expressions to primary_key_name of new layer when switching.
        
        v3.1 Sprint 9: Simplified - delegates to ExploringController.
        Resets expressions to primary_key when switching layers.
        """
        if self._controller_integration and self._controller_integration.exploring_controller:
            try:
                if self._controller_integration.delegate_reset_layer_expressions(layer_props):
                    return
            except Exception as e:
                logger.debug(f"_reset_layer_expressions delegation failed: {e}")
    
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
        """
        v3.1 Sprint 9: Simplified - delegates to FilteringController.
        Detects existing filters and enables additive mode if needed.
        """
        if self._controller_integration and self._controller_integration.filtering_controller:
            try:
                succeeded, result = self._controller_integration.delegate_detect_multi_step_filter(
                    layer, layer_props
                )
                if succeeded:
                    if result:
                        self._sync_additive_mode_widgets(layer_props)
                    return result
            except Exception as e:
                logger.debug(f"_detect_multi_step_filter delegation failed: {e}")
        return False
    
    def _sync_additive_mode_widgets(self, layer_props):
        """
        Synchronize UI widgets after additive mode is enabled by controller.
        
        v4.0 Sprint 2: Helper for controller delegation.
        
        Args:
            layer_props: Layer properties dict with updated filtering state
        """
        try:
            # Set combobox widgets to index 0 (AND) for additive mode
            self.widgets["FILTERING"]["SOURCE_LAYER_COMBINE_OPERATOR"]["WIDGET"].blockSignals(True)
            self.widgets["FILTERING"]["SOURCE_LAYER_COMBINE_OPERATOR"]["WIDGET"].setCurrentIndex(0)
            self.widgets["FILTERING"]["SOURCE_LAYER_COMBINE_OPERATOR"]["WIDGET"].blockSignals(False)
            
            self.widgets["FILTERING"]["OTHER_LAYERS_COMBINE_OPERATOR"]["WIDGET"].blockSignals(True)
            self.widgets["FILTERING"]["OTHER_LAYERS_COMBINE_OPERATOR"]["WIDGET"].setCurrentIndex(0)
            self.widgets["FILTERING"]["OTHER_LAYERS_COMBINE_OPERATOR"]["WIDGET"].blockSignals(False)
        except Exception as widget_error:
            logger.debug(f"Error syncing additive mode widgets: {widget_error}")
    
    def _synchronize_layer_widgets(self, layer, layer_props):
        """
        Synchronize all widgets with the new current layer.
        
        Updates comboboxes, field expression widgets, and backend indicator.
        
        v4.0 Sprint 3: Delegates to LayerSyncController when available.
        v2.9.42: Added protection to prevent combobox changes during post-filter window.
        """
        # v4.0 Sprint 3: Delegation to LayerSyncController (Sprint 5: fallback removed)
        if self._controller_integration and self._controller_integration.layer_sync_controller:
            try:
                if self._controller_integration.delegate_synchronize_layer_widgets(layer, layer_props):
                    logger.debug("_synchronize_layer_widgets: delegated to LayerSyncController")
                    return
            except Exception as e:
                logger.debug(f"_synchronize_layer_widgets delegation failed: {e}")
        
        # No fallback - controller handles all logic
        logger.warning("_synchronize_layer_widgets: Controller delegation failed")
    
    def _reload_exploration_widgets(self, layer, layer_props):
        """v4.0 Sprint 9: Wrapper - delegates to ExploringController."""
        if self._controller_integration and self._controller_integration.exploring_controller:
            self._controller_integration.exploring_controller._reload_exploration_widgets(layer, layer_props)

    def _restore_groupbox_ui_state(self, groupbox_name):
        """v4.0 Sprint 9: Restore exploring groupbox visual state."""
        if not self.widgets_initialized:
            return
        
        self.current_exploring_groupbox = groupbox_name
        
        if self.current_layer is not None and self.current_layer.id() in self.PROJECT_LAYERS:
            self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["current_exploring_groupbox"] = groupbox_name
        
        states = {
            "single_selection": (True, False, False, True, False, True),
            "multiple_selection": (False, True, True, False, False, True),
            "custom_selection": (False, True, False, True, True, False),
        }
        s = states.get(groupbox_name, states["single_selection"])
        
        groupboxes = [
            self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"],
            self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"],
            self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"],
        ]
        
        for gb in groupboxes:
            gb.blockSignals(True)
        
        try:
            groupboxes[0].setChecked(s[0]); groupboxes[0].setCollapsed(s[1])
            groupboxes[1].setChecked(s[2]); groupboxes[1].setCollapsed(s[3])
            groupboxes[2].setChecked(s[4]); groupboxes[2].setCollapsed(s[5])
            
            for gb in groupboxes:
                gb.update()
        finally:
            for gb in groupboxes:
                gb.blockSignals(False)
    
    def _reconnect_layer_signals(self, widgets_to_reconnect, layer_props):
        """v4.0 Sprint 9: Reconnect layer signals - delegates to LayerSyncController."""
        if self._controller_integration and self._controller_integration.layer_sync_controller:
            try:
                if self._controller_integration.delegate_reconnect_layer_signals(widgets_to_reconnect, layer_props):
                    return
            except:
                pass

    
    def _ensure_valid_current_layer(self, requested_layer):
        """v4.0 Sprint 9: Ensure valid layer - delegates to LayerSyncController."""
        if self._controller_integration and self._controller_integration.layer_sync_controller:
            try:
                result = self._controller_integration.delegate_ensure_valid_current_layer(requested_layer)
                if result is not None:
                    return result
            except:
                logger.debug(f"_ensure_valid_current_layer delegation failed: {e}")
        
        # Minimal fallback: use requested layer if valid
        if requested_layer is not None:
            try:
                _ = requested_layer.id()
                return requested_layer
            except (RuntimeError, AttributeError):
                pass
        return None


    def _is_layer_truly_deleted(self, layer):
        """
        v3.1 Sprint 9: Simplified - delegates to LayerSyncController.
        Checks if layer is truly deleted, respecting filtering protection window.
        """
        if self._controller_integration and self._controller_integration.layer_sync_controller:
            try:
                return self._controller_integration.delegate_is_layer_truly_deleted(layer)
            except Exception as e:
                logger.debug(f"_is_layer_truly_deleted delegation failed: {e}")
        
        # Minimal fallback
        if layer is None:
            return True
        try:
            import sip
            return sip.isdeleted(layer)
        except Exception:
            return True


    def current_layer_changed(self, layer):
        """v3.1 Sprint 11: Simplified - handle current layer change event."""
        if self._updating_current_layer:
            return
        
        # Delegate protection to controller
        if self._controller_integration:
            if not self._controller_integration.delegate_current_layer_changed(layer):
                return
        
        layer = self._ensure_valid_current_layer(layer)
        if layer is None:
            return
        
        if self._plugin_busy:
            self._defer_layer_change(layer)
            return
        
        try:
            _ = layer.id()
        except (RuntimeError, AttributeError):
            return
        
        self._updating_current_layer = True
        self._reset_selection_tracking_for_layer(layer)
            
        try:
            should_continue, validated_layer, layer_props = self._validate_and_prepare_layer(layer)
            if not should_continue:
                return
            
            self._reset_layer_expressions(layer_props)
            widgets_to_reconnect = self._disconnect_layer_signals()
            self._synchronize_layer_widgets(validated_layer, layer_props)
            self._reload_exploration_widgets(validated_layer, layer_props)
            self._update_exploring_buttons_state()
            self._reconnect_layer_signals(widgets_to_reconnect, layer_props)
        except Exception as e:
            logger.error(f"Error in current_layer_changed: {e}")
        finally:
            self._updating_current_layer = False
    
    def _defer_layer_change(self, layer):
        """Defer layer change when plugin is busy."""
        from qgis.PyQt.QtCore import QTimer
        from qgis.core import QgsProject
        
        logger.debug(f"Plugin is busy, deferring layer change for: {layer.name() if layer else 'None'}")
        weak_self = weakref.ref(self)
        try:
            captured_layer_id = layer.id() if layer else None
        except (RuntimeError, OSError, SystemError):
            captured_layer_id = None
        
        def safe_layer_change():
            strong_self = weak_self()
            if strong_self is not None and captured_layer_id:
                fresh_layer = QgsProject.instance().mapLayer(captured_layer_id)
                if fresh_layer is not None:
                    strong_self.current_layer_changed(fresh_layer)
        
        QTimer.singleShot(150, safe_layer_change)
    
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
        """
        Handle property changes for project-level (export) properties.
        
        v4.0 Sprint 3: Delegates to PropertyController when available.
        """
        # v4.0 Sprint 3: Delegation to PropertyController (Sprint 5: fallback removed)
        if self._controller_integration and self._controller_integration.property_controller:
            try:
                if self._controller_integration.delegate_change_project_property(
                    input_property, input_data, custom_functions
                ):
                    logger.debug("project_property_changed: delegated to PropertyController")
                    return
            except Exception as e:
                logger.debug(f"project_property_changed delegation failed: {e}")
        
        # No fallback - controller handles all logic
        logger.warning("project_property_changed: Controller delegation failed")


    # v4.0 Sprint 9: Property helper methods removed - logic migrated to PropertyController
    # Removed: _parse_property_data, _find_property_path, _update_is_property,
    # _update_selection_expression_property, _update_other_property (~130 lines)

    def layer_property_changed(self, input_property, input_data=None, custom_functions={}):
        """
        WRAPPER: Delegates to PropertyController.
        
        Handle property changes for the current layer.
        v4.0 Sprint 9: Migrated to PropertyController.
        """
        if self._controller_integration and self._controller_integration.property_controller:
            self._controller_integration.delegate_change_layer_property(
                input_property, input_data, custom_functions
            )

    def layer_property_changed_with_buffer_style(self, input_property, input_data=None):
        """
        WRAPPER: Delegates to PropertyController.
        
        Handle buffer value changes with visual style feedback.
        v4.0 Sprint 9: Migrated to PropertyController.
        """
        if self._controller_integration and self._controller_integration.property_controller:
            self._controller_integration.property_controller.change_property_with_buffer_style(
                input_property, input_data
            )
    
    def _update_buffer_spinbox_style(self, buffer_value):
        """
        Update the visual style of the buffer spinbox based on value.
        
        Negative values get a distinctive style to indicate erosion mode.
        
        Args:
            buffer_value: The current buffer value
        """
        spinbox = self.mQgsDoubleSpinBox_filtering_buffer_value
        
        if buffer_value is not None and buffer_value < 0:
            # Negative buffer (erosion) - use distinctive orange/yellow style
            spinbox.setStyleSheet("""
                QgsDoubleSpinBox {
                    background-color: #FFF3CD;
                    border: 2px solid #FFC107;
                    color: #856404;
                }
                QgsDoubleSpinBox:focus {
                    border: 2px solid #FF9800;
                }
            """)
            spinbox.setToolTip(self.tr("Negative buffer (erosion): shrinks polygons inward"))
        else:
            # Zero or positive buffer - reset to default style
            spinbox.setStyleSheet("")
            spinbox.setToolTip(self.tr("Buffer value in meters (positive=expand, negative=shrink polygons)"))
    
    def _update_buffer_validation(self):
        """
        Update buffer spinbox validation based on source layer geometry type.
        
        v4.0 Sprint 1: Delegated to PropertyController.
        
        Negative buffers (erosion) only work on polygon/multipolygon geometries.
        For point and line geometries, the minimum value is set to 0 to prevent
        negative buffer input.
        """
        # v4.0: Delegate to PropertyController (Sprint 5: fallback removed)
        if self._controller_integration and self._controller_integration.property_controller:
            try:
                self._controller_integration.delegate_update_buffer_validation()
                return
            except Exception as e:
                logger.debug(f"_update_buffer_validation delegation failed: {e}")
        
        # No fallback - controller handles all logic
        logger.warning("_update_buffer_validation: Controller delegation failed")

    def set_exporting_properties(self):
        """v3.1 Sprint 16: Set exporting widgets from project properties."""
        if not self.widgets_initialized or not self.has_loaded_layers:
            return

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
        """v3.1 Sprint 12: Simplified - enable widgets in a property group."""
        if not self.widgets_initialized or not self.has_loaded_layers:
            return
        for t in tuple_group:
            if t[0].upper() not in self.widgets or t[1].upper() not in self.widgets[t[0].upper()]:
                continue
            widget_entry = self.widgets[t[0].upper()][t[1].upper()]
            if t[1] in ['has_output_folder_to_export', 'has_zip_to_export']:
                has_layers = any(self.checkableComboBoxLayer_exporting_layers.itemCheckState(i) == Qt.Checked 
                               for i in range(self.checkableComboBoxLayer_exporting_layers.count())) if hasattr(self, 'checkableComboBoxLayer_exporting_layers') else False
                widget_entry["WIDGET"].setEnabled(has_layers)
            else:
                widget_entry["WIDGET"].setEnabled(True)
            if widget_entry["TYPE"] == 'QgsFieldExpressionWidget' and self.current_layer:
                widget_entry["WIDGET"].setLayer(self.current_layer)


    def properties_group_state_reset_to_default(self, tuple_group, group_name, state):
        """v3.1 Sprint 12: Simplified - reset property group to defaults via controller."""
        if self._controller_integration and self._controller_integration.property_controller:
            try:
                if self._controller_integration.delegate_reset_property_group(tuple_group, group_name, state):
                    return
            except Exception:
                pass

    def filtering_init_buffer_property(self):
        """v3.1 Sprint 12: Simplified - init buffer property override widget."""
        if not self.widgets_initialized or not self.has_loaded_layers:
            return
        if not self.current_layer or self.current_layer.id() not in self.PROJECT_LAYERS:
            return

        layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
        layer_id = self.current_layer.id()
        
        name = f"{layer_id}_buffer_property_definition"
        description = f"Replace unique buffer value with values based on expression for {layer_id}"
        prop_def = QgsPropertyDefinition(name, QgsPropertyDefinition.DataTypeNumeric, description, 'Expression must returns numeric values (unit is in meters)')
        
        buffer_expr = layer_props["filtering"]["buffer_value_expression"]
        if not isinstance(buffer_expr, str):
            buffer_expr = str(buffer_expr) if buffer_expr else ''
            layer_props["filtering"]["buffer_value_expression"] = buffer_expr
        
        prop = QgsProperty.fromExpression(buffer_expr) if buffer_expr and buffer_expr.strip() else QgsProperty()
        self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].init(0, prop, prop_def, self.current_layer)
        
        has_buffer_checked = layer_props["filtering"].get("has_buffer_value", False)
        is_active = layer_props["filtering"]["buffer_value_property"]
        has_valid_expr = bool(buffer_expr and buffer_expr.strip())
        
        self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"].setEnabled(has_buffer_checked and not (is_active and has_valid_expr))
        self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].setEnabled(has_buffer_checked)


    def filtering_buffer_property_changed(self):
        """v4.0 Sprint 8: Optimized - handle buffer property override button changes."""
        if not self.widgets_initialized or not self.has_loaded_layers: return

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
        """v3.1 Sprint 11: Simplified - handle layers_to_filter button changes."""
        if not self.widgets_initialized or not self.has_loaded_layers:
            return
        is_checked = self.widgets["FILTERING"]["HAS_LAYERS_TO_FILTER"]["WIDGET"].isChecked()
        if self._controller_integration:
            self._controller_integration.delegate_filtering_layers_to_filter_state_changed(is_checked)
        self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].setEnabled(is_checked)
        self.widgets["FILTERING"]["USE_CENTROIDS_DISTANT_LAYERS"]["WIDGET"].setEnabled(is_checked)


    def filtering_combine_operator_state_changed(self):
        """v3.1 Sprint 11: Simplified - handle combine operator button changes."""
        if not self.widgets_initialized or not self.has_loaded_layers:
            return
        is_checked = self.widgets["FILTERING"]["HAS_COMBINE_OPERATOR"]["WIDGET"].isChecked()
        if self._controller_integration:
            self._controller_integration.delegate_filtering_combine_operator_state_changed(is_checked)
        self.widgets["FILTERING"]["SOURCE_LAYER_COMBINE_OPERATOR"]["WIDGET"].setEnabled(is_checked)
        self.widgets["FILTERING"]["OTHER_LAYERS_COMBINE_OPERATOR"]["WIDGET"].setEnabled(is_checked)


    def filtering_geometric_predicates_state_changed(self):
        """v3.1 Sprint 11: Simplified - handle geometric predicates button changes."""
        if not self.widgets_initialized or not self.has_loaded_layers:
            return
        is_checked = self.widgets["FILTERING"]["HAS_GEOMETRIC_PREDICATES"]["WIDGET"].isChecked()
        if self._controller_integration:
            self._controller_integration.delegate_filtering_geometric_predicates_state_changed(is_checked)
        self.widgets["FILTERING"]["GEOMETRIC_PREDICATES"]["WIDGET"].setEnabled(is_checked)


    def filtering_buffer_type_state_changed(self):
        """v4.0 Sprint 8: Optimized - handle buffer type button changes."""
        if not self.widgets_initialized or not self.has_loaded_layers: return
        is_checked = self.widgets["FILTERING"]["HAS_BUFFER_TYPE"]["WIDGET"].isChecked()
        if self._controller_integration:
            self._controller_integration.delegate_filtering_buffer_type_state_changed(is_checked)
        self.widgets["FILTERING"]["BUFFER_TYPE"]["WIDGET"].setEnabled(is_checked)
        self.widgets["FILTERING"]["BUFFER_SEGMENTS"]["WIDGET"].setEnabled(is_checked)

    def _update_centroids_source_checkbox_state(self):
        """v4.0 Sprint 8: Optimized - update centroids checkbox enabled state."""
        if not self.widgets_initialized: return
        if (combo := self.widgets.get("FILTERING", {}).get("CURRENT_LAYER", {}).get("WIDGET")) and \
           (checkbox := self.widgets.get("FILTERING", {}).get("USE_CENTROIDS_SOURCE_LAYER", {}).get("WIDGET")):
            checkbox.setEnabled(combo.currentLayer() is not None and combo.isEnabled())

              
    def dialog_export_output_path(self):
        """v3.1 Sprint 12: Simplified - dialog for export output path."""
        if not self.widgets_initialized or not self.has_loaded_layers:
            return
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
        """v3.1 Sprint 12: Simplified - reset export output path."""
        if not self.widgets_initialized or not self.has_loaded_layers:
            return
        if not self.widgets["EXPORTING"]["OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].text():
            self.widgets["EXPORTING"]["OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].clear()
            self.widgets["EXPORTING"]["HAS_OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].setChecked(False)
            self.project_property_changed('has_output_folder_to_export', False)
            self.project_property_changed('output_folder_to_export', '')

    def dialog_export_output_pathzip(self):
        """v3.1 Sprint 12: Simplified - dialog for zip export path."""
        if not self.widgets_initialized or not self.has_loaded_layers:
            return
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
        """v3.1 Sprint 12: Simplified - reset zip export path."""
        if not self.widgets_initialized or not self.has_loaded_layers:
            return
        if not self.widgets["EXPORTING"]["ZIP_TO_EXPORT"]["WIDGET"].text():
            self.widgets["EXPORTING"]["ZIP_TO_EXPORT"]["WIDGET"].clear()
            self.widgets["EXPORTING"]["HAS_ZIP_TO_EXPORT"]["WIDGET"].setChecked(False)
            self.project_property_changed('has_zip_to_export', False)
            self.project_property_changed('zip_to_export', '')

    def filtering_auto_current_layer_changed(self, state=None):
        """v3.1 Sprint 12: Simplified - handle auto current layer toggle."""
        if not self.widgets_initialized or not self.has_loaded_layers:
            return
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
        if "APP" in self.CONFIG_DATA and "OPTIONS" in self.CONFIG_DATA["APP"]:
            if "GITHUB_PAGE" in self.CONFIG_DATA["APP"]["OPTIONS"]:
                url = self.CONFIG_DATA["APP"]["OPTIONS"]["GITHUB_PAGE"]
                if url and url.startswith("http"):
                    webbrowser.open(url)

    def reload_plugin(self):
        """v3.1 Sprint 17: Reload the FilterMate plugin to apply layout changes."""
        try:
            from qgis.utils import plugins
            from qgis.PyQt.QtCore import QTimer
            
            self.save_configuration_model()
            if 'filter_mate' not in plugins:
                show_warning("FilterMate", "Could not reload plugin automatically. Please close and reopen.")
                return
            
            fm = plugins['filter_mate']
            self.close()
            fm.pluginIsActive, fm.app = False, None
            QTimer.singleShot(100, fm.run)
        except Exception as e:
            show_error("FilterMate", f"Error reloading plugin: {str(e)}")


    def setLayerVariableEvent(self, layer=None, properties=None):
        """v4.0 Sprint 13: Emit signal to set layer variables with validity check."""
        if not self.widgets_initialized:
            return
        properties = properties if isinstance(properties, list) else []
        layer = layer or self.current_layer
        if is_valid_layer(layer):
            self.settingLayerVariable.emit(layer, properties)


    def resetLayerVariableOnErrorEvent(self, layer, properties=None):
        """v4.0 Sprint 13: Emit signal to reset layer variables after error."""
        if not self.widgets_initialized:
            return
        properties = properties if isinstance(properties, list) else []
        layer = layer or self.current_layer
        if not self._is_layer_truly_deleted(layer):
            try:
                self.resettingLayerVariableOnError.emit(layer, properties)
            except TypeError as e:
                logger.warning(f"Signal emission failed: {e}")


    def resetLayerVariableEvent(self, layer=None, properties=None):
        """v3.1 Sprint 15: Reset layer properties to default values."""
        if not self.widgets_initialized:
            return
        layer = layer or self.current_layer
        if not layer or not is_valid_layer(layer) or layer.id() not in self.PROJECT_LAYERS:
            return
        
        try:
            layer_props = self.PROJECT_LAYERS[layer.id()]
            best_field = get_best_display_field(layer) or layer_props.get("infos", {}).get("primary_key_name", "")
            
            defaults = {
                "exploring": {"is_changing_all_layer_properties": True, "is_tracking": False, "is_selecting": False, "is_linking": False,
                    "current_exploring_groupbox": "single_selection", "single_selection_expression": best_field,
                    "multiple_selection_expression": best_field, "custom_selection_expression": best_field},
                "filtering": {"has_layers_to_filter": False, "layers_to_filter": [], "has_combine_operator": False,
                    "source_layer_combine_operator": "AND", "other_layers_combine_operator": "AND", "has_geometric_predicates": False,
                    "geometric_predicates": [], "has_buffer_value": False, "buffer_value": 0.0, "buffer_value_property": False,
                    "buffer_value_expression": "", "has_buffer_type": False, "buffer_type": "Round"}
            }
            
            properties_to_save = []
            for category, props in defaults.items():
                layer_props[category].update(props)
                properties_to_save.extend((category, k) for k in props)
            
            self.settingLayerVariable.emit(layer, properties_to_save)
            self._synchronize_layer_widgets(layer, layer_props)
            self._update_buffer_spinbox_style(0.0)
            self._reset_exploring_button_states(layer_props)
            self._reset_filtering_button_states(layer_props)
            self.iface.messageBar().pushSuccess("FilterMate", self.tr("Layer properties reset to defaults"))
        except Exception as e:
            self.iface.messageBar().pushCritical("FilterMate", self.tr("Error resetting layer properties: {}").format(str(e)))

    def _reset_exploring_button_states(self, layer_props):
        """Reset exploring button visual states based on layer properties."""
        try:
            # Block signals during state update
            is_selecting_widget = self.widgets["EXPLORING"]["IS_SELECTING"]["WIDGET"]
            is_tracking_widget = self.widgets["EXPLORING"]["IS_TRACKING"]["WIDGET"]
            is_linking_widget = self.widgets["EXPLORING"]["IS_LINKING"]["WIDGET"]
            
            is_selecting_widget.blockSignals(True)
            is_tracking_widget.blockSignals(True)
            is_linking_widget.blockSignals(True)
            
            is_selecting_widget.setChecked(layer_props["exploring"]["is_selecting"])
            is_tracking_widget.setChecked(layer_props["exploring"]["is_tracking"])
            is_linking_widget.setChecked(layer_props["exploring"]["is_linking"])
            
            is_selecting_widget.blockSignals(False)
            is_tracking_widget.blockSignals(False)
            is_linking_widget.blockSignals(False)
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
        if self.widgets_initialized is True:

            self.settingProjectVariables.emit()

    def _update_backend_indicator(self, provider_type, postgresql_connection_available=None, actual_backend=None):
        """v4.0 Sprint 13: Simplified - delegates to BackendController."""
        if self._controller_integration and self._controller_integration.backend_controller and self.current_layer:
            if self._controller_integration.delegate_update_backend_indicator(
                self.current_layer, postgresql_connection_available, actual_backend):
                self._current_provider_type = provider_type
                self._current_postgresql_available = postgresql_connection_available
                return
        self._update_backend_indicator_legacy(provider_type, postgresql_connection_available, actual_backend)
    
    def _update_backend_indicator_legacy(self, provider_type, postgresql_connection_available=None, actual_backend=None):
        """v4.0 Sprint 13: Simplified legacy fallback."""
        if self._controller_integration and self._controller_integration._backend_controller and self.current_layer:
            self._controller_integration._backend_controller.update_for_layer(
                self.current_layer, postgresql_available=postgresql_connection_available, actual_backend=actual_backend)
            return
        if hasattr(self, 'backend_indicator_label') and self.backend_indicator_label:
            self.backend_indicator_label.setText(actual_backend.upper() if actual_backend else provider_type.upper()[:3])
    
    def getProjectLayersEvent(self, event):

        if self.widgets_initialized is True:

            self.gettingProjectLayers.emit()

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
        """v4.0 Sprint 13: Get cache statistics - delegates to controller or uses local cache."""
        if self._controller_integration:
            stats = self._controller_integration.delegate_exploring_get_cache_stats()
            if stats:
                return stats
        return self._exploring_cache.get_stats() if hasattr(self, '_exploring_cache') else {}
    
    def invalidate_exploring_cache(self, layer_id=None, groupbox_type=None):
        """v4.0 Sprint 13: Invalidate exploring cache - delegates to controller or uses local cache."""
        if layer_id is None and groupbox_type is None and self._controller_integration:
            if self._controller_integration.delegate_exploring_clear_cache():
                return
        if hasattr(self, '_exploring_cache'):
            if layer_id is None:
                self._exploring_cache.invalidate_all()
            elif groupbox_type is None:
                self._exploring_cache.invalidate_layer(layer_id)
            else:
                self._exploring_cache.invalidate(layer_id, groupbox_type)

    def launchTaskEvent(self, state, task_name):
        """v3.1 Sprint 17: Emit signal to launch a task."""
        if not self.widgets_initialized: return
        if not self.current_layer or self.current_layer.id() not in self.PROJECT_LAYERS: return
        
        current_layers_to_filter = self.get_layers_to_filter()
        self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["layers_to_filter"] = current_layers_to_filter
        self.setLayerVariableEvent(self.current_layer, [("filtering", "layers_to_filter")])
        self.launchingTask.emit(task_name)
    
    def _setup_truncation_tooltips(self):
        """
        Setup tooltips for widgets that may display truncated text.
        
        Adds tooltips to show full text content when text is potentially truncated
        in combo boxes, expression widgets, and other text-displaying widgets.
        """
        # Widgets to monitor for text truncation
        widgets_to_monitor = [
            # Layer selection combos
            (self.comboBox_filtering_current_layer, 'currentTextChanged', lambda: self._update_combo_tooltip(self.comboBox_filtering_current_layer)),
            (self.checkableComboBoxLayer_filtering_layers_to_filter, 'checkedItemsChanged', lambda: self._update_checkable_combo_tooltip(self.checkableComboBoxLayer_filtering_layers_to_filter)),
            (self.checkableComboBoxLayer_exporting_layers, 'checkedItemsChanged', lambda: [self._update_checkable_combo_tooltip(self.checkableComboBoxLayer_exporting_layers), self._update_export_buttons_state()]),
            
            # Expression widgets
            (self.mFieldExpressionWidget_exploring_single_selection, 'fieldChanged', lambda: self._update_expression_tooltip(self.mFieldExpressionWidget_exploring_single_selection)),
            (self.mFieldExpressionWidget_exploring_multiple_selection, 'fieldChanged', lambda: self._update_expression_tooltip(self.mFieldExpressionWidget_exploring_multiple_selection)),
            (self.mFieldExpressionWidget_exploring_custom_selection, 'fieldChanged', lambda: self._update_expression_tooltip(self.mFieldExpressionWidget_exploring_custom_selection)),
            
            # Feature picker
            (self.mFeaturePickerWidget_exploring_single_selection, 'featureChanged', lambda: self._update_feature_picker_tooltip(self.mFeaturePickerWidget_exploring_single_selection)),
        ]
        
        # Connect signals for dynamic tooltip updates
        for widget, signal_name, slot in widgets_to_monitor:
            if widget and hasattr(widget, signal_name):
                try:
                    signal = getattr(widget, signal_name)
                    signal.connect(slot)
                    # Initial tooltip setup
                    slot()
                except Exception as e:
                    logger.debug(f"FilterMate: Could not connect truncation tooltip for {widget.objectName()}: {e}")
    
    def _update_combo_tooltip(self, combo_widget):
        """Update tooltip for a QComboBox-like widget."""
        if not combo_widget:
            return
        
        try:
            if hasattr(combo_widget, 'currentText'):
                text = combo_widget.currentText()
                # Set tooltip if text is longer than typical display width (30 chars threshold)
                if text and len(text) > 30:
                    combo_widget.setToolTip(text)
                elif text:
                    # Short text - use descriptive tooltip instead
                    combo_widget.setToolTip(QCoreApplication.translate("FilterMate", "Current layer: {0}").format(text))
                else:
                    combo_widget.setToolTip(QCoreApplication.translate("FilterMate", "No layer selected"))
        except Exception as e:
            logger.debug(f"FilterMate: Error updating combo tooltip: {e}")
    
    def _update_checkable_combo_tooltip(self, combo_widget):
        """Update tooltip for a checkable combo box showing selected items."""
        if not combo_widget:
            return
        
        try:
            if hasattr(combo_widget, 'checkedItems'):
                items = combo_widget.checkedItems()
                if items:
                    # Join item names with line breaks for readability
                    text = "\n".join([item.text() for item in items if hasattr(item, 'text')])
                    if text:
                        combo_widget.setToolTip(QCoreApplication.translate("FilterMate", "Selected layers:\n{0}").format(text))
                    else:
                        combo_widget.setToolTip(QCoreApplication.translate("FilterMate", "Multiple layers selected"))
                else:
                    combo_widget.setToolTip(QCoreApplication.translate("FilterMate", "No layers selected"))
        except Exception as e:
            logger.debug(f"FilterMate: Error updating checkable combo tooltip: {e}")
    
    def _update_export_buttons_state(self):
        """Update enabled state of output and zip buttons based on selected layers."""
        try:
            # Check if any layers are selected in the export combobox
            has_layers_selected = False
            if hasattr(self, 'checkableComboBoxLayer_exporting_layers'):
                for i in range(self.checkableComboBoxLayer_exporting_layers.count()):
                    if self.checkableComboBoxLayer_exporting_layers.itemCheckState(i) == Qt.Checked:
                        has_layers_selected = True
                        break
            
            # Enable/disable output and zip buttons
            if hasattr(self, 'pushButton_checkable_exporting_output_folder'):
                self.pushButton_checkable_exporting_output_folder.setEnabled(has_layers_selected)
            if hasattr(self, 'pushButton_checkable_exporting_zip'):
                self.pushButton_checkable_exporting_zip.setEnabled(has_layers_selected)
        except Exception as e:
            logger.debug(f"FilterMate: Error updating export buttons state: {e}")
    
    def _update_expression_tooltip(self, expression_widget):
        """Update tooltip for a QgsFieldExpressionWidget."""
        if not expression_widget:
            return
        
        try:
            if hasattr(expression_widget, 'expression'):
                expr = expression_widget.expression()
                if expr and len(expr) > 40:
                    # For long expressions, format with line breaks at logical points
                    formatted_expr = expr.replace(' AND ', '\nAND ').replace(' OR ', '\nOR ')
                    expression_widget.setToolTip(QCoreApplication.translate("FilterMate", "Expression:\n{0}").format(formatted_expr))
                elif expr:
                    expression_widget.setToolTip(QCoreApplication.translate("FilterMate", "Expression: {0}").format(expr))
                else:
                    expression_widget.setToolTip(QCoreApplication.translate("FilterMate", "No expression defined"))
        except Exception as e:
            logger.debug(f"FilterMate: Error updating expression tooltip: {e}")
    
    def _update_feature_picker_tooltip(self, picker_widget):
        """Update tooltip for a QgsFeaturePickerWidget."""
        if not picker_widget:
            return
        
        try:
            if hasattr(picker_widget, 'displayExpression'):
                display_expr = picker_widget.displayExpression()
                if display_expr and len(display_expr) > 30:
                    picker_widget.setToolTip(QCoreApplication.translate("FilterMate", "Display expression: {0}").format(display_expr))
                elif hasattr(picker_widget, 'feature'):
                    feature = picker_widget.feature()
                    if feature and feature.isValid():
                        # Show feature ID and first attribute
                        attrs = feature.attributes()
                        if attrs:
                            picker_widget.setToolTip(QCoreApplication.translate("FilterMate", "Feature ID: {0}\nFirst attribute: {1}").format(feature.id(), attrs[0]))
        except Exception as e:
            logger.debug(f"FilterMate: Error updating feature picker tooltip: {e}")

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
        """
        Setup keyboard shortcuts for the dockwidget.
        
        F5: Force reload all layers from current project.
             Useful when project change doesn't properly refresh the layer list.
        Ctrl+Z: Undo last filter operation.
        Ctrl+Y: Redo last undone filter operation.
        """
        from qgis.PyQt.QtWidgets import QShortcut
        from qgis.PyQt.QtGui import QKeySequence
        
        # F5 - Force reload layers
        self._reload_shortcut = QShortcut(QKeySequence("F5"), self)
        self._reload_shortcut.activated.connect(self._on_reload_layers_shortcut)
        self._reload_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        
        # Ctrl+Z - Undo filter operation
        self._undo_shortcut = QShortcut(QKeySequence.Undo, self)  # Standard Ctrl+Z / Cmd+Z
        self._undo_shortcut.activated.connect(self._on_undo_shortcut)
        self._undo_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        
        # Ctrl+Y - Redo filter operation (also Ctrl+Shift+Z on some platforms)
        self._redo_shortcut = QShortcut(QKeySequence.Redo, self)  # Standard Ctrl+Y / Cmd+Shift+Z
        self._redo_shortcut.activated.connect(self._on_redo_shortcut)
        self._redo_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        
        logger.debug("Keyboard shortcuts initialized: F5 = Reload layers, Ctrl+Z = Undo, Ctrl+Y = Redo")
    
    
    def _on_reload_layers_shortcut(self):
        """v4.0 Sprint 13: Handle F5 shortcut to reload layers."""
        self._trigger_reload_layers()
    
    def _trigger_reload_layers(self):
        """v4.0 Sprint 13: Trigger layer reload with visual feedback."""
        if hasattr(self, 'backend_indicator_label') and self.backend_indicator_label:
            self.backend_indicator_label.setText("⟳")
            self.backend_indicator_label.setStyleSheet("QLabel#label_backend_indicator { color: #3498db; font-size: 9pt; font-weight: 600; padding: 3px 10px; border-radius: 12px; border: none; background-color: #e8f4fc; }")
        self.launchingTask.emit('reload_layers')

    def _on_undo_shortcut(self):
        """v4.0 Sprint 13: Handle Ctrl+Z to undo last filter."""
        undo_widget = self.widgets.get("ACTION", {}).get("UNDO_FILTER", {}).get("WIDGET")
        if undo_widget and undo_widget.isEnabled():
            self.launchTaskEvent(False, 'undo')

    def _on_redo_shortcut(self):
        """v4.0 Sprint 13: Handle Ctrl+Y to redo last filter."""
        redo_widget = self.widgets.get("ACTION", {}).get("REDO_FILTER", {}).get("WIDGET")
        if redo_widget and redo_widget.isEnabled():
            self.launchTaskEvent(False, 'redo')

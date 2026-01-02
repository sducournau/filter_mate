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
"""


from .config.config import ENV_VARS
import os
import json
import re
import sip
import weakref
from functools import partial
from osgeo import ogr

# Import logging for error handling
from .modules.logging_config import get_app_logger
logger = get_app_logger()
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
from qgis.PyQt.QtWidgets import (
    QAction,
    QActionGroup,
    QApplication,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidgetAction
)
from qgis.core import (
    Qgis,
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
    QgsCollapsibleGroupBox,
    QgsDoubleSpinBox,
    QgsFeaturePickerWidget,
    QgsFieldComboBox,
    QgsFieldExpressionWidget,
    QgsMapLayerComboBox,
    QgsProjectionSelectionWidget,
    QgsPropertyOverrideButton
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
from .modules.object_safety import is_valid_layer, is_sip_deleted
from .modules.appUtils import (
    get_datasource_connexion_from_layer,
    get_primary_key_name,
    get_best_display_field,
    get_value_relation_info,
    get_field_display_expression,
    get_layer_display_expression,
    get_fields_with_value_relations,
    POSTGRESQL_AVAILABLE,
    is_layer_source_available
)
from .modules.customExceptions import SignalStateChangeError
from .modules.constants import PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR, get_geometry_type_string
from .modules.ui_styles import StyleLoader, QGISThemeWatcher
from .modules.feedback_utils import show_info, show_warning, show_error, show_success
from .modules.config_helpers import set_config_value
from .modules.exploring_cache import ExploringFeaturesCache
from .filter_mate_dockwidget_base import Ui_FilterMateDockWidgetBase

# Import async expression evaluation for large layers (v2.5.10)
try:
    from .modules.tasks.expression_evaluation_task import (
        ExpressionEvaluationTask,
        get_expression_manager
    )
    ASYNC_EXPRESSION_AVAILABLE = True
except ImportError:
    ASYNC_EXPRESSION_AVAILABLE = False
    get_expression_manager = None

# Import CRS utilities for improved CRS compatibility (v2.5.7)
try:
    from .modules.crs_utils import (
        is_geographic_crs,
        get_optimal_metric_crs,
        CRSTransformer,
        get_crs_units,
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
    from .modules.ui_config import UIConfig
    from .modules import ui_widget_utils as ui_utils
    UI_CONFIG_AVAILABLE = True
except ImportError:
    UI_CONFIG_AVAILABLE = False

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
        """Constructor."""
        super(FilterMateDockWidget, self).__init__(parent)
        
        self.exception = None
        self.iface = iface

        self.plugin_dir = plugin_dir
        self.CONFIG_DATA = config_data
        self.PROJECT_LAYERS = project_layers
        self.PROJECT = project
        self.current_layer = None
        self.current_layer_selection_connection = None
        
        # Protection flags against recursive calls
        self._updating_layers = False
        self._updating_current_layer = False
        self._updating_groupbox = False  # Prevents infinite loop in groupbox collapse/expand signals
        self._signals_connected = False
        self._pending_layers_update = False  # Flag to track if layers were updated before widgets_initialized
        self._plugin_busy = False  # Global flag to block operations during critical changes (project load, etc.)
        self._syncing_from_qgis = False  # Flag to prevent infinite recursion in QGIS ↔ widgets synchronization
        
        # Flag to track if LAYER_TREE_VIEW signal is connected (for bidirectional sync)
        self._layer_tree_view_signal_connected = False
        
        # Signal connection state tracking to avoid redundant connect/disconnect calls
        # Key format: "WIDGET_GROUP.WIDGET_NAME.SIGNAL_NAME" -> bool (True=connected, False=disconnected)
        self._signal_connection_states = {}
        
        # Theme watcher for automatic dark/light mode switching
        self._theme_watcher = None
        
        # PERFORMANCE: Debounce timers for expression changes
        # Prevents excessive recomputation when user types quickly or makes rapid changes
        self._expression_debounce_timer = QTimer()
        self._expression_debounce_timer.setSingleShot(True)
        self._expression_debounce_timer.setInterval(450)  # 450ms debounce delay
        self._expression_debounce_timer.timeout.connect(self._execute_debounced_expression_change)
        self._pending_expression_change = None  # Stores pending (groupbox, expression) tuple
        
        # PERFORMANCE: Cache for expression evaluation results
        # Avoids recomputing same expressions repeatedly
        self._expression_cache = {}  # Key: (layer_id, expression) -> Value: (features, timestamp)
        self._expression_cache_max_age = 60.0  # Cache entries expire after 60 seconds
        self._expression_cache_max_size = 100  # Maximum cache entries
        
        # PERFORMANCE (v2.5.10): Async expression evaluation for large layers
        # Threshold above which expression evaluation runs in background task
        self._async_expression_threshold = 10000  # Features count threshold for async
        self._expression_manager = get_expression_manager() if ASYNC_EXPRESSION_AVAILABLE else None
        self._pending_async_evaluation = None  # Track pending async evaluation
        
        # Loading state tracking for UI feedback
        self._expression_loading = False
        
        # Initialize layer state
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
        """Initialize layer-related state during __init__."""
        # Check for vector layers in the project, not just PROJECT_LAYERS
        # PROJECT_LAYERS may be empty on initialization even if vector layers exist
        if self.PROJECT:
            vector_layers = [layer for layer in self.PROJECT.mapLayers().values() 
                           if isinstance(layer, QgsVectorLayer)]
            if len(vector_layers) > 0:
                self.init_layer = self.iface.activeLayer() if self.iface.activeLayer() is not None else vector_layers[0]
                self.has_loaded_layers = True
            else:
                self.init_layer = None
                self.has_loaded_layers = False
        else:
            self.init_layer = None
            self.has_loaded_layers = False


        self.widgets = None
        self.widgets_initialized = False
        self.current_exploring_groupbox = None
        self.tabTools_current_index = 0
        self.backend_indicator_label = None
        self.plugin_title_label = None
        self.frame_header = None

        # Initialize exploring features cache for flash/zoom/identify operations
        # Cache stores selected features and pre-computed bounding boxes per groupbox
        self._exploring_cache = ExploringFeaturesCache(max_layers=50, max_age_seconds=300.0)
        logger.debug("Initialized exploring features cache")

        self.predicates = None
        self.buffer_property_has_been_init = False
        self.project_props = None
        self.layer_properties_tuples_dict = None
        self.export_properties_tuples_dict = None
        self.json_template_project_exporting = '{"has_layers_to_export":false,"layers_to_export":[],"has_projection_to_export":false,"projection_to_export":"","has_styles_to_export":false,"styles_to_export":"","has_datatype_to_export":false,"datatype_to_export":"","datatype_to_export":"","has_output_folder_to_export":false,"output_folder_to_export":"","has_zip_to_export":false,"zip_to_export":"","batch_output_folder":false,"batch_zip":false }'

        # Initialize config changes tracking
        self.pending_config_changes = []
        self.config_changes_pending = False

        # Initialize IconThemeManager early (before any icons are set)
        if ICON_THEME_AVAILABLE:
            try:
                current_theme = StyleLoader.detect_qgis_theme()
                IconThemeManager.set_theme(current_theme)
                logger.debug(f"Early IconThemeManager init: {current_theme}")
            except Exception as e:
                logger.warning(f"Could not initialize IconThemeManager early: {e}")

        logger.info("FilterMate DockWidget: Starting setupUi()")
        self.setupUi(self)
        logger.info("FilterMate DockWidget: setupUi() complete, starting setupUiCustom()")
        self.setupUiCustom()
        logger.info("FilterMate DockWidget: setupUiCustom() complete, starting manage_ui_style()")
        self.manage_ui_style()
        logger.info("FilterMate DockWidget: manage_ui_style() complete")
        
        # Call manage_interactions() synchronously
        logger.info("FilterMate DockWidget: Calling manage_interactions() synchronously")
        try:
            self.manage_interactions()
            logger.info("FilterMate DockWidget: manage_interactions() complete")
        except Exception as e:
            logger.error(f"FilterMate DockWidget: Error in manage_interactions(): {e}", exc_info=True)
    
    def _deferred_manage_interactions(self):
        """Deferred initialization - NOT USED during debugging."""
        # This method is not called during debugging
        pass
        

    def getSignal(self, oObject : QObject, strSignalName : str):
        """Get signal from QObject by name with caching for performance.
        
        Uses a class-level cache to avoid repeated iteration over metaObject
        which can be very slow for complex QGIS widgets with many methods.
        
        Args:
            oObject: Qt object to search for signal
            strSignalName: Name of the signal to find
            
        Returns:
            QMetaMethod: The signal method if found, None otherwise
        """
        # Create cache key from object's class name and signal name
        # Using class name instead of object id since signals are class-level
        class_name = oObject.metaObject().className()
        cache_key = f"{class_name}.{strSignalName}"
        
        # Check cache first
        if cache_key in FilterMateDockWidget._signal_cache:
            return FilterMateDockWidget._signal_cache[cache_key]
        
        # Not in cache - search metaObject
        oMetaObj = oObject.metaObject()
        for i in range(oMetaObj.methodCount()):
            oMetaMethod = oMetaObj.method(i)
            if not oMetaMethod.isValid():
                continue
            if oMetaMethod.methodType() == QMetaMethod.Signal and \
                oMetaMethod.name() == strSignalName:
                # Cache the result
                FilterMateDockWidget._signal_cache[cache_key] = oMetaMethod
                return oMetaMethod
        
        # Signal not found - cache None to avoid repeated searches
        FilterMateDockWidget._signal_cache[cache_key] = None
        return None

    def manageSignal(self, widget_path, custom_action=None, custom_signal_name=None):
        current_signal_name = None
        current_triggered_function = None
        state = None
        widget_object = None

        if isinstance(widget_path, list) and len(widget_path) == 2:
            widget_object = self.widgets[widget_path[0]][widget_path[1]]
        else:
            raise SignalStateChangeError(state, widget_path, 'Incorrect input parameters')

        if custom_signal_name is not None:
           for signal in widget_object["SIGNALS"]:
               if signal[0] == custom_signal_name and signal[-1] is not None:
                    current_signal_name = custom_signal_name
                    current_triggered_function = signal[-1]
                    
                    # OPTIMIZATION: Check cached state to avoid redundant operations
                    state_key = f"{widget_path[0]}.{widget_path[1]}.{current_signal_name}"
                    cached_state = self._signal_connection_states.get(state_key)
                    
                    if custom_action == 'connect' and cached_state is True:
                        # Already connected, skip
                        state = True
                        continue
                    elif custom_action == 'disconnect' and cached_state is False:
                        # Already disconnected, skip
                        state = False
                        continue
                    
                    state = self.changeSignalState(widget_path, current_signal_name, current_triggered_function, custom_action)
                    # Update cached state
                    self._signal_connection_states[state_key] = state

        else:
            for signal in widget_object["SIGNALS"]:
                if signal[-1] is not None:
                    current_signal_name = str(signal[0])
                    current_triggered_function = signal[-1]
                    
                    # OPTIMIZATION: Check cached state to avoid redundant operations
                    state_key = f"{widget_path[0]}.{widget_path[1]}.{current_signal_name}"
                    cached_state = self._signal_connection_states.get(state_key)
                    
                    if custom_action == 'connect' and cached_state is True:
                        # Already connected, skip
                        state = True
                        continue
                    elif custom_action == 'disconnect' and cached_state is False:
                        # Already disconnected, skip
                        state = False
                        continue
                    
                    state = self.changeSignalState(widget_path, current_signal_name, current_triggered_function, custom_action)
                    # Update cached state
                    self._signal_connection_states[state_key] = state
        
        # PERFORMANCE FIX: If state is None but there are signals with None handlers,
        # that means signals are intentionally handled elsewhere (e.g., with debounce).
        # Return True to indicate success rather than raising an error.
        if state is None:
            # Check if there are any signals defined (even with None handlers)
            if len(widget_object["SIGNALS"]) > 0:
                # Signals exist but all have None handlers - this is intentional
                return True
            raise SignalStateChangeError(state, widget_path)

        return state
        

        

    def changeSignalState(self, widget_path, current_signal_name, current_triggered_function, custom_action=None):
        state = None

        if isinstance(widget_path, list) and len(widget_path) == 2:
            if hasattr(self.widgets[widget_path[0]][widget_path[1]]["WIDGET"], current_signal_name):
                # Special handling for LAYER_TREE_VIEW to use specific handler disconnect
                is_layer_tree_view = (widget_path == ["QGIS", "LAYER_TREE_VIEW"])
                
                if is_layer_tree_view:
                    # Use our own flag to track connection state
                    state = self._layer_tree_view_signal_connected
                else:
                    state = self.widgets[widget_path[0]][widget_path[1]]["WIDGET"].isSignalConnected(self.getSignal(self.widgets[widget_path[0]][widget_path[1]]["WIDGET"], current_signal_name))
                
                if custom_action is not None:
                    if custom_action == 'disconnect' and state is True:
                        try:
                            # Use specific handler for disconnect to not break other connections
                            getattr(self.widgets[widget_path[0]][widget_path[1]]["WIDGET"], current_signal_name).disconnect(current_triggered_function)
                            if is_layer_tree_view:
                                self._layer_tree_view_signal_connected = False
                        except TypeError:
                            # Signal was not connected or already disconnected
                            if is_layer_tree_view:
                                self._layer_tree_view_signal_connected = False
                    elif custom_action == 'connect' and state is False:
                        try:
                            getattr(self.widgets[widget_path[0]][widget_path[1]]["WIDGET"], current_signal_name).connect(current_triggered_function)
                            if is_layer_tree_view:
                                self._layer_tree_view_signal_connected = True
                        except TypeError:
                            # Already connected
                            if is_layer_tree_view:
                                self._layer_tree_view_signal_connected = True
                    elif custom_action == 'connect' and state is True:
                        pass  # Already connected, skip
                else:
                    if state is True:
                        try:
                            getattr(self.widgets[widget_path[0]][widget_path[1]]["WIDGET"], current_signal_name).disconnect(current_triggered_function)
                            if is_layer_tree_view:
                                self._layer_tree_view_signal_connected = False
                        except TypeError:
                            if is_layer_tree_view:
                                self._layer_tree_view_signal_connected = False
                    else:
                        try:
                            getattr(self.widgets[widget_path[0]][widget_path[1]]["WIDGET"], current_signal_name).connect(current_triggered_function)
                            if is_layer_tree_view:
                                self._layer_tree_view_signal_connected = True
                        except TypeError:
                            if is_layer_tree_view:
                                self._layer_tree_view_signal_connected = True

                if is_layer_tree_view:
                    state = self._layer_tree_view_signal_connected
                else:
                    state = self.widgets[widget_path[0]][widget_path[1]]["WIDGET"].isSignalConnected(self.getSignal(self.widgets[widget_path[0]][widget_path[1]]["WIDGET"], current_signal_name))
                
                return state
        
        if state is None:
            raise SignalStateChangeError(state, widget_path)

    def reset_multiple_checkable_combobox(self):
        """
        Safely reset and recreate the multiple checkable combobox widget.
        
        This method handles proper cleanup of the old widget and creation of a new one
        to avoid Qt memory issues and crashes.
        """
        try:
            # Use the horizontal layout that contains the combobox
            layout = self.horizontalLayout_exploring_multiple_feature_picker
            
            # Safely remove old widget from layout (it's at index 0)
            if layout.count() > 0:
                item = layout.itemAt(0)
                if item and item.widget():
                    old_widget = item.widget()
                    layout.removeWidget(old_widget)
                    # Properly delete the old widget to free resources
                    old_widget.deleteLater()
            
            # Reset and close widget safely
            if hasattr(self, 'checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection') and \
               self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection is not None:
                try:
                    self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection.reset()
                    self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection.close()
                    self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection.deleteLater()
                except (RuntimeError, AttributeError) as e:
                    # Widget may already be deleted or being destroyed
                    logger.debug(f"Could not close widget (may already be destroyed): {e}")
            
            # Create new widget
            self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection = None
            self.set_multiple_checkable_combobox()

            # Insert new widget into layout (at position 0, before the order by button)
            if self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection is not None:
                layout.insertWidget(0, self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection)
                layout.update()

                # Update widgets registry
                self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"] = {
                    "TYPE": "CustomCheckableFeatureComboBox",
                    "WIDGET": self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection,
                    "SIGNALS": [
                        ("updatingCheckedItemList", self.exploring_features_changed),
                        ("filteringCheckedItemList", self.exploring_source_params_changed)
                    ]
                }
        except Exception as e:
            logger.error(f"Error resetting multiple checkable combobox: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def set_multiple_checkable_combobox(self):
        self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection = QgsCheckableComboBoxFeaturesListPickerWidget(self.CONFIG_DATA, self)


    def _fix_toolbox_icons(self):
        """
        Fix toolBox_tabTools icons with absolute paths.
        
        The auto-generated filter_mate_dockwidget_base.py uses relative paths
        for icons which don't work. This method replaces them with absolute paths.
        """
        toolbox_icons = {
            0: "filter_multi.png",   # FILTERING tab
            1: "save.png",           # EXPORTING tab
            2: "parameters.png"      # CONFIGURATION tab
        }
        
        for index, icon_file in toolbox_icons.items():
            icon_path = os.path.join(self.plugin_dir, "icons", icon_file)
            if os.path.exists(icon_path):
                # Use themed icon for dark mode support
                if ICON_THEME_AVAILABLE:
                    icon = get_themed_icon(icon_path)
                else:
                    icon = QtGui.QIcon(icon_path)
                self.toolBox_tabTools.setItemIcon(index, icon)


    def setupUiCustom(self):
        self.set_multiple_checkable_combobox()
        
        # Setup splitter between frame_exploring and frame_toolset
        self._setup_main_splitter()
        
        # Apply dynamic dimensions based on active profile
        self.apply_dynamic_dimensions()
        
        # Fix toolBox icons with absolute paths
        self._fix_toolbox_icons()

        # Setup backend indicator (right-aligned label showing current backend)
        self._setup_backend_indicator()
        
        # Setup action bar layout based on configuration
        self._setup_action_bar_layout()

    def _setup_main_splitter(self):
        """
        Setup the main splitter between frame_exploring and frame_toolset.
        
        The splitter already exists as 'splitter_main' from the .ui file.
        This method configures it using UIConfig settings for optimal behavior.
        
        Configuration includes:
        - Handle width and margins
        - Stretch factors for proportional sizing
        - Collapsible behavior
        - Size policies for child frames
        - Initial size distribution
        """
        from .modules.ui_config import UIConfig
        from qgis.PyQt.QtWidgets import QSizePolicy
        
        try:
            # The splitter already exists from the .ui file as splitter_main
            # Just reference it as main_splitter for consistency
            self.main_splitter = self.splitter_main
            
            # Get splitter configuration from UIConfig
            splitter_config = UIConfig.get_config('splitter')
            handle_width = splitter_config.get('handle_width', 6)
            handle_margin = splitter_config.get('handle_margin', 40)
            exploring_stretch = splitter_config.get('exploring_stretch', 2)
            toolset_stretch = splitter_config.get('toolset_stretch', 5)
            collapsible = splitter_config.get('collapsible', False)
            opaque_resize = splitter_config.get('opaque_resize', True)
            
            # Configure splitter properties
            self.main_splitter.setChildrenCollapsible(collapsible)
            self.main_splitter.setHandleWidth(handle_width)
            self.main_splitter.setOpaqueResize(opaque_resize)
            
            # Style the splitter handle - subtle and minimal
            self.main_splitter.setStyleSheet(f"""
                QSplitter::handle:vertical {{
                    background-color: #d0d0d0;
                    height: {handle_width - 2}px;
                    margin: 2px {handle_margin}px;
                    border-radius: {(handle_width - 2) // 2}px;
                }}
                QSplitter::handle:vertical:hover {{
                    background-color: #3498db;
                }}
            """)
            
            # Configure size policies for frames
            self._apply_splitter_frame_policies()
            
            # Set stretch factors for proportional sizing
            self.main_splitter.setStretchFactor(0, exploring_stretch)
            self.main_splitter.setStretchFactor(1, toolset_stretch)
            
            # Set initial sizes based on available height
            self._set_initial_splitter_sizes()
            
            logger.debug(f"Main splitter setup: handle={handle_width}px, "
                        f"stretch={exploring_stretch}:{toolset_stretch}, "
                        f"collapsible={collapsible}")
            
        except Exception as e:
            logger.error(f"Error setting up main splitter: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.main_splitter = None
        
        # Setup action bar layout
        self._setup_action_bar_layout()
        
        # Setup tab-specific widgets (always needed regardless of splitter)
        self._setup_exploring_tab_widgets()
        self._setup_filtering_tab_widgets()
        self._setup_exporting_tab_widgets()

        # Continue setupUiCustom after widget creation
        if 'CURRENT_PROJECT' in self.CONFIG_DATA:
            self.project_props = self.CONFIG_DATA["CURRENT_PROJECT"]

        self.manage_configuration_model()
        self.dockwidget_widgets_configuration()
        
        # Setup anti-truncation tooltips for widgets with potentially long text
        self._setup_truncation_tooltips()
    
    def _apply_splitter_frame_policies(self):
        """
        Apply size policies to frames within the splitter.
        
        This ensures proper behavior when resizing:
        - frame_exploring: Minimum policy (can shrink to min but prefers base)
        - frame_toolset: Expanding policy (takes remaining space)
        """
        from .modules.ui_config import UIConfig
        from qgis.PyQt.QtWidgets import QSizePolicy
        
        # Map string policies to Qt enum values
        policy_map = {
            'Fixed': QSizePolicy.Fixed,
            'Minimum': QSizePolicy.Minimum,
            'Maximum': QSizePolicy.Maximum,
            'Preferred': QSizePolicy.Preferred,
            'Expanding': QSizePolicy.Expanding,
            'MinimumExpanding': QSizePolicy.MinimumExpanding,
            'Ignored': QSizePolicy.Ignored
        }
        
        # Configure frame_exploring
        if hasattr(self, 'frame_exploring'):
            exploring_config = UIConfig.get_config('frame_exploring')
            if exploring_config:
                h_policy = policy_map.get(exploring_config.get('size_policy_h', 'Preferred'), QSizePolicy.Preferred)
                v_policy = policy_map.get(exploring_config.get('size_policy_v', 'Minimum'), QSizePolicy.Minimum)
                self.frame_exploring.setSizePolicy(h_policy, v_policy)
                logger.debug(f"frame_exploring policy: {exploring_config.get('size_policy_h')}/{exploring_config.get('size_policy_v')}")
        
        # Configure frame_toolset
        if hasattr(self, 'frame_toolset'):
            toolset_config = UIConfig.get_config('frame_toolset')
            if toolset_config:
                h_policy = policy_map.get(toolset_config.get('size_policy_h', 'Preferred'), QSizePolicy.Preferred)
                v_policy = policy_map.get(toolset_config.get('size_policy_v', 'Expanding'), QSizePolicy.Expanding)
                self.frame_toolset.setSizePolicy(h_policy, v_policy)
                logger.debug(f"frame_toolset policy: {toolset_config.get('size_policy_h')}/{toolset_config.get('size_policy_v')}")
    
    def _set_initial_splitter_sizes(self):
        """
        Set initial splitter sizes based on configuration ratios.
        
        Uses the available height to distribute space between frames
        according to the configured ratios (50/50 by default for equal space).
        """
        from .modules.ui_config import UIConfig
        
        splitter_config = UIConfig.get_config('splitter')
        exploring_ratio = splitter_config.get('initial_exploring_ratio', 0.50)
        toolset_ratio = splitter_config.get('initial_toolset_ratio', 0.50)
        
        # Get available height from splitter or use default
        total_height = self.main_splitter.height()
        if total_height < 100:  # Splitter not yet sized, use reasonable default
            total_height = 600
        
        # Calculate sizes based on ratios for equal distribution
        exploring_size = int(total_height * exploring_ratio)
        toolset_size = int(total_height * toolset_ratio)
        
        # Set sizes - Qt will adjust based on actual available space
        self.main_splitter.setSizes([exploring_size, toolset_size])
        
        logger.debug(f"Initial splitter sizes: exploring={exploring_size}px ({exploring_ratio:.0%}), toolset={toolset_size}px ({toolset_ratio:.0%})")


    def apply_dynamic_dimensions(self):
        """
        Apply dynamic dimensions to widgets based on active UI profile (compact/normal).
        
        Orchestrates the application of dimensions by calling specialized methods.
        Called from setupUiCustom() during initialization.
        """
        try:
            # Apply dockwidget minimum size based on profile
            self._apply_dockwidget_dimensions()
            
            # Apply dimensions in logical groups
            self._apply_widget_dimensions()
            self._apply_frame_dimensions()
            self._harmonize_checkable_pushbuttons()
            self._apply_layout_spacing()
            self._harmonize_spacers()
            self._apply_qgis_widget_dimensions()
            self._align_key_layouts()
            self._adjust_row_spacing()
            
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
        from .modules.ui_config import UIConfig
        from qgis.PyQt.QtCore import QSize
        
        # Get dockwidget dimensions from active profile
        min_width = UIConfig.get_config('dockwidget', 'min_width')
        min_height = UIConfig.get_config('dockwidget', 'min_height')
        preferred_width = UIConfig.get_config('dockwidget', 'preferred_width')
        preferred_height = UIConfig.get_config('dockwidget', 'preferred_height')
        
        if min_width and min_height:
            self.setMinimumSize(QSize(min_width, min_height))
            logger.debug(f"Applied dockwidget minimum size: {min_width}x{min_height}px")
        
        # Set a reasonable preferred size (not enforced, just a hint)
        if preferred_width and preferred_height:
            # Only resize if current size is larger than preferred (don't expand small windows)
            current_size = self.size()
            if current_size.width() > preferred_width or current_size.height() > preferred_height:
                self.resize(preferred_width, preferred_height)
                logger.debug(f"Resized dockwidget to preferred size: {preferred_width}x{preferred_height}px")
    
    def _apply_widget_dimensions(self):
        """
        Apply dimensions to standard Qt widgets (ComboBox, LineEdit, SpinBox, GroupBox).
        
        Reads dimensions from UIConfig and applies them to all relevant widgets
        using findChildren() for batch processing.
        """
        from .modules.ui_config import UIConfig
        from qgis.PyQt.QtWidgets import QComboBox, QLineEdit, QDoubleSpinBox, QSpinBox, QGroupBox
        
        # Get dimensions from active profile
        combobox_height = UIConfig.get_config('combobox', 'height')
        input_height = UIConfig.get_config('input', 'height')
        groupbox_min_height = UIConfig.get_config('groupbox', 'min_height')
        
        # Apply to ComboBoxes
        for combo in self.findChildren(QComboBox):
            combo.setMinimumHeight(combobox_height)
            combo.setMaximumHeight(combobox_height)
            combo.setSizePolicy(combo.sizePolicy().horizontalPolicy(), 
                              QtWidgets.QSizePolicy.Fixed)
        
        # Apply to LineEdits
        for line_edit in self.findChildren(QLineEdit):
            line_edit.setMinimumHeight(input_height)
            line_edit.setMaximumHeight(input_height)
            line_edit.setSizePolicy(line_edit.sizePolicy().horizontalPolicy(), 
                                   QtWidgets.QSizePolicy.Fixed)
        
        # Apply to SpinBoxes (QDoubleSpinBox and QSpinBox)
        for spinbox in self.findChildren(QDoubleSpinBox):
            spinbox.setMinimumHeight(input_height)
            spinbox.setMaximumHeight(input_height)
            spinbox.setSizePolicy(spinbox.sizePolicy().horizontalPolicy(), 
                                QtWidgets.QSizePolicy.Fixed)
        
        for spinbox in self.findChildren(QSpinBox):
            spinbox.setMinimumHeight(input_height)
            spinbox.setMaximumHeight(input_height)
            spinbox.setSizePolicy(spinbox.sizePolicy().horizontalPolicy(), 
                                QtWidgets.QSizePolicy.Fixed)
        
        # Apply to GroupBoxes (QgsCollapsibleGroupBox included)
        for groupbox in self.findChildren(QGroupBox):
            groupbox.setMinimumHeight(groupbox_min_height)
        
        logger.debug(f"Applied widget dimensions: ComboBox={combobox_height}px, Input={input_height}px")
    
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
        from .modules.ui_config import UIConfig
        from qgis.PyQt.QtWidgets import QSizePolicy
        
        # Map string policies to Qt enum values
        policy_map = {
            'Fixed': QSizePolicy.Fixed,
            'Minimum': QSizePolicy.Minimum,
            'Maximum': QSizePolicy.Maximum,
            'Preferred': QSizePolicy.Preferred,
            'Expanding': QSizePolicy.Expanding,
            'MinimumExpanding': QSizePolicy.MinimumExpanding,
            'Ignored': QSizePolicy.Ignored
        }
        
        # Get widget_keys dimensions
        widget_keys_min_width = UIConfig.get_config('widget_keys', 'min_width')
        widget_keys_max_width = UIConfig.get_config('widget_keys', 'max_width')
        
        # Get frame exploring configuration
        exploring_config = UIConfig.get_config('frame_exploring')
        exploring_min = exploring_config.get('min_height', 120) if exploring_config else 120
        exploring_max = exploring_config.get('max_height', 350) if exploring_config else 350
        exploring_h_policy = exploring_config.get('size_policy_h', 'Preferred') if exploring_config else 'Preferred'
        exploring_v_policy = exploring_config.get('size_policy_v', 'Minimum') if exploring_config else 'Minimum'
        
        # Get frame toolset configuration
        toolset_config = UIConfig.get_config('frame_toolset')
        toolset_min = toolset_config.get('min_height', 200) if toolset_config else 200
        toolset_max = toolset_config.get('max_height', 16777215) if toolset_config else 16777215
        toolset_h_policy = toolset_config.get('size_policy_h', 'Preferred') if toolset_config else 'Preferred'
        toolset_v_policy = toolset_config.get('size_policy_v', 'Expanding') if toolset_config else 'Expanding'
        
        # Get frame filtering configuration
        filtering_config = UIConfig.get_config('frame_filtering')
        filtering_min = filtering_config.get('min_height', 180) if filtering_config else 180
        
        # Get widget_keys padding and border radius from config
        widget_keys_config = UIConfig.get_config('widget_keys')
        widget_keys_padding = widget_keys_config.get('padding', 2) if widget_keys_config else 2
        
        # Apply to widget keys containers with enhanced styling
        for widget_name in ['widget_exploring_keys', 'widget_filtering_keys', 'widget_exporting_keys']:
            if hasattr(self, widget_name):
                widget = getattr(self, widget_name)
                widget.setMinimumWidth(widget_keys_min_width)
                widget.setMaximumWidth(widget_keys_max_width)
                # Apply consistent padding via layout margins
                layout = widget.layout()
                if layout:
                    layout.setContentsMargins(widget_keys_padding, widget_keys_padding, 
                                            widget_keys_padding, widget_keys_padding)
                    layout.setSpacing(0)  # No extra spacing in container
        
        # Apply to frame_exploring with size policy
        if hasattr(self, 'frame_exploring'):
            self.frame_exploring.setMinimumHeight(exploring_min)
            self.frame_exploring.setMaximumHeight(exploring_max)
            h_policy = policy_map.get(exploring_h_policy, QSizePolicy.Preferred)
            v_policy = policy_map.get(exploring_v_policy, QSizePolicy.Minimum)
            self.frame_exploring.setSizePolicy(h_policy, v_policy)
        
        # Apply to frame_toolset with size policy
        if hasattr(self, 'frame_toolset'):
            self.frame_toolset.setMinimumHeight(toolset_min)
            self.frame_toolset.setMaximumHeight(toolset_max)
            h_policy = policy_map.get(toolset_h_policy, QSizePolicy.Preferred)
            v_policy = policy_map.get(toolset_v_policy, QSizePolicy.Expanding)
            self.frame_toolset.setSizePolicy(h_policy, v_policy)
        
        # Apply to frame_filtering (if it exists inside toolbox)
        if hasattr(self, 'frame_filtering'):
            self.frame_filtering.setMinimumHeight(filtering_min)
        
        logger.debug(f"Applied frame dimensions: exploring={exploring_min}-{exploring_max}px ({exploring_v_policy}), "
                    f"toolset={toolset_min}px+ ({toolset_v_policy}), "
                    f"widget_keys={widget_keys_min_width}-{widget_keys_max_width}px")
    
    def _harmonize_checkable_pushbuttons(self):
        """
        Harmonize dimensions of all checkable pushbuttons across tabs.
        
        Applies consistent sizing to exploring, filtering, and exporting pushbuttons
        based on the active UI profile (compact/normal/hidpi) using key_button dimensions
        from UIConfig.
        """
        try:
            from qgis.PyQt.QtWidgets import QPushButton, QSizePolicy
            from qgis.PyQt.QtCore import QSize
            from .modules.ui_config import UIConfig, DisplayProfile
            
            # Get dynamic dimensions from key_button config
            key_button_config = UIConfig.get_config('key_button')
            
            # Profile-aware fallback values
            current_profile = UIConfig.get_profile()
            if key_button_config:
                pushbutton_min_size = key_button_config.get('min_size', 26)
                pushbutton_max_size = key_button_config.get('max_size', 32)
                pushbutton_icon_size = key_button_config.get('icon_size', 16)
                button_spacing = key_button_config.get('spacing', 2)
            else:
                # Fallback values based on profile if config not available
                if current_profile == DisplayProfile.COMPACT:
                    pushbutton_min_size = 26
                    pushbutton_max_size = 32
                    pushbutton_icon_size = 16
                    button_spacing = 2
                elif current_profile == DisplayProfile.HIDPI:
                    pushbutton_min_size = 36
                    pushbutton_max_size = 44
                    pushbutton_icon_size = 24
                    button_spacing = 6
                else:  # NORMAL
                    pushbutton_min_size = 30
                    pushbutton_max_size = 36
                    pushbutton_icon_size = 18
                    button_spacing = 4
            
            # Get all checkable pushbuttons with consistent naming pattern
            checkable_buttons = []
            
            # Exploring buttons (including non-checkable explore buttons)
            exploring_button_names = [
                'pushButton_exploring_identify',
                'pushButton_exploring_zoom',
                'pushButton_checkable_exploring_selecting',
                'pushButton_checkable_exploring_tracking',
                'pushButton_checkable_exploring_linking_widgets',
                'pushButton_exploring_reset_layer_properties'
            ]
            
            # Filtering buttons
            filtering_button_names = [
                'pushButton_checkable_filtering_auto_current_layer',
                'pushButton_checkable_filtering_layers_to_filter',
                'pushButton_checkable_filtering_current_layer_combine_operator',
                'pushButton_checkable_filtering_geometric_predicates',
                'pushButton_checkable_filtering_buffer_value',
                'pushButton_checkable_filtering_buffer_type'
            ]
            
            # Exporting buttons
            exporting_button_names = [
                'pushButton_checkable_exporting_layers',
                'pushButton_checkable_exporting_projection',
                'pushButton_checkable_exporting_styles',
                'pushButton_checkable_exporting_datatype',
                'pushButton_checkable_exporting_output_folder',
                'pushButton_checkable_exporting_zip'
            ]
            
            all_button_names = exploring_button_names + filtering_button_names + exporting_button_names
            
            # Apply consistent dimensions to all key pushbuttons
            for button_name in all_button_names:
                if hasattr(self, button_name):
                    button = getattr(self, button_name)
                    if isinstance(button, QPushButton):
                        # Set consistent square size constraints
                        button.setMinimumSize(pushbutton_min_size, pushbutton_min_size)
                        button.setMaximumSize(pushbutton_max_size, pushbutton_max_size)
                        
                        # Set consistent icon size
                        button.setIconSize(QSize(pushbutton_icon_size, pushbutton_icon_size))
                        
                        # Ensure consistent style properties
                        button.setFlat(True)
                        
                        # Set consistent size policy - Fixed for uniform sizing
                        button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                        
                        checkable_buttons.append(button_name)
            
            # Apply spacing to layout containers
            for layout_name in ['verticalLayout_exploring_content', 
                               'verticalLayout_filtering_keys',
                               'verticalLayout_exporting_keys']:
                if hasattr(self, layout_name):
                    layout = getattr(self, layout_name)
                    layout.setSpacing(button_spacing)
            
            mode_name = UIConfig.get_profile_name()
            logger.debug(f"Harmonized {len(checkable_buttons)} key pushbuttons in {mode_name} mode: {pushbutton_min_size}-{pushbutton_max_size}px (icon: {pushbutton_icon_size}px)")
            
        except Exception as e:
            logger.warning(f"Could not harmonize checkable pushbuttons: {e}")
            import traceback
            traceback.print_exc()
    
    def _apply_layout_spacing(self):
        """
        Apply consistent spacing to layouts across all tabs.
        
        Uses harmonized spacing values from UIConfig to ensure
        uniform visual appearance across the entire UI.
        """
        try:
            from .modules.ui_config import UIConfig
            
            # Get harmonized layout spacing from config
            layout_spacing = UIConfig.get_config('layout', 'spacing_frame') or 8
            content_spacing = UIConfig.get_config('layout', 'spacing_content') or 6
            section_spacing = UIConfig.get_config('layout', 'spacing_section') or 8
            main_spacing = UIConfig.get_config('layout', 'spacing_main') or 8
            
            # Get key button spacing for harmonized key layouts
            key_button_config = UIConfig.get_config('key_button')
            button_spacing = key_button_config.get('spacing', 2) if key_button_config else 2
            
            # Apply main container spacing for better responsiveness
            if hasattr(self, 'verticalLayout_main_content'):
                self.verticalLayout_main_content.setSpacing(main_spacing)
            
            # Apply spacing to exploring layouts
            exploring_layouts = [
                'verticalLayout_exploring_single_selection',
                'verticalLayout_exploring_multiple_selection',
                'verticalLayout_exploring_custom_selection'
            ]
            for layout_name in exploring_layouts:
                if hasattr(self, layout_name):
                    getattr(self, layout_name).setSpacing(layout_spacing)
            
            # Apply spacing to filtering layouts - keys use button spacing, values use content spacing
            if hasattr(self, 'verticalLayout_filtering_keys'):
                self.verticalLayout_filtering_keys.setSpacing(button_spacing)
            if hasattr(self, 'verticalLayout_filtering_values'):
                self.verticalLayout_filtering_values.setSpacing(content_spacing)
            
            # Apply spacing to exporting layouts - keys use button spacing, values use content spacing
            if hasattr(self, 'verticalLayout_exporting_keys'):
                self.verticalLayout_exporting_keys.setSpacing(button_spacing)
            if hasattr(self, 'verticalLayout_exporting_values'):
                self.verticalLayout_exporting_values.setSpacing(content_spacing)
            
            # Apply spacing to exploring key layout
            if hasattr(self, 'verticalLayout_exploring_content'):
                self.verticalLayout_exploring_content.setSpacing(button_spacing)
            
            # Note: Content margins for horizontal_layouts are now handled by _align_key_layouts
            # to ensure consistent vertical alignment of toolbar bars across all tabs
            # Only apply spacing here, margins are set to 0 in _align_key_layouts
            section_spacing_adjusted = UIConfig.get_config('layout', 'spacing_section') or 4
            horizontal_layouts = [
                'horizontalLayout_filtering_content',
                'horizontalLayout_exporting_content'
            ]
            for layout_name in horizontal_layouts:
                if hasattr(self, layout_name):
                    layout = getattr(self, layout_name)
                    layout.setSpacing(section_spacing_adjusted)
            
            # Apply harmonized margins to groupbox layouts
            margins_frame = UIConfig.get_config('layout', 'margins_frame')
            if margins_frame and isinstance(margins_frame, dict):
                left = margins_frame.get('left', 8)
                top = margins_frame.get('top', 8)
                right = margins_frame.get('right', 8)
                bottom = margins_frame.get('bottom', 10)
                
                # Exploring groupbox layouts
                groupbox_layouts = [
                    'gridLayout_exploring_single_content',
                    'gridLayout_exploring_multiple_content',
                    'verticalLayout_exploring_custom_container'
                ]
                
                for layout_name in groupbox_layouts:
                    if hasattr(self, layout_name):
                        layout = getattr(self, layout_name)
                        layout.setContentsMargins(left, top, right, bottom)
                
                # Apply to filtering/exporting value layouts
                value_layouts = [
                    'verticalLayout_filtering_values',
                    'verticalLayout_exporting_values'
                ]
                for layout_name in value_layouts:
                    if hasattr(self, layout_name):
                        layout = getattr(self, layout_name)
                        layout.setContentsMargins(left, top, right, bottom)
                
                logger.debug(f"Applied harmonized margins: {left}-{top}-{right}-{bottom}")
            
            # Apply action bar margins if available
            margins_actions = UIConfig.get_config('layout', 'margins_actions')
            if margins_actions and hasattr(self, 'frame_actions'):
                layout = self.frame_actions.layout()
                if layout:
                    layout.setContentsMargins(
                        margins_actions.get('left', 8),
                        margins_actions.get('top', 6),
                        margins_actions.get('right', 8),
                        margins_actions.get('bottom', 12)
                    )
            
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
            from qgis.PyQt.QtWidgets import QSpacerItem
            from .modules.ui_elements import get_spacer_size
            from .modules.ui_config import UIConfig, DisplayProfile
            
            # Get compact mode status from UIConfig
            is_compact = UIConfig._active_profile == DisplayProfile.COMPACT
            
            # Get dynamic spacer sizes based on active profile
            spacer_sizes = {
                'exploring': get_spacer_size('verticalSpacer_exploring_tab_top', is_compact),
                'filtering': get_spacer_size('verticalSpacer_filtering_keys_field_top', is_compact),
                'exporting': get_spacer_size('verticalSpacer_exporting_keys_field_top', is_compact)
            }
            
            spacer_width = 20  # Standard width for vertical spacers
            
            # Harmonize spacers in all three key widgets
            sections = {
                'exploring': 'widget_exploring_keys',
                'filtering': 'widget_filtering_keys',
                'exporting': 'widget_exporting_keys'
            }
            
            for section_name, widget_name in sections.items():
                # Get section-specific spacer height
                target_spacer_height = spacer_sizes.get(section_name, 4)
                
                if hasattr(self, widget_name):
                    widget = getattr(self, widget_name)
                    layout = widget.layout()
                    if layout:
                        spacer_count = 0
                        # Find the nested verticalLayout (e.g., verticalLayout_filtering_keys)
                        for i in range(layout.count()):
                            item = layout.itemAt(i)
                            if item and hasattr(item, 'layout') and item.layout():
                                nested_layout = item.layout()
                                # Iterate through nested layout items to find spacers
                                for j in range(nested_layout.count()):
                                    nested_item = nested_layout.itemAt(j)
                                    if nested_item and isinstance(nested_item, QSpacerItem):
                                        # Set section-specific spacer dimensions
                                        nested_item.changeSize(
                                            spacer_width,
                                            target_spacer_height,
                                            nested_item.sizePolicy().horizontalPolicy(),
                                            nested_item.sizePolicy().verticalPolicy()
                                        )
                                        spacer_count += 1
                        
                        if spacer_count > 0:
                            logger.debug(f"Harmonized {spacer_count} spacers in {section_name} to {target_spacer_height}px")
            
            mode_name = 'COMPACT' if is_compact else 'NORMAL'
            logger.debug(f"Applied spacer dimensions ({mode_name} mode): {spacer_sizes}")
            
        except Exception as e:
            logger.warning(f"Could not harmonize spacers: {e}")
            import traceback
            traceback.print_exc()
    
    def _apply_qgis_widget_dimensions(self):
        """
        Apply dimensions to QGIS custom widgets.
        
        Sets heights for QgsFeaturePickerWidget, QgsFieldExpressionWidget, 
        QgsProjectionSelectionWidget, and forces QgsPropertyOverrideButton to exact 22px.
        """
        try:
            from qgis.PyQt.QtWidgets import QSizePolicy
            from .modules.ui_config import UIConfig
            
            # Get dimensions from config
            combobox_height = UIConfig.get_config('combobox', 'height') or 24
            input_height = UIConfig.get_config('input', 'height') or 24
            
            # QgsFeaturePickerWidget
            for widget in self.findChildren(QgsFeaturePickerWidget):
                widget.setMinimumHeight(combobox_height)
                widget.setMaximumHeight(combobox_height)
                widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            # QgsFieldExpressionWidget
            for widget in self.findChildren(QgsFieldExpressionWidget):
                widget.setMinimumHeight(input_height)
                widget.setMaximumHeight(input_height)
                widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            # QgsProjectionSelectionWidget
            for widget in self.findChildren(QgsProjectionSelectionWidget):
                widget.setMinimumHeight(combobox_height)
                widget.setMaximumHeight(combobox_height)
                widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            # QgsMapLayerComboBox
            for widget in self.findChildren(QgsMapLayerComboBox):
                widget.setMinimumHeight(combobox_height)
                widget.setMaximumHeight(combobox_height)
                widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            # QgsFieldComboBox
            for widget in self.findChildren(QgsFieldComboBox):
                widget.setMinimumHeight(combobox_height)
                widget.setMaximumHeight(combobox_height)
                widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            # QgsCheckableComboBox (QGIS native)
            for widget in self.findChildren(QgsCheckableComboBox):
                widget.setMinimumHeight(combobox_height)
                widget.setMaximumHeight(combobox_height)
                widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            # QgsPropertyOverrideButton - FORCE to exact 22px (smaller than inputs)
            from qgis.gui import QgsPropertyOverrideButton
            for widget in self.findChildren(QgsPropertyOverrideButton):
                # Force to 22px (slightly smaller than 24px inputs for visual hierarchy)
                button_size = 22
                widget.setMinimumHeight(button_size)
                widget.setMaximumHeight(button_size)
                widget.setMinimumWidth(button_size)
                widget.setMaximumWidth(button_size)
                widget.setFixedSize(button_size, button_size)
                widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            
            logger.debug(f"Applied QGIS widget dimensions: ComboBox={combobox_height}px, Input={input_height}px")
            
        except Exception as e:
            # QGIS widgets may not support all size constraints
            logger.debug(f"Could not apply dimensions to QGIS widgets: {e}")
    
    def _align_key_layouts(self):
        """
        Align key layouts (exploring/filtering/exporting) for visual consistency.
        
        Sets consistent spacing, margins, and alignment for all key widget layouts
        and their parent containers. Harmonizes vertical bars of pushbuttons.
        """
        try:
            from .modules.ui_config import UIConfig
            
            # Get key button config for harmonized spacing
            key_button_config = UIConfig.get_config('key_button')
            button_spacing = key_button_config.get('spacing', 2) if key_button_config else 2
            
            # Get widget_keys config for container margins
            widget_keys_config = UIConfig.get_config('widget_keys')
            widget_keys_padding = widget_keys_config.get('padding', 2) if widget_keys_config else 2
            
            # Apply consistent spacing and alignment to ALL key layouts
            key_layouts = [
                ('verticalLayout_exploring_content', 'exploring content'),
                ('verticalLayout_filtering_keys', 'filtering keys'),
                ('verticalLayout_exporting_keys', 'exporting keys')
            ]
            
            for layout_name, description in key_layouts:
                if hasattr(self, layout_name):
                    layout = getattr(self, layout_name)
                    # Set consistent spacing between items (reduced for compact icons)
                    layout.setSpacing(button_spacing)
                    # Remove content margins for alignment
                    layout.setContentsMargins(0, 0, 0, 0)
                    # Center buttons vertically within their space
                    layout.setAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
                    
                    # Center each item horizontally within the layout
                    for i in range(layout.count()):
                        item = layout.itemAt(i)
                        if item and item.widget():
                            # Re-set alignment for each widget to center horizontally
                            layout.setAlignment(item.widget(), Qt.AlignHCenter)
            
            # Apply consistent styling to parent container layouts (widget_*_keys_container)
            container_layouts = [
                ('verticalLayout_exploring_container', 'exploring'),
                ('verticalLayout_filtering_keys_container', 'filtering'),
                ('verticalLayout_exporting_keys_container', 'exporting')
            ]
            
            for layout_name, section in container_layouts:
                if hasattr(self, layout_name):
                    layout = getattr(self, layout_name)
                    # Consistent minimal margins: 2px all around
                    layout.setContentsMargins(widget_keys_padding, widget_keys_padding, 
                                            widget_keys_padding, widget_keys_padding)
                    layout.setSpacing(0)
            
            # Apply consistent margins to parent horizontal/grid layouts for vertical alignment
            # This ensures exploring bar aligns with filtering/exporting bars
            parent_horizontal_layouts = [
                ('gridLayout_main_actions', 'exploring parent'),
                ('horizontalLayout_filtering_content', 'filtering parent'),
                ('horizontalLayout_exporting_content', 'exporting parent')
            ]
            
            for layout_name, description in parent_horizontal_layouts:
                if hasattr(self, layout_name):
                    layout = getattr(self, layout_name)
                    # Consistent left margin (0) to align all vertical bars
                    layout.setContentsMargins(0, 0, 0, 0)
                    layout.setSpacing(4)
            
            # Apply consistent styling to parent widget containers
            parent_widgets = [
                ('widget_exploring_keys', 'exploring'),
                ('widget_filtering_keys', 'filtering'),
                ('widget_exporting_keys', 'exporting')
            ]
            
            for widget_name, section in parent_widgets:
                if hasattr(self, widget_name):
                    widget = getattr(self, widget_name)
                    # Get widget_keys dimensions from config
                    min_width = widget_keys_config.get('min_width', 34) if widget_keys_config else 34
                    max_width = widget_keys_config.get('max_width', 40) if widget_keys_config else 40
                    widget.setMinimumWidth(min_width)
                    widget.setMaximumWidth(max_width)
                    
                    parent_layout = widget.layout()
                    if parent_layout:
                        # Minimal horizontal margins, consistent vertical margins
                        parent_layout.setContentsMargins(widget_keys_padding, widget_keys_padding, 
                                                        widget_keys_padding, widget_keys_padding)
                        # Center content
                        parent_layout.setAlignment(Qt.AlignCenter)
            
            # Apply consistent spacing to content layouts (groupboxes for exploring, values for filtering/exporting)
            # This ensures vertical alignment between the exploring groupboxes and filtering/exporting widgets
            content_layouts = [
                ('verticalLayout_exploring_tabs_content', 'exploring groupboxes'),
                ('verticalLayout_filtering_values', 'filtering values'),
                ('verticalLayout_exporting_values', 'exporting values')
            ]
            
            content_spacing = 4  # Consistent spacing between content items
            for layout_name, description in content_layouts:
                if hasattr(self, layout_name):
                    layout = getattr(self, layout_name)
                    layout.setSpacing(content_spacing)
                    # Consistent margins for all content layouts
                    layout.setContentsMargins(0, 0, 0, 0)
            
            # Reduce padding on filtering and exporting main layouts to match exploring
            # These are the top-level horizontal layouts inside the toolbox pages
            main_page_layouts = [
                ('horizontalLayout_filtering_main', 'filtering main'),
                ('horizontalLayout_exporting_main', 'exporting main')
            ]
            
            for layout_name, description in main_page_layouts:
                if hasattr(self, layout_name):
                    layout = getattr(self, layout_name)
                    # Match the exploring section margins (2px all around)
                    layout.setContentsMargins(2, 2, 2, 2)
                    layout.setSpacing(4)
            
            logger.debug(f"Aligned key layouts with {button_spacing}px spacing, {widget_keys_padding}px padding")
            
        except Exception as e:
            logger.warning(f"Could not align key layouts: {e}")
            import traceback
            traceback.print_exc()
    
    def _adjust_row_spacing(self):
        """
        Adjust row spacing in filtering and exporting value layouts.
        
        Synchronizes spacer heights between key and value layouts for proper
        horizontal alignment of widgets across columns.
        """
        try:
            from qgis.PyQt.QtWidgets import QSpacerItem
            from .modules.ui_elements import get_spacer_size
            from .modules.ui_config import UIConfig, DisplayProfile
            
            # Get compact mode status and spacer sizes
            is_compact = UIConfig._active_profile == DisplayProfile.COMPACT
            layout_spacing = UIConfig.get_config('layout', 'spacing_frame') or 4
            
            spacer_sizes = {
                'filtering': get_spacer_size('verticalSpacer_filtering_keys_field_top', is_compact),
                'exporting': get_spacer_size('verticalSpacer_exporting_keys_field_top', is_compact)
            }
            
            # Adjust spacers in filtering values layout to match keys layout
            if hasattr(self, 'verticalLayout_filtering_values'):
                values_layout = self.verticalLayout_filtering_values
                spacer_target_height = spacer_sizes.get('filtering', 4)
                
                for i in range(values_layout.count()):
                    item = values_layout.itemAt(i)
                    if item and isinstance(item, QSpacerItem):
                        # Adjust spacer to target height for alignment
                        item.changeSize(
                            item.sizeHint().width(),
                            spacer_target_height,
                            item.sizePolicy().horizontalPolicy(),
                            item.sizePolicy().verticalPolicy()
                        )
                
                # Set spacing to match keys layout
                self.verticalLayout_filtering_values.setSpacing(layout_spacing)
            
            # Adjust spacers in exporting values layout to match keys layout
            if hasattr(self, 'verticalLayout_exporting_values'):
                values_layout = self.verticalLayout_exporting_values
                spacer_target_height = spacer_sizes.get('exporting', 4)
                
                for i in range(values_layout.count()):
                    item = values_layout.itemAt(i)
                    if item and isinstance(item, QSpacerItem):
                        # Adjust spacer to target height for alignment
                        item.changeSize(
                            item.sizeHint().width(),
                            spacer_target_height,
                            item.sizePolicy().horizontalPolicy(),
                            item.sizePolicy().verticalPolicy()
                        )
                
                # Set spacing to match keys layout
                self.verticalLayout_exporting_values.setSpacing(layout_spacing)
            
            logger.debug(f"Adjusted row spacing: filtering/exporting aligned with {layout_spacing}px spacing")
            
        except Exception as e:
            logger.warning(f"Could not adjust row spacing: {e}")
            import traceback
            traceback.print_exc()

    def _setup_backend_indicator(self):
        """
        Create and configure header bar with plugin title, favorites indicator, and backend indicator.
        
        Sets up a header bar at the top of the plugin with:
        - Favorites indicator badge (★ count) aligned right (before backend)
        - Backend indicator badge (PostgreSQL/Spatialite/OGR) aligned right
        """
        # Create header frame container
        self.frame_header = QtWidgets.QFrame(self.dockWidgetContents)
        self.frame_header.setObjectName("frame_header")
        self.frame_header.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.frame_header.setMaximumHeight(22)
        self.frame_header.setMinimumHeight(18)
        
        # Header layout - compact (favorites + backend indicators)
        header_layout = QtWidgets.QHBoxLayout(self.frame_header)
        header_layout.setContentsMargins(10, 1, 10, 1)
        header_layout.setSpacing(8)
        
        # Expanding spacer before indicators (pushes indicators to right)
        header_layout.addSpacerItem(QtWidgets.QSpacerItem(40, 10, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))
        
        # Keep title label reference for compatibility but don't add to layout
        self.plugin_title_label = None
        
        # === FAVORITES INDICATOR (left of backend indicator) ===
        self.favorites_indicator_label = QtWidgets.QLabel(self.frame_header)
        self.favorites_indicator_label.setObjectName("label_favorites_indicator")
        self.favorites_indicator_label.setText("★")
        
        # Modern badge style - gold/amber color for favorites
        self.favorites_indicator_label.setStyleSheet("""
            QLabel#label_favorites_indicator {
                color: white;
                font-size: 9pt;
                font-weight: 600;
                padding: 3px 10px;
                border-radius: 12px;
                border: none;
                background-color: #f39c12;
            }
            QLabel#label_favorites_indicator:hover {
                background-color: #d68910;
                cursor: pointer;
            }
        """)
        self.favorites_indicator_label.setAlignment(Qt.AlignCenter)
        self.favorites_indicator_label.setMinimumWidth(35)
        self.favorites_indicator_label.setMaximumHeight(20)
        
        # Make clickable for favorites menu
        self.favorites_indicator_label.setCursor(Qt.PointingHandCursor)
        self.favorites_indicator_label.setToolTip("★ Favorites\nClick to manage filter favorites")
        self.favorites_indicator_label.mousePressEvent = self._on_favorite_indicator_clicked
        
        header_layout.addWidget(self.favorites_indicator_label)
        
        # === BACKEND INDICATOR (right) ===
        self.backend_indicator_label = QtWidgets.QLabel(self.frame_header)
        self.backend_indicator_label.setObjectName("label_backend_indicator")
        
        # Display waiting message if no layers loaded
        if self.has_loaded_layers:
            self.backend_indicator_label.setText("OGR")
        else:
            self.backend_indicator_label.setText("...")
        
        # Modern badge style matching _update_backend_indicator design (OGR style as default)
        self.backend_indicator_label.setStyleSheet("""
            QLabel#label_backend_indicator {
                color: white;
                font-size: 9pt;
                font-weight: 600;
                padding: 3px 10px;
                border-radius: 12px;
                border: none;
                background-color: #3498db;
            }
            QLabel#label_backend_indicator:hover {
                background-color: #2980b9;
                cursor: pointer;
            }
        """)
        self.backend_indicator_label.setAlignment(Qt.AlignCenter)
        self.backend_indicator_label.setMinimumWidth(40)
        self.backend_indicator_label.setMaximumHeight(20)
        
        # Make clickable for backend selection
        self.backend_indicator_label.setCursor(Qt.PointingHandCursor)
        self.backend_indicator_label.setToolTip("Click to change backend\n(When '...' is shown: click to reload layers)")
        self.backend_indicator_label.mousePressEvent = self._on_backend_indicator_clicked
        
        # Initialize backend preference storage
        self.forced_backends = {}  # layer_id -> forced_backend_type
        
        header_layout.addWidget(self.backend_indicator_label)
        
        # Insert header frame at the top of verticalLayout_8 (main container)
        if hasattr(self, 'verticalLayout_8'):
            self.verticalLayout_8.insertWidget(0, self.frame_header)
            logger.debug("Header bar inserted at top with favorites and backend indicators")
    
    def _on_backend_indicator_clicked(self, event):
        """
        Handle click on backend indicator to show backend selection menu.
        Allows user to force a specific backend for the current layer.
        
        NEW: If indicator shows "..." (no layers loaded), clicking triggers
        a force reload of layers instead of showing the backend menu.
        """
        from qgis.PyQt.QtWidgets import QMenu
        from qgis.PyQt.QtGui import QCursor
        from .modules.appUtils import POSTGRESQL_AVAILABLE
        from .modules.constants import PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR
        
        # NEW: If indicator shows "..." (waiting state), trigger reload instead
        if hasattr(self, 'backend_indicator_label') and self.backend_indicator_label:
            current_text = self.backend_indicator_label.text()
            if current_text == "..." or current_text == "⟳":
                logger.info("Backend indicator clicked while in waiting state - triggering reload")
                self._trigger_reload_layers()
                return
        
        current_layer = self.current_layer
        if not current_layer:
            # No current layer - trigger reload as fallback
            logger.info("Backend indicator clicked with no current layer - triggering reload")
            self._trigger_reload_layers()
            return
        
        # Get available backends for this layer
        available_backends = self._get_available_backends_for_layer(current_layer)
        
        if not available_backends:
            show_warning("FilterMate", "No alternative backends available for this layer")
            return
        
        # Create context menu
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #cccccc;
                padding: 5px;
            }
            QMenu::item {
                padding: 5px 20px;
            }
            QMenu::item:selected {
                background-color: #3498db;
                color: white;
            }
        """)
        
        # Add header
        header = menu.addAction("Select Backend:")
        header.setEnabled(False)
        menu.addSeparator()
        
        # Add available backends
        current_forced = self.forced_backends.get(current_layer.id())
        
        for backend_type, backend_name, backend_icon in available_backends:
            action_text = f"{backend_icon} {backend_name}"
            if current_forced == backend_type:
                action_text += " ✓"
            action = menu.addAction(action_text)
            action.setData(backend_type)
        
        menu.addSeparator()
        
        # Add "Auto" option (remove forced backend)
        auto_action = menu.addAction("⚙️ Auto (Default)")
        auto_action.setData(None)
        if not current_forced:
            auto_action.setText(auto_action.text() + " ✓")
        
        menu.addSeparator()
        
        # Add "Auto-select All" option
        auto_all_action = menu.addAction("🎯 Auto-select Optimal for All Layers")
        auto_all_action.setData('__AUTO_ALL__')
        
        # Add "Force All Layers" option - force current backend for all layers
        menu.addSeparator()
        # Detect current backend (forced or auto-detected)
        current_backend = self._detect_current_backend(current_layer)
        backend_name = current_backend.upper() if current_backend else "CURRENT"
        force_all_text = f"🔒 Force {backend_name} for All Layers"
        force_all_tooltip = f"Force all layers to use {backend_name} backend"
        
        force_all_action = menu.addAction(force_all_text)
        force_all_action.setData('__FORCE_ALL__')
        force_all_action.setToolTip(force_all_tooltip)
        
        # Add PostgreSQL maintenance section if PostgreSQL is available
        if POSTGRESQL_AVAILABLE:
            menu.addSeparator()
            
            # PostgreSQL maintenance submenu
            pg_submenu = menu.addMenu("🐘 PostgreSQL Maintenance")
            
            # Auto cleanup toggle
            auto_cleanup_enabled = getattr(self, '_pg_auto_cleanup_enabled', True)
            cleanup_toggle_text = "✓ Auto-cleanup session views" if auto_cleanup_enabled else "  Auto-cleanup session views"
            cleanup_toggle_action = pg_submenu.addAction(cleanup_toggle_text)
            cleanup_toggle_action.setData('__PG_TOGGLE_CLEANUP__')
            cleanup_toggle_action.setToolTip("Automatically drop materialized views when plugin unloads")
            
            pg_submenu.addSeparator()
            
            # Manual cleanup current session
            cleanup_session_action = pg_submenu.addAction("🧹 Cleanup my session views now")
            cleanup_session_action.setData('__PG_CLEANUP_SESSION__')
            cleanup_session_action.setToolTip("Drop all materialized views created by this session")
            
            # Cleanup schema if no other sessions
            cleanup_schema_action = pg_submenu.addAction("🗑️ Cleanup schema (if no other sessions)")
            cleanup_schema_action.setData('__PG_CLEANUP_SCHEMA__')
            cleanup_schema_action.setToolTip("Drop the filter_mate_temp schema if no other clients are using it")
            
            pg_submenu.addSeparator()
            
            # Show session info
            session_info_action = pg_submenu.addAction("ℹ️ Show session info")
            session_info_action.setData('__PG_SESSION_INFO__')
        
        # Show menu and handle selection
        selected_action = menu.exec_(QCursor.pos())
        
        if selected_action:
            selected_backend = selected_action.data()
            
            # Handle "Auto-select All" special action
            if selected_backend == '__AUTO_ALL__':
                self.auto_select_optimal_backends()
                return
            
            # Handle "Force All Layers" special action
            if selected_backend == '__FORCE_ALL__':
                # Use detected backend (which may be forced or auto-detected)
                backend_to_force = self._detect_current_backend(current_layer)
                self._force_backend_for_all_layers(backend_to_force)
                return
            
            # Handle PostgreSQL maintenance actions
            if selected_backend == '__PG_TOGGLE_CLEANUP__':
                self._toggle_pg_auto_cleanup()
                return
            
            if selected_backend == '__PG_CLEANUP_SESSION__':
                self._cleanup_postgresql_session_views()
                return
            
            if selected_backend == '__PG_CLEANUP_SCHEMA__':
                self._cleanup_postgresql_schema_if_empty()
                return
            
            if selected_backend == '__PG_SESSION_INFO__':
                self._show_postgresql_session_info()
                return
            
            self._set_forced_backend(current_layer.id(), selected_backend)
            
            # Update indicator to reflect change
            if selected_backend:
                self._update_backend_indicator(self._current_provider_type, 
                                              self._current_postgresql_available,
                                              actual_backend=selected_backend)
                show_success("FilterMate", f"Backend forced to {selected_backend.upper()} for layer '{current_layer.name()}'")
            else:
                # Reset to auto - no forced backend
                self._update_backend_indicator(self._current_provider_type, 
                                              self._current_postgresql_available,
                                              actual_backend=None)
                show_info("FilterMate", f"Backend set to Auto for layer '{current_layer.name()}'")
    

    # ========================================
    # FAVORITES INDICATOR METHODS
    # ========================================
    
    def _on_favorite_indicator_clicked(self, event):
        """
        Handle click on favorites indicator to show favorites menu.
        Allows user to:
        - Add current filter as favorite
        - Apply a saved favorite
        - Manage favorites (edit, delete)
        """
        from qgis.PyQt.QtWidgets import QMenu, QInputDialog, QMessageBox
        from qgis.PyQt.QtGui import QCursor
        from qgis.core import QgsExpressionContextUtils
        
        # Get favorites manager from app (will be initialized there)
        favorites_manager = getattr(self, '_favorites_manager', None)
        if favorites_manager is None:
            # Create temporary manager if not yet initialized
            from .modules.filter_favorites import FavoritesManager
            self._favorites_manager = FavoritesManager()
            
            # Try to get database path and project UUID from project variables
            if self.PROJECT:
                scope = QgsExpressionContextUtils.projectScope(self.PROJECT)
                project_uuid = scope.variable('filterMate_db_project_uuid')
                if project_uuid:
                    # Construct db path from config
                    from .config.config import ENV_VARS
                    import os
                    db_path = os.path.normpath(ENV_VARS.get("PLUGIN_CONFIG_DIRECTORY", "") + os.sep + 'filterMate_db.sqlite')
                    if os.path.exists(db_path):
                        self._favorites_manager.set_database(db_path, str(project_uuid))
            
            self._favorites_manager.load_from_project()
            favorites_manager = self._favorites_manager
        
        # Create context menu
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #cccccc;
                padding: 5px;
            }
            QMenu::item {
                padding: 5px 20px;
            }
            QMenu::item:selected {
                background-color: #f39c12;
                color: white;
            }
            QMenu::separator {
                height: 1px;
                background-color: #cccccc;
                margin: 3px 10px;
            }
        """)
        
        # === ADD TO FAVORITES ===
        add_action = menu.addAction("⭐ Add Current Filter to Favorites")
        add_action.setData('__ADD_FAVORITE__')
        
        # Check if there's an expression to save
        current_expression = self._get_current_filter_expression()
        if not current_expression:
            add_action.setEnabled(False)
            add_action.setText("⭐ Add Current Filter (no filter active)")
        
        menu.addSeparator()
        
        # === FAVORITES LIST ===
        favorites = favorites_manager.get_all_favorites()
        
        if favorites:
            # Add header
            header = menu.addAction(f"📋 Saved Favorites ({len(favorites)})")
            header.setEnabled(False)
            
            # Show recent/most used first (up to 10)
            recent_favs = favorites_manager.get_recent_favorites(limit=10)
            for fav in recent_favs:
                # Build display text with layers count
                layers_count = fav.get_layers_count() if hasattr(fav, 'get_layers_count') else 1
                fav_text = f"  ★ {fav.get_display_name(25)}"
                if layers_count > 1:
                    fav_text += f" [{layers_count}]"
                if fav.use_count > 0:
                    fav_text += f" ({fav.use_count}×)"
                action = menu.addAction(fav_text)
                action.setData(('apply', fav.id))
                # Build tooltip with layer details
                tooltip = fav.get_preview(80)
                if fav.remote_layers:
                    tooltip += f"\n\nLayers ({layers_count}):\n• {fav.layer_name or 'Source'}"
                    for remote_name in list(fav.remote_layers.keys())[:5]:
                        tooltip += f"\n• {remote_name}"
                    if len(fav.remote_layers) > 5:
                        tooltip += f"\n... and {len(fav.remote_layers) - 5} more"
                action.setToolTip(tooltip)
            
            # Show "More..." if there are more favorites
            if len(favorites) > 10:
                more_action = menu.addAction(f"  ... {len(favorites) - 10} more favorites")
                more_action.setData('__SHOW_ALL__')
        else:
            no_favs = menu.addAction("(No favorites saved)")
            no_favs.setEnabled(False)
        
        menu.addSeparator()
        
        # === MANAGEMENT OPTIONS ===
        manage_action = menu.addAction("⚙️ Manage Favorites...")
        manage_action.setData('__MANAGE__')
        
        export_action = menu.addAction("📤 Export Favorites...")
        export_action.setData('__EXPORT__')
        
        import_action = menu.addAction("📥 Import Favorites...")
        import_action.setData('__IMPORT__')
        
        # Show menu and handle selection
        selected_action = menu.exec_(QCursor.pos())
        
        if selected_action:
            action_data = selected_action.data()
            
            if action_data == '__ADD_FAVORITE__':
                self._add_current_to_favorites()
            elif action_data == '__MANAGE__':
                self._show_favorites_manager_dialog()
            elif action_data == '__EXPORT__':
                self._export_favorites()
            elif action_data == '__IMPORT__':
                self._import_favorites()
            elif action_data == '__SHOW_ALL__':
                self._show_favorites_manager_dialog()
            elif isinstance(action_data, tuple) and action_data[0] == 'apply':
                self._apply_favorite(action_data[1])
    
    def _get_current_filter_expression(self) -> str:
        """
        Get the current filter expression.
        
        Tries multiple sources in order:
        1. Expression widget (if exists and has content)
        2. Current layer's subsetString (the actual applied filter)
        3. Source layer from combobox's subsetString
        
        Returns:
            str: The current filter expression, or empty string if none
        """
        try:
            # Source 1: Try to get expression from the expression widget
            if hasattr(self, 'mQgsFieldExpressionWidget_filtering_active_expression'):
                widget = self.mQgsFieldExpressionWidget_filtering_active_expression
                if hasattr(widget, 'expression'):
                    expr = widget.expression()
                    if expr and expr.strip():
                        return expr
                elif hasattr(widget, 'currentText'):
                    expr = widget.currentText()
                    if expr and expr.strip():
                        return expr
            
            # Source 2: Try to get subsetString from current layer
            if hasattr(self, 'current_layer') and self.current_layer:
                subset = self.current_layer.subsetString()
                if subset and subset.strip():
                    return subset
            
            # Source 3: Try to get from the filtering source layer combobox
            if hasattr(self, 'comboBox_filtering_current_layer'):
                layer = self.comboBox_filtering_current_layer.currentLayer()
                if layer:
                    subset = layer.subsetString()
                    if subset and subset.strip():
                        return subset
            
            return ""
        except Exception as e:
            logger.debug(f"Could not get current expression: {e}")
            return ""
    
    def _add_current_to_favorites(self):
        """Add current filter configuration to favorites, including all filtered remote layers."""
        from qgis.PyQt.QtWidgets import QInputDialog, QLineEdit, QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox, QTextEdit
        from qgis.core import QgsProject
        from datetime import datetime
        from .modules.filter_favorites import FilterFavorite
        
        expression = self._get_current_filter_expression()
        if not expression:
            show_warning("FilterMate", "No active filter to save as favorite")
            return
        
        # Collect all filtered layers (remote layers with active filters)
        remote_layers_data = {}
        project = QgsProject.instance()
        source_layer_id = None
        source_layer_name = None
        
        if hasattr(self, 'current_layer') and self.current_layer:
            source_layer_id = self.current_layer.id()
            source_layer_name = self.current_layer.name()
        
        # Iterate through all vector layers to find those with filters
        for layer_id, layer in project.mapLayers().items():
            # Skip non-vector layers
            if not hasattr(layer, 'subsetString'):
                continue
            # Skip the source layer (already captured in main expression)
            if layer_id == source_layer_id:
                continue
            # Check if layer has an active filter
            subset = layer.subsetString()
            if subset and subset.strip():
                remote_layers_data[layer.name()] = {
                    'expression': subset,
                    'feature_count': layer.featureCount(),
                    'layer_id': layer_id,
                    'provider': layer.providerType()
                }
        
        # Build default name and auto-description
        layers_count = 1 + len(remote_layers_data)
        default_name = ""
        if layers_count > 1:
            default_name = f"Filter ({layers_count} layers)"
        
        # Generate auto-description
        auto_description = self._generate_favorite_description(
            source_layer_name, expression, remote_layers_data
        )
        
        # Create custom dialog for name + description
        dialog = QDialog(self)
        dialog.setWindowTitle("FilterMate - Add to Favorites")
        dialog.setMinimumSize(380, 200)
        dialog.resize(420, 260)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        form_layout = QFormLayout()
        
        # Name input
        name_edit = QLineEdit()
        name_edit.setText(default_name)
        name_edit.setPlaceholderText("Enter a name for this filter")
        form_layout.addRow(f"Name ({layers_count} layer{'s' if layers_count > 1 else ''}):", name_edit)
        
        # Description input (auto-generated but editable)
        desc_edit = QTextEdit()
        desc_edit.setMaximumHeight(120)
        desc_edit.setText(auto_description)
        desc_edit.setPlaceholderText("Description (auto-generated, you can modify it)")
        form_layout.addRow("Description:", desc_edit)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec_() == QDialog.Accepted:
            name = name_edit.text().strip()
            description = desc_edit.toPlainText().strip()
            
            if name:
                # Get current layer info
                layer_name = None
                layer_provider = None
                if hasattr(self, 'current_layer') and self.current_layer:
                    layer_name = self.current_layer.name()
                    layer_provider = self.current_layer.providerType()
                
                # Create favorite with remote layers and description
                fav = FilterFavorite(
                    name=name,
                    expression=expression,
                    layer_name=layer_name,
                    layer_provider=layer_provider,
                    remote_layers=remote_layers_data if remote_layers_data else None,
                    description=description
                )
                
                # Add to manager
                self._favorites_manager.add_favorite(fav)
                self._favorites_manager.save_to_project()
                
                # Update indicator
                self._update_favorite_indicator()
                
                msg = f"Filter saved as '{name}'"
                if remote_layers_data:
                    msg += f" ({len(remote_layers_data) + 1} layers)"
                show_success("FilterMate", msg)
    
    def _generate_favorite_description(self, source_layer_name: str, expression: str, 
                                        remote_layers: dict) -> str:
        """
        Generate an automatic description for a favorite.
        
        Args:
            source_layer_name: Name of the source layer
            expression: Filter expression
            remote_layers: Dict of remote layers data
            
        Returns:
            str: Auto-generated description
        """
        from datetime import datetime
        
        lines = []
        
        # Add date
        lines.append(f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        
        # Source layer info
        if source_layer_name:
            lines.append(f"Source: {source_layer_name}")
            # Extract key info from expression (first condition or truncated)
            expr_preview = expression[:100] + "..." if len(expression) > 100 else expression
            lines.append(f"Filter: {expr_preview}")
        
        # Remote layers summary
        if remote_layers:
            lines.append("")
            lines.append(f"Remote layers ({len(remote_layers)}):")
            for layer_name, data in list(remote_layers.items())[:5]:
                feature_count = data.get('feature_count', '?')
                lines.append(f"  • {layer_name} ({feature_count} features)")
            if len(remote_layers) > 5:
                lines.append(f"  ... and {len(remote_layers) - 5} more")
        
        return "\n".join(lines)
    
    def _apply_favorite(self, favorite_id: str):
        """Apply a saved favorite filter to all layers (source + remote)."""
        from qgis.core import QgsProject
        
        fav = self._favorites_manager.get_favorite(favorite_id)
        if not fav:
            show_warning("FilterMate", "Favorite not found")
            return
        
        project = QgsProject.instance()
        applied_count = 0
        errors = []
        
        # Try to find and apply filter to source layer by name
        source_layer = None
        if fav.layer_name:
            matching_layers = project.mapLayersByName(fav.layer_name)
            if matching_layers:
                source_layer = matching_layers[0]
        
        # Apply filter to source layer
        if source_layer and fav.expression:
            try:
                source_layer.setSubsetString(fav.expression)
                applied_count += 1
                logger.info(f"Applied filter to source layer: {source_layer.name()}")
            except Exception as e:
                errors.append(f"{fav.layer_name}: {str(e)}")
                logger.error(f"Failed to apply filter to {fav.layer_name}: {e}")
        elif fav.expression:
            # If source layer not found, try to apply to current layer
            if hasattr(self, 'current_layer') and self.current_layer:
                try:
                    self.current_layer.setSubsetString(fav.expression)
                    applied_count += 1
                    logger.info(f"Applied filter to current layer: {self.current_layer.name()}")
                except Exception as e:
                    errors.append(f"Current layer: {str(e)}")
        
        # Apply filters to remote layers
        if fav.remote_layers:
            for layer_name, layer_data in fav.remote_layers.items():
                expression = layer_data.get('expression', '')
                if not expression:
                    continue
                
                # Find layer by name
                matching_layers = project.mapLayersByName(layer_name)
                if matching_layers:
                    layer = matching_layers[0]
                    try:
                        layer.setSubsetString(expression)
                        applied_count += 1
                        logger.info(f"Applied filter to remote layer: {layer_name}")
                    except Exception as e:
                        errors.append(f"{layer_name}: {str(e)}")
                        logger.error(f"Failed to apply filter to {layer_name}: {e}")
                else:
                    logger.warning(f"Layer not found in project: {layer_name}")
        
        # Zoom to filtered source layer extent (using actual filtered extent, not cached)
        # Always zoom when loading a favorite for better UX
        target_layer = source_layer if source_layer else (self.current_layer if hasattr(self, 'current_layer') else None)
        
        try:
            from qgis.utils import iface
            
            if target_layer and target_layer.featureCount() > 0:
                # Force update extents after filter application
                target_layer.updateExtents()
                
                # Use get_filtered_layer_extent for accurate bounding box of filtered features
                extent = self.get_filtered_layer_extent(target_layer)
                
                if extent and not extent.isEmpty():
                    iface.mapCanvas().zoomToFeatureExtent(extent)
                    logger.info(f"Zoomed to filtered extent of layer: {target_layer.name()}")
                else:
                    iface.mapCanvas().refresh()
            else:
                # Just refresh if no features match the filter
                iface.mapCanvas().refresh()
                if target_layer:
                    logger.debug(f"Canvas refreshed (no features match filter)")
        except Exception as e:
            logger.warning(f"Could not zoom to filtered extent: {e}")
            try:
                iface.mapCanvas().refresh()
            except:
                pass
        
        # Update usage stats
        self._favorites_manager.mark_favorite_used(favorite_id)
        self._favorites_manager.save_to_project()
        
        # Update indicator
        self._update_favorite_indicator()
        
        # Show result
        if errors:
            show_warning("FilterMate", f"Applied filter to {applied_count} layers. Errors: {len(errors)}")
        else:
            total_layers = fav.get_layers_count() if hasattr(fav, 'get_layers_count') else applied_count
            if applied_count > 1:
                show_success("FilterMate", f"Applied '{fav.name}' to {applied_count} layers")
            else:
                show_success("FilterMate", f"Applied filter: {fav.name}")
    
    def _show_favorites_manager_dialog(self):
        """Show the favorites management dialog with list, edit, delete, and search capabilities."""
        from qgis.PyQt.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
            QPushButton, QLabel, QLineEdit, QTextEdit, QMessageBox, QMenu,
            QGroupBox, QFormLayout, QDialogButtonBox, QSplitter, QTreeWidget,
            QTreeWidgetItem, QHeaderView, QTabWidget, QWidget, QScrollArea,
            QCompleter
        )
        from qgis.PyQt.QtCore import Qt, QStringListModel
        from qgis.PyQt.QtGui import QFont, QColor
        
        if not self._favorites_manager or self._favorites_manager.count == 0:
            QMessageBox.information(
                self,
                "Favorites Manager",
                "No favorites saved yet.\n\nClick the ★ indicator and select 'Add current filter to favorites' to save your first favorite."
            )
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("FilterMate - Favorites Manager")
        dialog.setMinimumSize(550, 400)
        dialog.resize(650, 480)
        dialog.setModal(True)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # Header with search
        header_layout = QHBoxLayout()
        header_label = QLabel(f"<b>Saved Favorites ({self._favorites_manager.count})</b>")
        header_label.setStyleSheet("font-size: 11pt; margin-bottom: 5px;")
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Search box for filtering favorites
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍")
        search_label.setStyleSheet("font-size: 12pt;")
        search_layout.addWidget(search_label)
        
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("Search by name, expression, tags, or description...")
        search_edit.setClearButtonEnabled(True)
        search_edit.setStyleSheet("padding: 4px 8px; border-radius: 4px;")
        search_layout.addWidget(search_edit)
        layout.addLayout(search_layout)
        
        # Main content with splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel: List of favorites
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        list_widget = QListWidget()
        list_widget.setMinimumWidth(180)
        list_widget.setMaximumWidth(250)
        list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        
        # Store all favorites for search filtering
        all_favorites = self._favorites_manager.get_all_favorites()
        
        def populate_list(favorites_to_show):
            """Populate list widget with given favorites."""
            list_widget.clear()
            for fav in favorites_to_show:
                layers_count = fav.get_layers_count() if hasattr(fav, 'get_layers_count') else 1
                item_text = f"★ {fav.name}"
                if layers_count > 1:
                    item_text += f" [{layers_count}]"
                # Show tags in item if any
                if fav.tags:
                    item_text += f" 🏷️"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, fav.id)
                tooltip = f"Layer: {fav.layer_name}\nUsed: {fav.use_count} times"
                if fav.tags:
                    tooltip += f"\nTags: {', '.join(fav.tags)}"
                if fav.description:
                    tooltip += f"\n\n{fav.description}"
                item.setToolTip(tooltip)
                list_widget.addItem(item)
        
        def on_search_changed(text):
            """Filter favorites based on search text."""
            if not text.strip():
                populate_list(all_favorites)
            else:
                filtered = self._favorites_manager.search_favorites(text)
                populate_list(filtered)
                # Update header with filtered count
                header_label.setText(f"<b>Favorites ({len(filtered)}/{self._favorites_manager.count})</b>")
        
        search_edit.textChanged.connect(on_search_changed)
        
        # Initial population
        populate_list(all_favorites)
        
        left_layout.addWidget(list_widget)
        splitter.addWidget(left_panel)
        
        # Right panel: Details with tabs
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        # Tab widget for details
        tab_widget = QTabWidget()
        
        # === TAB 1: General Info ===
        general_tab = QWidget()
        general_layout = QFormLayout(general_tab)
        general_layout.setContentsMargins(8, 8, 8, 8)
        general_layout.setSpacing(6)
        general_layout.setRowWrapPolicy(QFormLayout.DontWrapRows)
        
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("Favorite name")
        general_layout.addRow("Name:", name_edit)
        
        description_edit = QTextEdit()
        description_edit.setMaximumHeight(60)
        description_edit.setPlaceholderText("Description (auto-generated, editable)")
        general_layout.addRow("Description:", description_edit)
        
        # Tags editing field
        tags_edit = QLineEdit()
        tags_edit.setPlaceholderText("Enter tags separated by commas (e.g., urban, population, 2024)")
        tags_edit.setToolTip("Tags help organize and search favorites.\nSeparate multiple tags with commas.")
        general_layout.addRow("Tags:", tags_edit)
        
        layer_label = QLabel("-")
        layer_label.setStyleSheet("color: #555;")
        layer_label.setWordWrap(True)
        general_layout.addRow("Source Layer:", layer_label)
        
        provider_label = QLabel("-")
        provider_label.setStyleSheet("color: #777;")
        general_layout.addRow("Provider:", provider_label)
        
        # Stats row
        stats_layout = QHBoxLayout()
        stats_layout.setContentsMargins(0, 0, 0, 0)
        use_count_label = QLabel("-")
        created_label = QLabel("-")
        created_label.setStyleSheet("color: #777; font-size: 9pt;")
        stats_layout.addWidget(QLabel("Used:"))
        stats_layout.addWidget(use_count_label)
        stats_layout.addStretch()
        stats_layout.addWidget(QLabel("Created:"))
        stats_layout.addWidget(created_label)
        general_layout.addRow(stats_layout)
        
        tab_widget.addTab(general_tab, "📋 General")
        
        # === TAB 2: Source Expression ===
        expr_tab = QWidget()
        expr_layout = QVBoxLayout(expr_tab)
        expr_layout.setContentsMargins(8, 8, 8, 8)
        expr_layout.setSpacing(4)
        
        source_expr_label = QLabel("<b>Source Layer Expression:</b>")
        expr_layout.addWidget(source_expr_label)
        
        expression_edit = QTextEdit()
        expression_edit.setPlaceholderText("Filter expression for source layer")
        expression_edit.setStyleSheet("font-family: monospace; font-size: 10pt;")
        expr_layout.addWidget(expression_edit)
        
        tab_widget.addTab(expr_tab, "🔍 Expression")
        
        # === TAB 3: Remote Layers ===
        remote_tab = QWidget()
        remote_layout = QVBoxLayout(remote_tab)
        remote_layout.setContentsMargins(8, 8, 8, 8)
        remote_layout.setSpacing(4)
        
        remote_header = QLabel("<b>Filtered Remote Layers:</b>")
        remote_layout.addWidget(remote_header)
        
        remote_tree = QTreeWidget()
        remote_tree.setHeaderLabels(["Layer", "Features", "Expression"])
        remote_tree.setColumnCount(3)
        remote_tree.header().setStretchLastSection(True)
        remote_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        remote_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        remote_tree.setAlternatingRowColors(True)
        remote_layout.addWidget(remote_tree)
        
        no_remote_label = QLabel("<i>No remote layers in this favorite</i>")
        no_remote_label.setStyleSheet("color: #888; padding: 10px;")
        no_remote_label.setAlignment(Qt.AlignCenter)
        remote_layout.addWidget(no_remote_label)
        
        tab_widget.addTab(remote_tab, "🗂️ Remote Layers")
        
        right_layout.addWidget(tab_widget)
        splitter.addWidget(right_panel)
        
        # Set splitter proportions (30% list, 70% details)
        splitter.setSizes([200, 450])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)  # Stretch factor for splitter
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 8, 0, 0)
        
        apply_btn = QPushButton("▶ Apply")
        apply_btn.setEnabled(False)
        apply_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 6px 12px;")
        
        save_btn = QPushButton("💾 Save Changes")
        save_btn.setEnabled(False)
        save_btn.setStyleSheet("padding: 6px 12px;")
        
        delete_btn = QPushButton("🗑️ Delete")
        delete_btn.setEnabled(False)
        delete_btn.setStyleSheet("background-color: #e74c3c; color: white; padding: 6px 12px;")
        
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("padding: 6px 12px;")
        
        button_layout.addWidget(apply_btn)
        button_layout.addWidget(save_btn)
        button_layout.addStretch()
        button_layout.addWidget(delete_btn)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
        
        # Store current favorite id
        current_fav_id = [None]
        
        def on_selection_changed():
            item = list_widget.currentItem()
            if item:
                fav_id = item.data(Qt.UserRole)
                fav = self._favorites_manager.get_favorite(fav_id)
                if fav:
                    current_fav_id[0] = fav_id
                    name_edit.setText(fav.name)
                    description_edit.setText(fav.description or "")
                    # Load tags as comma-separated string
                    tags_edit.setText(", ".join(fav.tags) if fav.tags else "")
                    layer_label.setText(fav.layer_name or "-")
                    provider_label.setText(fav.layer_provider or "-")
                    expression_edit.setText(fav.expression)
                    use_count_label.setText(f"{fav.use_count} times")
                    created_label.setText(fav.created_at[:16] if fav.created_at else "-")
                    
                    # Populate remote layers tree
                    remote_tree.clear()
                    if fav.remote_layers and len(fav.remote_layers) > 0:
                        no_remote_label.hide()
                        remote_tree.show()
                        for layer_name, layer_data in fav.remote_layers.items():
                            expr = layer_data.get('expression', '')
                            feature_count = layer_data.get('feature_count', '?')
                            item = QTreeWidgetItem([
                                layer_name,
                                str(feature_count),
                                expr[:80] + "..." if len(expr) > 80 else expr
                            ])
                            item.setToolTip(2, expr)  # Full expression in tooltip
                            remote_tree.addTopLevelItem(item)
                        # Update tab label with count
                        tab_widget.setTabText(2, f"🗂️ Remote Layers ({len(fav.remote_layers)})")
                    else:
                        remote_tree.hide()
                        no_remote_label.show()
                        tab_widget.setTabText(2, "🗂️ Remote Layers")
                    
                    apply_btn.setEnabled(True)
                    save_btn.setEnabled(True)
                    delete_btn.setEnabled(True)
        
        def on_apply():
            if current_fav_id[0]:
                self._apply_favorite(current_fav_id[0])
                dialog.accept()
        
        def on_save():
            if current_fav_id[0]:
                new_name = name_edit.text().strip()
                new_expr = expression_edit.toPlainText().strip()
                new_desc = description_edit.toPlainText().strip()
                # Parse tags from comma-separated string
                new_tags = [tag.strip() for tag in tags_edit.text().split(',') if tag.strip()]
                if new_name:
                    self._favorites_manager.update_favorite(
                        current_fav_id[0],
                        name=new_name,
                        expression=new_expr,
                        description=new_desc,
                        tags=new_tags
                    )
                    self._favorites_manager.save_to_project()
                    # Update list item
                    item = list_widget.currentItem()
                    if item:
                        fav = self._favorites_manager.get_favorite(current_fav_id[0])
                        layers_count = fav.get_layers_count() if fav and hasattr(fav, 'get_layers_count') else 1
                        item_text = f"★ {new_name}"
                        if layers_count > 1:
                            item_text += f" [{layers_count}]"
                        if new_tags:
                            item_text += " 🏷️"
                        item.setText(item_text)
                    show_success("FilterMate", "Favorite updated")
        
        def on_delete():
            if current_fav_id[0]:
                fav = self._favorites_manager.get_favorite(current_fav_id[0])
                if fav:
                    reply = QMessageBox.question(
                        dialog,
                        "Delete Favorite",
                        f"Delete favorite '{fav.name}'?",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if reply == QMessageBox.Yes:
                        self._favorites_manager.remove_favorite(current_fav_id[0])
                        list_widget.takeItem(list_widget.currentRow())
                        header_label.setText(f"<b>Saved Favorites ({self._favorites_manager.count})</b>")
                        
                        # Clear all fields in all tabs
                        # Tab 1: General
                        name_edit.clear()
                        description_edit.clear()
                        tags_edit.clear()
                        layer_label.setText("-")
                        provider_label.setText("-")
                        use_count_label.setText("-")
                        created_label.setText("-")
                        
                        # Tab 2: Expression
                        expression_edit.clear()
                        
                        # Tab 3: Remote Layers
                        remote_tree.clear()
                        no_remote_label.show()
                        remote_tree.hide()
                        tab_widget.setTabText(2, "🗂️ Remote Layers")
                        
                        current_fav_id[0] = None
                        apply_btn.setEnabled(False)
                        save_btn.setEnabled(False)
                        delete_btn.setEnabled(False)
                        self._update_favorite_indicator()
                        
                        # Save changes to persist deletion
                        self._favorites_manager.save_to_project()
                        
                        # Auto-select next available item after deletion
                        if list_widget.count() > 0:
                            list_widget.setCurrentRow(0)
                            # Force trigger selection change (signal may not fire if row 0 was already selected)
                            on_selection_changed()
        
        list_widget.currentItemChanged.connect(on_selection_changed)
        apply_btn.clicked.connect(on_apply)
        save_btn.clicked.connect(on_save)
        delete_btn.clicked.connect(on_delete)
        close_btn.clicked.connect(dialog.reject)
        
        # Select first item
        if list_widget.count() > 0:
            list_widget.setCurrentRow(0)
        
        dialog.exec_()
    
    def _export_favorites(self):
        """Export favorites to a JSON file."""
        from qgis.PyQt.QtWidgets import QFileDialog
        
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Favorites",
            "filtermate_favorites.json",
            "JSON Files (*.json)"
        )
        
        if filepath:
            if self._favorites_manager.export_to_file(filepath):
                show_success("FilterMate", f"Exported {self._favorites_manager.count} favorites")
            else:
                show_warning("FilterMate", "Failed to export favorites")
    
    def _import_favorites(self):
        """Import favorites from a JSON file."""
        from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox
        
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Import Favorites",
            "",
            "JSON Files (*.json)"
        )
        
        if filepath:
            # Ask merge or replace
            result = QMessageBox.question(
                self,
                "Import Favorites",
                "Merge with existing favorites?\n\n"
                "Yes = Add to existing\n"
                "No = Replace all existing",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            
            if result == QMessageBox.Cancel:
                return
            
            merge = (result == QMessageBox.Yes)
            count = self._favorites_manager.import_from_file(filepath, merge=merge)
            
            if count > 0:
                self._favorites_manager.save_to_project()
                self._update_favorite_indicator()
                show_success("FilterMate", f"Imported {count} favorites")
            else:
                show_warning("FilterMate", "No favorites imported")
    
    def _update_favorite_indicator(self):
        """Update the favorites indicator badge with current count."""
        if not hasattr(self, 'favorites_indicator_label') or not self.favorites_indicator_label:
            return
        
        # Get favorites manager
        favorites_manager = getattr(self, '_favorites_manager', None)
        if favorites_manager is None:
            count = 0
        else:
            count = favorites_manager.count
        
        # Update text
        if count > 0:
            self.favorites_indicator_label.setText(f"★ {count}")
            tooltip = f"★ {count} Favorites saved\nClick to apply or manage"
            # Brighter color when there are favorites
            style = """
                QLabel#label_favorites_indicator {
                    color: white;
                    font-size: 9pt;
                    font-weight: 600;
                    padding: 3px 10px;
                    border-radius: 12px;
                    border: none;
                    background-color: #f39c12;
                }
                QLabel#label_favorites_indicator:hover {
                    background-color: #d68910;
                }
            """
        else:
            self.favorites_indicator_label.setText("★")
            tooltip = "★ No favorites saved\nClick to add current filter"
            # Muted color when empty
            style = """
                QLabel#label_favorites_indicator {
                    color: #95a5a6;
                    font-size: 9pt;
                    font-weight: 600;
                    padding: 3px 10px;
                    border-radius: 12px;
                    border: none;
                    background-color: #ecf0f1;
                }
                QLabel#label_favorites_indicator:hover {
                    background-color: #d5dbdb;
                }
            """
        
        self.favorites_indicator_label.setStyleSheet(style)
        self.favorites_indicator_label.setToolTip(tooltip)
        self.favorites_indicator_label.adjustSize()

    def _get_available_backends_for_layer(self, layer):
        """
        Get list of available backends for the given layer.
        
        Returns:
            List of tuples: (backend_type, backend_name, backend_icon)
        """
        from .modules.appUtils import POSTGRESQL_AVAILABLE
        from .modules.constants import PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR
        
        available = []
        provider_type = layer.providerType()
        
        # PostgreSQL backend (only for postgres layers with psycopg2 available)
        if provider_type == 'postgres' and POSTGRESQL_AVAILABLE:
            available.append(('postgresql', 'PostgreSQL', '🐘'))
        
        # Spatialite backend (for spatialite layers and some OGR layers)
        if provider_type in ['spatialite', 'ogr']:
            # Check if it's a SQLite-based layer
            source = layer.source()
            if 'gpkg' in source.lower() or 'sqlite' in source.lower() or provider_type == 'spatialite':
                available.append(('spatialite', 'Spatialite', '💾'))
        
        # OGR backend (always available as fallback)
        available.append(('ogr', 'OGR', '📁'))
        
        # Remove current backend to show only alternatives
        # (but keep at least one option)
        if len(available) > 1:
            current_backend = self._detect_current_backend(layer)
            available = [b for b in available if b[0] != current_backend]
        
        return available
    
    def _detect_current_backend(self, layer):
        """
        Detect which backend is currently being used for a layer.
        
        Returns:
            str: Backend type ('postgresql', 'spatialite', 'ogr')
        """
        from .modules.appUtils import POSTGRESQL_AVAILABLE
        
        provider_type = layer.providerType()
        
        # Check for forced backend first
        if hasattr(self, 'forced_backends') and layer.id() in self.forced_backends:
            return self.forced_backends[layer.id()]
        
        # Auto-detection based on provider
        if provider_type == 'postgres' and POSTGRESQL_AVAILABLE:
            return 'postgresql'
        elif provider_type == 'spatialite':
            return 'spatialite'
        else:
            return 'ogr'

    def _verify_backend_supports_layer(self, layer, backend_type):
        """
        Verify that a backend can actually support a layer.
        
        Uses the backend's supports_layer() method to test actual compatibility
        (not just theoretical availability).
        
        Args:
            layer: QgsVectorLayer instance
            backend_type: Backend type string ('postgresql', 'spatialite', 'ogr')
        
        Returns:
            bool: True if backend can support this layer
        """
        from .modules.backends.postgresql_backend import PostgreSQLGeometricFilter
        from .modules.backends.spatialite_backend import SpatialiteGeometricFilter
        from .modules.backends.ogr_backend import OGRGeometricFilter
        from .modules.appUtils import POSTGRESQL_AVAILABLE
        
        if not layer or not layer.isValid():
            return False
        
        # Create backend instance with minimal params
        task_params = {}
        
        try:
            if backend_type == 'postgresql':
                if not POSTGRESQL_AVAILABLE:
                    return False
                backend = PostgreSQLGeometricFilter(task_params)
            elif backend_type == 'spatialite':
                backend = SpatialiteGeometricFilter(task_params)
            elif backend_type == 'ogr':
                backend = OGRGeometricFilter(task_params)
            else:
                return False
            
            # Test actual compatibility
            return backend.supports_layer(layer)
            
        except Exception as e:
            logger.warning(f"Error testing backend {backend_type} for layer {layer.name()}: {e}")
            return False
    
    def _set_forced_backend(self, layer_id, backend_type):
        """
        Force a specific backend for a layer.
        
        Args:
            layer_id: Layer ID
            backend_type: Backend type to force, or None for auto
        """
        if not hasattr(self, 'forced_backends'):
            self.forced_backends = {}
        
        if backend_type is None:
            # Remove forced backend (use auto)
            if layer_id in self.forced_backends:
                del self.forced_backends[layer_id]
        else:
            self.forced_backends[layer_id] = backend_type

    def _force_backend_for_all_layers(self, backend_type):
        """
        Force a specific backend for all layers in the project.
        
        For Spatialite backend on GeoPackage/OGR layers: forces even if support test fails,
        because user explicitly requested this backend.
        
        Args:
            backend_type: Backend type to force ('postgresql', 'spatialite', 'ogr', or None)
        """
        from qgis.utils import iface
        from qgis.core import QgsProject
        from .modules.backends.postgresql_backend import PostgreSQLGeometricFilter
        from .modules.backends.spatialite_backend import SpatialiteGeometricFilter
        from .modules.backends.ogr_backend import OGRGeometricFilter
        from .modules.appUtils import POSTGRESQL_AVAILABLE
        
        if not backend_type:
            show_warning("FilterMate", "No backend selected to force")
            return
        
        logger.info("=" * 60)
        logger.info(f"FORCING {backend_type.upper()} BACKEND FOR ALL LAYERS")
        logger.info("=" * 60)
        
        forced_count = 0
        skipped_count = 0
        warned_count = 0  # Layers forced with warning
        incompatible_layers = []
        
        project = QgsProject.instance()
        layers = project.mapLayers().values()
        
        # Create backend instance to test compatibility
        task_params = {}  # Minimal params just for testing
        if backend_type == 'postgresql':
            if not POSTGRESQL_AVAILABLE:
                show_warning(
                    "FilterMate", 
                    "PostgreSQL backend not available (psycopg2 not installed)"
                )
                return
            backend = PostgreSQLGeometricFilter(task_params)
        elif backend_type == 'spatialite':
            backend = SpatialiteGeometricFilter(task_params)
        elif backend_type == 'ogr':
            backend = OGRGeometricFilter(task_params)
        else:
            show_warning("FilterMate", f"Unknown backend type: {backend_type}")
            return
        
        from qgis.core import QgsVectorLayer
        
        for layer in layers:
            # Skip non-vector layers (raster, mesh, etc.)
            if not isinstance(layer, QgsVectorLayer):
                continue
            
            if not layer.isValid():
                skipped_count += 1
                continue
            
            layer_name = layer.name()
            logger.info(f"\nProcessing layer: {layer_name}")
            logger.info(f"  Provider: {layer.providerType()}, Features: {layer.featureCount():,}")
            
            # Check if backend supports this layer
            supports = backend.supports_layer(layer)
            
            if supports:
                self._set_forced_backend(layer.id(), backend_type)
                forced_count += 1
                logger.info(f"  ✓ Forced backend to: {backend_type.upper()}")
            else:
                # SPECIAL CASE: For Spatialite backend on GeoPackage/OGR layers,
                # force anyway because user explicitly requested it
                # The support test may fail due to geometry column detection issues
                source = layer.source()
                source_path = source.split('|')[0] if '|' in source else source
                is_gpkg_or_sqlite = (
                    source_path.lower().endswith('.gpkg') or 
                    source_path.lower().endswith('.sqlite')
                )
                is_ogr = layer.providerType() == 'ogr'
                
                if backend_type == 'spatialite' and (is_gpkg_or_sqlite or is_ogr):
                    # Force Spatialite anyway for GeoPackage/SQLite/OGR layers
                    self._set_forced_backend(layer.id(), backend_type)
                    warned_count += 1
                    logger.warning(
                        f"  ⚠️ Forcing {backend_type.upper()} for {layer_name} despite support test failure. "
                        f"GeoPackage/SQLite files should support Spatialite SQL functions."
                    )
                elif backend_type == 'ogr':
                    # OGR is universal fallback - force for all vector layers
                    self._set_forced_backend(layer.id(), backend_type)
                    forced_count += 1
                    logger.info(f"  ✓ Forced backend to: {backend_type.upper()} (universal fallback)")
                else:
                    incompatible_layers.append(layer_name)
                    skipped_count += 1
                    logger.info(f"  ⚠ Backend {backend_type.upper()} not compatible with this layer - skipping")
        
        total_forced = forced_count + warned_count
        logger.info("\n" + "=" * 60)
        logger.info("FORCE BACKEND COMPLETE")
        logger.info(f"Forced: {forced_count} layers to {backend_type.upper()}")
        if warned_count > 0:
            logger.info(f"Forced with warning: {warned_count} layers (support test failed but forced anyway)")
        logger.info(f"Skipped: {skipped_count} layers (incompatible or invalid)")
        if incompatible_layers:
            logger.info(f"Incompatible layers: {', '.join(incompatible_layers)}")
        logger.info("=" * 60)
        
        # Show summary message with details
        if total_forced > 0:
            msg = f"Forced {total_forced} layer(s) to use {backend_type.upper()} backend"
            if warned_count > 0:
                msg += f" ({warned_count} with warnings)"
            if skipped_count > 0:
                msg += f" ({skipped_count} incompatible layer(s) skipped)"
            show_success("FilterMate", msg)
        else:
            msg = f"No layers compatible with {backend_type.upper()} backend"
            if incompatible_layers:
                msg += f" - Incompatible: {', '.join(incompatible_layers[:3])}"
                if len(incompatible_layers) > 3:
                    msg += f" and {len(incompatible_layers) - 3} more"
            show_warning("FilterMate", msg)
        
        # Update indicator for current layer
        if self.current_layer:
            # Get layer properties to pass to synchronization
            _, _, layer_props = self._validate_and_prepare_layer(self.current_layer)
            self._synchronize_layer_widgets(self.current_layer, layer_props)
    
    def get_forced_backend_for_layer(self, layer_id):
        """
        Get forced backend for a layer, if any.
        
        Args:
            layer_id: Layer ID
        
        Returns:
            str or None: Forced backend type, or None if auto
        """
        if not hasattr(self, 'forced_backends'):
            self.forced_backends = {}
        return self.forced_backends.get(layer_id)
    
    def _get_optimal_backend_for_layer(self, layer):
        """
        Determine optimal backend for a layer based on its characteristics.
        
        Logic matches BackendFactory.get_backend() to ensure consistency.
        
        Analysis criteria:
        - Layer provider type
        - Feature count (small/medium/large datasets)
        - PostgreSQL availability (psycopg2 installed)
        - Data source type (file-based vs server-based)
        
        Args:
            layer: QgsVectorLayer instance
        
        Returns:
            str or None: Optimal backend type ('postgresql', 'spatialite', 'ogr'), or None for auto
        """
        from qgis.core import QgsVectorLayer
        from .modules.appUtils import detect_layer_provider_type, POSTGRESQL_AVAILABLE
        from .modules.backends.factory import should_use_memory_optimization
        
        # Only process vector layers
        if not layer or not isinstance(layer, QgsVectorLayer) or not layer.isValid():
            return None
        
        provider_type = detect_layer_provider_type(layer)
        feature_count = layer.featureCount()
        source = layer.source().lower()
        
        logger.info(f"Analyzing layer: {layer.name()}")
        logger.info(f"  Provider: {provider_type}, Features: {feature_count:,}")
        logger.info(f"  PostgreSQL available: {POSTGRESQL_AVAILABLE}")
        
        # PostgreSQL layers
        if provider_type == 'postgresql':
            if not POSTGRESQL_AVAILABLE:
                logger.info(f"  → PostgreSQL unavailable - OGR fallback")
                return 'ogr'
            
            # Check if memory optimization would be used (matches BackendFactory logic)
            if should_use_memory_optimization(layer, provider_type):
                logger.info(f"  → Small PostgreSQL dataset ({feature_count} features) - OGR memory optimization")
                return 'ogr'
            
            # Large PostgreSQL datasets - use PostgreSQL backend for server-side ops
            logger.info(f"  → Large PostgreSQL dataset ({feature_count} features) - PostgreSQL optimal")
            return 'postgresql'
        
        # SQLite/Spatialite layers
        elif provider_type == 'spatialite':
            if feature_count > 5000:
                logger.info(f"  → SQLite dataset ({feature_count} features) - Spatialite R-tree indexes optimal")
                return 'spatialite'
            else:
                logger.info(f"  → Small SQLite dataset ({feature_count} features) - OGR sufficient")
                return 'ogr'
        
        # OGR layers (Shapefile, GeoJSON, GeoPackage via OGR)
        elif provider_type == 'ogr':
            # Check if it's a GeoPackage/SQLite accessed via OGR
            if 'gpkg' in source or 'sqlite' in source:
                if feature_count > 5000:
                    logger.info(f"  → GeoPackage via OGR ({feature_count} features) - Spatialite backend optimal")
                    return 'spatialite'
                else:
                    logger.info(f"  → Small GeoPackage ({feature_count} features) - OGR sufficient")
                    return 'ogr'
            
            # Regular OGR formats (Shapefile, GeoJSON, etc.)
            logger.info(f"  → OGR format ({feature_count} features) - OGR backend sufficient")
            return 'ogr'
        
        # Unknown provider - let auto-selection handle it
        logger.info(f"  → Unknown provider '{provider_type}' - using auto-selection")
        return None
    
    # ========================================
    # POSTGRESQL MAINTENANCE METHODS
    # ========================================
    
    def _toggle_pg_auto_cleanup(self):
        """
        Toggle automatic cleanup of PostgreSQL session views on plugin unload.
        """
        current_state = getattr(self, '_pg_auto_cleanup_enabled', True)
        self._pg_auto_cleanup_enabled = not current_state
        
        if self._pg_auto_cleanup_enabled:
            show_success("FilterMate", "PostgreSQL auto-cleanup enabled. Session views will be dropped on plugin unload.")
        else:
            show_info("FilterMate", "PostgreSQL auto-cleanup disabled. Session views will remain after plugin unload.")
        
        logger.info(f"PostgreSQL auto-cleanup toggled: {self._pg_auto_cleanup_enabled}")
    
    def _cleanup_postgresql_session_views(self):
        """
        Manually cleanup all PostgreSQL materialized views for the current session.
        """
        from .modules.appUtils import POSTGRESQL_AVAILABLE, get_datasource_connexion_from_layer
        
        if not POSTGRESQL_AVAILABLE:
            show_warning("FilterMate", "PostgreSQL not available")
            return
        
        # Get session_id from app
        app = getattr(self, '_app_ref', None)
        if not app:
            # Try to get from parent
            parent = self.parent()
            while parent:
                if hasattr(parent, 'session_id'):
                    app = parent
                    break
                parent = parent.parent() if hasattr(parent, 'parent') else None
        
        session_id = getattr(app, 'session_id', None) if app else None
        schema = getattr(app, 'app_postgresql_temp_schema', 'filter_mate_temp') if app else 'filter_mate_temp'
        
        if not session_id:
            show_warning("FilterMate", "Session ID not available. Cannot identify session views.")
            return
        
        # Find a PostgreSQL layer to get connection
        connexion = None
        project_layers = getattr(app, 'PROJECT_LAYERS', {}) if app else {}
        
        for layer_id, layer_info in project_layers.items():
            layer = layer_info.get('layer')
            if layer and layer.isValid() and layer.providerType() == 'postgres':
                connexion, _ = get_datasource_connexion_from_layer(layer)
                if connexion:
                    break
        
        if not connexion:
            show_warning("FilterMate", "No PostgreSQL connection available")
            return
        
        try:
            with connexion.cursor() as cursor:
                # Find all materialized views for this session
                cursor.execute("""
                    SELECT matviewname FROM pg_matviews 
                    WHERE schemaname = %s AND matviewname LIKE %s
                """, (schema, f"mv_{session_id}_%"))
                views = cursor.fetchall()
                
                if not views:
                    show_info("FilterMate", f"No materialized views found for session {session_id[:8]}")
                    return
                
                count = 0
                for (view_name,) in views:
                    try:
                        cursor.execute(f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."{view_name}" CASCADE;')
                        count += 1
                    except Exception as e:
                        logger.warning(f"Error dropping view {view_name}: {e}")
                
                connexion.commit()
                show_success("FilterMate", f"Cleaned up {count} materialized view(s) for session {session_id[:8]}")
                logger.info(f"Manually cleaned up {count} PostgreSQL materialized views for session {session_id}")
        except Exception as e:
            show_warning("FilterMate", f"Error cleaning up views: {str(e)[:50]}")
            logger.error(f"Error cleaning PostgreSQL views: {e}")
        finally:
            try:
                connexion.close()
            except:
                pass
    
    def _cleanup_postgresql_schema_if_empty(self):
        """
        Drop the filter_mate_temp schema if no other sessions are using it.
        
        Checks for existing materialized views from other sessions before dropping.
        """
        from .modules.appUtils import POSTGRESQL_AVAILABLE, get_datasource_connexion_from_layer
        
        if not POSTGRESQL_AVAILABLE:
            show_warning("FilterMate", "PostgreSQL not available")
            return
        
        # Get session_id and schema from app
        app = getattr(self, '_app_ref', None)
        if not app:
            parent = self.parent()
            while parent:
                if hasattr(parent, 'session_id'):
                    app = parent
                    break
                parent = parent.parent() if hasattr(parent, 'parent') else None
        
        session_id = getattr(app, 'session_id', None) if app else None
        schema = getattr(app, 'app_postgresql_temp_schema', 'filter_mate_temp') if app else 'filter_mate_temp'
        
        # Find a PostgreSQL layer to get connection
        connexion = None
        project_layers = getattr(app, 'PROJECT_LAYERS', {}) if app else {}
        
        for layer_id, layer_info in project_layers.items():
            layer = layer_info.get('layer')
            if layer and layer.isValid() and layer.providerType() == 'postgres':
                connexion, _ = get_datasource_connexion_from_layer(layer)
                if connexion:
                    break
        
        if not connexion:
            show_warning("FilterMate", "No PostgreSQL connection available")
            return
        
        try:
            with connexion.cursor() as cursor:
                # Check if schema exists
                cursor.execute("""
                    SELECT COUNT(*) FROM information_schema.schemata 
                    WHERE schema_name = %s
                """, (schema,))
                if cursor.fetchone()[0] == 0:
                    show_info("FilterMate", f"Schema '{schema}' does not exist")
                    return
                
                # Check for any materialized views in the schema
                cursor.execute("""
                    SELECT matviewname FROM pg_matviews 
                    WHERE schemaname = %s
                """, (schema,))
                views = cursor.fetchall()
                
                if views:
                    # Filter out our own session's views
                    other_session_views = []
                    our_views = []
                    for (view_name,) in views:
                        if session_id and view_name.startswith(f"mv_{session_id}_"):
                            our_views.append(view_name)
                        else:
                            other_session_views.append(view_name)
                    
                    if other_session_views:
                        # Other sessions are active
                        from qgis.PyQt.QtWidgets import QMessageBox
                        msg = (f"Schema '{schema}' has {len(other_session_views)} view(s) from other sessions.\n\n"
                               f"Other session views:\n" + 
                               "\n".join(f"  • {v}" for v in other_session_views[:5]))
                        if len(other_session_views) > 5:
                            msg += f"\n  ... and {len(other_session_views) - 5} more"
                        msg += f"\n\nOur session ({session_id[:8] if session_id else 'unknown'}): {len(our_views)} view(s)"
                        msg += "\n\nDo you want to drop the ENTIRE schema anyway?\n⚠️ This will affect other FilterMate clients!"
                        
                        reply = QMessageBox.question(
                            self, "Other Sessions Active", msg,
                            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                        )
                        
                        if reply != QMessageBox.Yes:
                            show_info("FilterMate", "Schema cleanup cancelled - other sessions are active")
                            return
                
                # Drop the schema
                cursor.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE;')
                connexion.commit()
                
                show_success("FilterMate", f"Schema '{schema}' dropped successfully")
                logger.info(f"PostgreSQL schema '{schema}' dropped")
                
        except Exception as e:
            show_warning("FilterMate", f"Error dropping schema: {str(e)[:50]}")
            logger.error(f"Error dropping PostgreSQL schema: {e}")
        finally:
            try:
                connexion.close()
            except:
                pass
    
    def _show_postgresql_session_info(self):
        """
        Show information about the current PostgreSQL session and materialized views.
        """
        from .modules.appUtils import POSTGRESQL_AVAILABLE, get_datasource_connexion_from_layer
        from qgis.PyQt.QtWidgets import QMessageBox
        
        if not POSTGRESQL_AVAILABLE:
            show_warning("FilterMate", "PostgreSQL not available")
            return
        
        # Get session info from app
        app = getattr(self, '_app_ref', None)
        if not app:
            parent = self.parent()
            while parent:
                if hasattr(parent, 'session_id'):
                    app = parent
                    break
                parent = parent.parent() if hasattr(parent, 'parent') else None
        
        session_id = getattr(app, 'session_id', None) if app else None
        schema = getattr(app, 'app_postgresql_temp_schema', 'filter_mate_temp') if app else 'filter_mate_temp'
        auto_cleanup = getattr(self, '_pg_auto_cleanup_enabled', True)
        
        info_text = f"<b>Session Information</b><br><br>"
        info_text += f"<b>Session ID:</b> {session_id or 'Not set'}<br>"
        info_text += f"<b>Temp Schema:</b> {schema}<br>"
        info_text += f"<b>Auto-cleanup:</b> {'Enabled' if auto_cleanup else 'Disabled'}<br><br>"
        
        # Try to get view count from database
        connexion = None
        project_layers = getattr(app, 'PROJECT_LAYERS', {}) if app else {}
        
        for layer_id, layer_info in project_layers.items():
            layer = layer_info.get('layer')
            if layer and layer.isValid() and layer.providerType() == 'postgres':
                connexion, _ = get_datasource_connexion_from_layer(layer)
                if connexion:
                    break
        
        if connexion:
            try:
                with connexion.cursor() as cursor:
                    # Count our session's views
                    if session_id:
                        cursor.execute("""
                            SELECT COUNT(*) FROM pg_matviews 
                            WHERE schemaname = %s AND matviewname LIKE %s
                        """, (schema, f"mv_{session_id}_%"))
                        our_count = cursor.fetchone()[0]
                    else:
                        our_count = 0
                    
                    # Count all views in schema
                    cursor.execute("""
                        SELECT COUNT(*) FROM pg_matviews 
                        WHERE schemaname = %s
                    """, (schema,))
                    total_count = cursor.fetchone()[0]
                    
                    # Check if schema exists
                    cursor.execute("""
                        SELECT COUNT(*) FROM information_schema.schemata 
                        WHERE schema_name = %s
                    """, (schema,))
                    schema_exists = cursor.fetchone()[0] > 0
                    
                    info_text += f"<b>Schema exists:</b> {'Yes' if schema_exists else 'No'}<br>"
                    info_text += f"<b>Your session views:</b> {our_count}<br>"
                    info_text += f"<b>Total views in schema:</b> {total_count}<br>"
                    info_text += f"<b>Other sessions views:</b> {total_count - our_count}<br>"
                    
            except Exception as e:
                info_text += f"<b>Error querying database:</b> {str(e)[:50]}<br>"
            finally:
                try:
                    connexion.close()
                except:
                    pass
        else:
            info_text += "<b>Database:</b> No PostgreSQL connection available<br>"
        
        QMessageBox.information(self, "PostgreSQL Session Info", info_text)

    def auto_select_optimal_backends(self):
        """
        Automatically select optimal backend for all layers in the project.
        
        Analyzes each layer's characteristics and sets the most appropriate backend.
        Shows summary message with results.
        """
        from qgis.core import QgsProject
        
        if not hasattr(self, 'PROJECT_LAYERS') or not self.PROJECT_LAYERS:
            show_warning("FilterMate", "No layers loaded in project")
            return
        
        logger.info("=" * 60)
        logger.info("AUTO-SELECTING OPTIMAL BACKENDS FOR ALL LAYERS")
        logger.info("=" * 60)
        
        optimized_count = 0
        skipped_count = 0
        backend_stats = {'postgresql': 0, 'spatialite': 0, 'ogr': 0, 'auto': 0}
        
        project = QgsProject.instance()
        layers = project.mapLayers().values()
        
        from qgis.core import QgsVectorLayer
        
        for layer in layers:
            # Skip non-vector layers (raster, mesh, etc.)
            if not isinstance(layer, QgsVectorLayer):
                continue
            
            if not layer.isValid():
                skipped_count += 1
                continue
            
            layer_name = layer.name()
            logger.info(f"\nAnalyzing layer: {layer_name}")
            
            # Get optimal backend for THIS SPECIFIC LAYER
            optimal_backend = self._get_optimal_backend_for_layer(layer)
            
            if optimal_backend:
                # Verify that the optimal backend actually supports this layer
                if self._verify_backend_supports_layer(layer, optimal_backend):
                    # Set forced backend
                    self._set_forced_backend(layer.id(), optimal_backend)
                    backend_stats[optimal_backend] += 1
                    optimized_count += 1
                    logger.info(f"  ✓ Set backend to: {optimal_backend.upper()}")
                else:
                    # Backend not compatible - keep auto
                    backend_stats['auto'] += 1
                    logger.info(f"  ⚠ Optimal backend {optimal_backend.upper()} not compatible - keeping auto-selection")
            else:
                # Keep auto-selection
                backend_stats['auto'] += 1
                logger.info(f"  → Keeping auto-selection")
        
        logger.info("\n" + "=" * 60)
        logger.info("AUTO-SELECTION COMPLETE")
        logger.info(f"Optimized: {optimized_count} layers")
        logger.info(f"Skipped: {skipped_count} invalid layers")
        logger.info(f"Backend distribution:")
        for backend, count in backend_stats.items():
            if count > 0:
                logger.info(f"  - {backend.upper()}: {count} layer(s)")
        logger.info("=" * 60)
        
        # Show summary message
        if optimized_count > 0:
            summary = f"Optimized {optimized_count} layer(s): "
            summary += ", ".join([f"{count} {backend.upper()}" for backend, count in backend_stats.items() if count > 0 and backend != 'auto'])
            show_success("FilterMate", summary)
        else:
            show_info("FilterMate", "All layers using auto-selection")
        
        # Update indicator for current layer
        if self.current_layer:
            # Get layer properties to pass to synchronization
            _, _, layer_props = self._validate_and_prepare_layer(self.current_layer)
            self._synchronize_layer_widgets(self.current_layer, layer_props)
        
        # The label will be added to frame_actions layout in _create_horizontal_action_bar_layout

    def _setup_action_bar_layout(self):
        """
        Setup the action bar layout based on configuration.
        
        Reads ACTION_BAR_POSITION from config and applies the appropriate layout:
        - 'top': Action bar at top (default horizontal layout)
        - 'bottom': Action bar at bottom (horizontal layout)
        - 'left': Action bar on left side (vertical layout)
        - 'right': Action bar on right side (vertical layout)
        """
        if not hasattr(self, 'frame_actions'):
            return
        
        # Get configured position
        position = self._get_action_bar_position()
        logger.info(f"Setting up action bar with position: {position}")
        
        # Initialize tracking attributes
        self._side_action_bar_active = False
        self._side_action_bar_position = None
        self._side_action_bar_alignment = None
        self._vertical_action_spacer = None
        self._side_action_wrapper = None
        
        # Apply the position
        if position in ('left', 'right'):
            # For side positions, we need to set up the wrapper layout
            self._apply_action_bar_position(position)
        else:
            # For top/bottom, use the default horizontal layout
            self.frame_actions.show()
            self._current_action_bar_position = position
            logger.info(f"Action bar: Using '{position}' position")

    def _get_action_bar_position(self):
        """
        Get action bar position from configuration.
        
        Returns:
            str: Position value ('top', 'bottom', 'left', 'right')
        """
        try:
            position_config = self.CONFIG_DATA.get('APP', {}).get('DOCKWIDGET', {}).get('ACTION_BAR_POSITION', {})
            if isinstance(position_config, dict):
                return position_config.get('value', 'top')
            return position_config if position_config else 'top'
        except (KeyError, TypeError, AttributeError):
            return 'top'

    def _get_action_bar_vertical_alignment(self):
        """
        Get action bar vertical alignment from configuration.
        
        Only applies when action bar is in vertical mode (left/right position).
        
        Returns:
            str: Alignment value ('top', 'bottom')
        """
        try:
            alignment_config = self.CONFIG_DATA.get('APP', {}).get('DOCKWIDGET', {}).get('ACTION_BAR_VERTICAL_ALIGNMENT', {})
            if isinstance(alignment_config, dict):
                return alignment_config.get('value', 'top')
            return alignment_config if alignment_config else 'top'
        except (KeyError, TypeError, AttributeError):
            return 'top'

    def _apply_action_bar_position(self, position):
        """
        Apply action bar position dynamically.
        
        Reorganizes the layout to place the action bar at the specified position.
        Supports horizontal (top/bottom) and vertical (left/right) layouts with
        appropriate spacers for each mode.
        
        Args:
            position: str - 'top', 'bottom', 'left', 'right'
        """
        if not hasattr(self, 'frame_actions'):
            return
        
        logger.info(f"Applying action bar position: {position}")
        
        # First, restore from any previous side action bar setup
        if hasattr(self, '_side_action_bar_active') and self._side_action_bar_active:
            self._restore_side_action_bar_layout()
        
        # Get all action buttons
        action_buttons = [
            self.pushButton_action_filter,
            self.pushButton_action_undo_filter,
            self.pushButton_action_redo_filter,
            self.pushButton_action_unfilter,
            self.pushButton_action_export,
            self.pushButton_action_about
        ]
        
        # Step 1: Completely delete the old layout and create new one
        self._clear_action_bar_layout()
        
        # Step 2: Create new layout based on position (horizontal or vertical)
        is_horizontal = position in ('top', 'bottom')
        if is_horizontal:
            self._create_horizontal_action_layout(action_buttons)
        else:
            self._create_vertical_action_layout(action_buttons)
        
        # Step 3: Apply size constraints based on orientation
        self._apply_action_bar_size_constraints(position)
        
        # Step 4: Reposition frame_actions in the main layout
        self._reposition_action_bar_in_main_layout(position)
        
        # Step 5: Adjust header for side positions (left/right)
        self._adjust_header_for_side_position(position)
        
        # Store current position for reference
        self._current_action_bar_position = position

    def _adjust_header_for_side_position(self, position):
        """
        Adjust header layout when action bar is in side position (left/right).
        
        Creates a wrapper with spacer to align the header with the main content.
        
        Args:
            position: str - 'top', 'bottom', 'left', 'right'
        """
        if not hasattr(self, 'frame_header') or not self.frame_header:
            return
        
        # Calculate the width of the action bar
        if UI_CONFIG_AVAILABLE:
            action_button_size = UIConfig.get_button_height("action_button")
            spacer_width = int(action_button_size * 1.3)
        else:
            spacer_width = 54  # Fallback width
        
        if position in ('left', 'right'):
            # Check if wrapper already exists
            if hasattr(self, '_header_wrapper') and self._header_wrapper:
                return  # Already wrapped
            
            # Get the parent layout of frame_header
            parent_layout = None
            if hasattr(self, 'verticalLayout_8'):
                parent_layout = self.verticalLayout_8
            
            if not parent_layout:
                return
            
            # Find frame_header's index in parent layout
            header_idx = parent_layout.indexOf(self.frame_header)
            if header_idx < 0:
                return
            
            # Remove frame_header from parent layout
            parent_layout.removeWidget(self.frame_header)
            
            # Create wrapper widget
            self._header_wrapper = QtWidgets.QWidget(self.dockWidgetContents)
            self._header_wrapper.setObjectName("header_wrapper")
            wrapper_layout = QtWidgets.QHBoxLayout(self._header_wrapper)
            wrapper_layout.setContentsMargins(0, 0, 0, 0)
            wrapper_layout.setSpacing(0)
            
            # Create spacer widget matching action bar width
            self._header_spacer = QtWidgets.QWidget(self._header_wrapper)
            self._header_spacer.setFixedWidth(spacer_width)
            self._header_spacer.setObjectName("header_spacer")
            
            # Add spacer and header in correct order
            if position == 'left':
                wrapper_layout.addWidget(self._header_spacer, 0)
                wrapper_layout.addWidget(self.frame_header, 1)
            else:  # right
                wrapper_layout.addWidget(self.frame_header, 1)
                wrapper_layout.addWidget(self._header_spacer, 0)
            
            # Insert wrapper at same position as original header
            parent_layout.insertWidget(header_idx, self._header_wrapper)
            
            logger.debug(f"Header wrapped with spacer for {position} side action bar (spacer_width={spacer_width})")
        else:
            # Restore original header position for top/bottom
            self._restore_header_from_wrapper()

    def _restore_header_from_wrapper(self):
        """
        Restore header from wrapper when switching away from side position.
        """
        if not hasattr(self, '_header_wrapper') or not self._header_wrapper:
            return
        
        if not hasattr(self, 'frame_header') or not self.frame_header:
            return
        
        # Get parent layout
        parent_layout = None
        if hasattr(self, 'verticalLayout_8'):
            parent_layout = self.verticalLayout_8
        
        if not parent_layout:
            return
        
        # Find wrapper's index
        wrapper_idx = parent_layout.indexOf(self._header_wrapper)
        if wrapper_idx < 0:
            return
        
        # Remove frame_header from wrapper
        wrapper_layout = self._header_wrapper.layout()
        if wrapper_layout:
            wrapper_layout.removeWidget(self.frame_header)
        
        # Remove wrapper from parent
        parent_layout.removeWidget(self._header_wrapper)
        
        # Re-add frame_header at same position
        self.frame_header.setParent(self.dockWidgetContents)
        parent_layout.insertWidget(wrapper_idx, self.frame_header)
        
        # Delete wrapper and spacer
        if hasattr(self, '_header_spacer') and self._header_spacer:
            self._header_spacer.deleteLater()
            self._header_spacer = None
        
        self._header_wrapper.deleteLater()
        self._header_wrapper = None
        
        logger.debug("Header restored from wrapper")


    def _clear_action_bar_layout(self):
        """
        Clear the existing action bar layout completely.
        
        Removes all widgets and spacers from the current layout and deletes it
        to prepare for a new layout.
        """
        old_layout = self.frame_actions.layout()
        if old_layout:
            # Remove all items from the layout
            while old_layout.count():
                item = old_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.setParent(None)  # Detach widget temporarily
            # Delete the layout by reparenting to a temporary widget
            temp_widget = QtWidgets.QWidget()
            temp_widget.setLayout(old_layout)
            temp_widget.deleteLater()

    def _create_horizontal_action_layout(self, action_buttons):
        """
        Create horizontal layout for action bar (top/bottom position).
        
        Creates a QHBoxLayout with action buttons separated by expanding
        horizontal spacers for even distribution.
        
        Args:
            action_buttons: list - List of QPushButton widgets to add
        """
        new_layout = QtWidgets.QHBoxLayout(self.frame_actions)
        # Increased bottom margin for better spacing below action buttons
        new_layout.setContentsMargins(8, 8, 8, 16)
        new_layout.setSpacing(6)
        
        for i, btn in enumerate(action_buttons):
            btn.setParent(self.frame_actions)
            new_layout.addWidget(btn)
            # Add small spacer between buttons
            if i < len(action_buttons) - 1:
                spacer = QtWidgets.QSpacerItem(
                    4, 20, 
                    QtWidgets.QSizePolicy.Expanding, 
                    QtWidgets.QSizePolicy.Minimum
                )
                new_layout.addItem(spacer)
        
        logger.debug("Created horizontal action bar layout")

    def _create_vertical_action_layout(self, action_buttons):
        """
        Create vertical layout for action bar (left/right position).
        
        Creates a QVBoxLayout with action buttons. The buttons are aligned
        at the top of the frame, with spacing between them.
        
        Args:
            action_buttons: list - List of QPushButton widgets to add
        """
        new_layout = QtWidgets.QVBoxLayout(self.frame_actions)
        new_layout.setContentsMargins(4, 4, 4, 4)
        new_layout.setSpacing(12)  # Spacing between buttons
        
        # Add buttons with center alignment
        for btn in action_buttons:
            btn.setParent(self.frame_actions)
            new_layout.addWidget(btn, 0, Qt.AlignHCenter)
        
        # Add stretch at the end to push buttons to top
        new_layout.addStretch(1)
        
        logger.debug("Created vertical action bar layout")

    def _apply_action_bar_size_constraints(self, position):
        """
        Apply appropriate size constraints to frame_actions based on position.
        
        For horizontal mode (top/bottom), constrains height.
        For vertical mode (left/right), constrains width and removes height constraints.
        
        Args:
            position: str - 'top', 'bottom', 'left', 'right'
        """
        if position in ('top', 'bottom'):
            # Horizontal mode: constrain height, allow width to expand
            if UI_CONFIG_AVAILABLE:
                action_button_height = UIConfig.get_button_height("action_button")
                frame_height = max(int(action_button_height * 1.8), 56)  # Minimum 56px to prevent clipping
            else:
                frame_height = 60  # Fallback height
            
            self.frame_actions.setMinimumHeight(frame_height)
            self.frame_actions.setMaximumHeight(frame_height + 15)  # Allow flexibility
            self.frame_actions.setMinimumWidth(0)
            self.frame_actions.setMaximumWidth(16777215)  # QWIDGETSIZE_MAX
            self.frame_actions.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, 
                QtWidgets.QSizePolicy.Preferred  # Changed from Fixed to allow expansion
            )
        else:
            # Vertical mode (left/right): constrain width, allow height to expand
            if UI_CONFIG_AVAILABLE:
                action_button_size = UIConfig.get_button_height("action_button")
                frame_width = int(action_button_size * 1.3)
            else:
                frame_width = 54  # Fallback width
            
            self.frame_actions.setMinimumWidth(frame_width)
            self.frame_actions.setMaximumWidth(frame_width)
            self.frame_actions.setMinimumHeight(0)
            self.frame_actions.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
            self.frame_actions.setSizePolicy(
                QtWidgets.QSizePolicy.Fixed, 
                QtWidgets.QSizePolicy.Expanding
            )
        
        logger.debug(f"Applied action bar size constraints for position: {position}")

    def _reposition_action_bar_in_main_layout(self, position):
        """
        Reposition the action bar frame in the main layout.
        
        Args:
            position: str - 'top', 'bottom', 'left', 'right'
        """
        # Remove frame_actions from horizontalLayout_actions_container (its original position)
        if self.horizontalLayout_actions_container.indexOf(self.frame_actions) >= 0:
            self.horizontalLayout_actions_container.removeWidget(self.frame_actions)
        
        if position == 'top':
            # Insert at the beginning of verticalLayout_main (before splitter)
            self.frame_actions.setParent(self.dockWidgetContents)
            self.verticalLayout_main.insertWidget(0, self.frame_actions)
            logger.info("Action bar positioned at TOP")
        elif position == 'bottom':
            # Re-add to horizontalLayout_actions_container (its original position at bottom)
            self.frame_actions.setParent(self.dockWidgetContents)
            self.horizontalLayout_actions_container.addWidget(self.frame_actions)
            logger.info("Action bar positioned at BOTTOM")
        elif position in ('left', 'right'):
            # Use wrapper for side positioning
            self._create_horizontal_wrapper_for_side_action_bar(position)
            logger.info(f"Action bar positioned at {position.upper()}")

    def _create_horizontal_wrapper_for_side_action_bar(self, position):
        """
        Position action bar vertically on left or right side.
        
        Alignment determines the vertical extent:
        - 'top': Action bar spans the full height (next to splitter)
        - 'bottom': Action bar is only in the bottom actions area
        
        Args:
            position: str - 'left' or 'right'
        """
        # Get alignment from config
        alignment = self._get_action_bar_vertical_alignment()
        
        # Calculate the width of frame_actions
        if UI_CONFIG_AVAILABLE:
            action_button_size = UIConfig.get_button_height("action_button")
            spacer_width = int(action_button_size * 1.3)
        else:
            spacer_width = 54  # Fallback width
        
        # Remove frame_actions from horizontalLayout_actions_container (its original position)
        if self.horizontalLayout_actions_container.indexOf(self.frame_actions) >= 0:
            self.horizontalLayout_actions_container.removeWidget(self.frame_actions)
        
        self.frame_actions.setParent(self.dockWidgetContents)
        
        if alignment == 'top':
            # 'top' alignment: Action bar spans full height, next to splitter
            if self.main_splitter is not None:
                parent_layout = self.verticalLayout_main
                splitter_idx = parent_layout.indexOf(self.main_splitter)
                
                if splitter_idx >= 0:
                    # Remove splitter from its current position
                    parent_layout.removeWidget(self.main_splitter)
                    
                    # Create a horizontal wrapper widget
                    self._side_action_wrapper = QtWidgets.QWidget(self.dockWidgetContents)
                    self._side_action_wrapper.setObjectName("side_action_wrapper")
                    wrapper_layout = QtWidgets.QHBoxLayout(self._side_action_wrapper)
                    wrapper_layout.setContentsMargins(0, 0, 0, 0)
                    wrapper_layout.setSpacing(0)
                    
                    # Add action bar and splitter in correct order
                    if position == 'left':
                        wrapper_layout.addWidget(self.frame_actions, 0)
                        wrapper_layout.addWidget(self.main_splitter, 1)
                    else:  # right
                        wrapper_layout.addWidget(self.main_splitter, 1)
                        wrapper_layout.addWidget(self.frame_actions, 0)
                    
                    # Insert wrapper at same position
                    parent_layout.insertWidget(splitter_idx, self._side_action_wrapper)
                    
                    # Add spacer to actions_container to align with action bar above
                    self._vertical_action_spacer = QtWidgets.QSpacerItem(
                        spacer_width, 0, 
                        QtWidgets.QSizePolicy.Fixed, 
                        QtWidgets.QSizePolicy.Minimum
                    )
                    if position == 'left':
                        self.horizontalLayout_actions_container.insertItem(0, self._vertical_action_spacer)
                    else:
                        self.horizontalLayout_actions_container.addItem(self._vertical_action_spacer)
                    
                    logger.info(f"Created side action bar wrapper (position={position}, alignment=top)")
        
        else:  # alignment == 'bottom'
            # 'bottom' alignment: Action bar only in actions container area
            # Place frame_actions in horizontalLayout_actions_container
            if position == 'left':
                self.horizontalLayout_actions_container.insertWidget(0, self.frame_actions)
            else:  # right
                self.horizontalLayout_actions_container.addWidget(self.frame_actions)
            
            # Add spacer next to splitter to align with action bar below
            if self.main_splitter is not None:
                parent_layout = self.verticalLayout_main
                splitter_idx = parent_layout.indexOf(self.main_splitter)
                
                if splitter_idx >= 0:
                    # Remove splitter from its current position
                    parent_layout.removeWidget(self.main_splitter)
                    
                    # Create a horizontal wrapper widget with spacer
                    self._side_action_wrapper = QtWidgets.QWidget(self.dockWidgetContents)
                    self._side_action_wrapper.setObjectName("side_action_wrapper")
                    wrapper_layout = QtWidgets.QHBoxLayout(self._side_action_wrapper)
                    wrapper_layout.setContentsMargins(0, 0, 0, 0)
                    wrapper_layout.setSpacing(0)
                    
                    # Create spacer widget for alignment
                    spacer_widget = QtWidgets.QWidget(self._side_action_wrapper)
                    spacer_widget.setFixedWidth(spacer_width)
                    spacer_widget.setObjectName("side_action_spacer_widget")
                    
                    # Add spacer and splitter in correct order
                    if position == 'left':
                        wrapper_layout.addWidget(spacer_widget, 0)
                        wrapper_layout.addWidget(self.main_splitter, 1)
                    else:  # right
                        wrapper_layout.addWidget(self.main_splitter, 1)
                        wrapper_layout.addWidget(spacer_widget, 0)
                    
                    # Insert wrapper at same position
                    parent_layout.insertWidget(splitter_idx, self._side_action_wrapper)
                    
                    # Note: Header margin adjustment is handled by _adjust_header_for_side_position
                    
                    logger.info(f"Created side action bar wrapper (position={position}, alignment=bottom)")
        
        # Mark that we're in side action bar mode
        self._side_action_bar_active = True
        self._side_action_bar_position = position
        self._side_action_bar_alignment = alignment

    def _restore_side_action_bar_layout(self):
        """
        Restore the layout when switching away from side (left/right) action bar position.
        
        Removes spacers, wrapper widgets, and moves frame_actions back to its original position
        in horizontalLayout_actions_container.
        """
        # Clean up the wrapper widget if it exists
        if hasattr(self, '_side_action_wrapper') and self._side_action_wrapper:
            # Move the splitter back to verticalLayout_main
            if self.main_splitter is not None:
                wrapper_layout = self._side_action_wrapper.layout()
                if wrapper_layout:
                    # Remove splitter from wrapper
                    wrapper_layout.removeWidget(self.main_splitter)
                    self.main_splitter.setParent(self.dockWidgetContents)
                
                # Get wrapper's position in parent layout
                parent_layout = self.verticalLayout_main
                wrapper_idx = parent_layout.indexOf(self._side_action_wrapper)
                
                # Remove wrapper and re-add splitter at same position
                if wrapper_idx >= 0:
                    parent_layout.removeWidget(self._side_action_wrapper)
                    parent_layout.insertWidget(wrapper_idx, self.main_splitter)
            
            # Delete wrapper widget
            self._side_action_wrapper.deleteLater()
            self._side_action_wrapper = None
        
        # Restore header from wrapper if it was wrapped
        self._restore_header_from_wrapper()
        
        # Remove previously added spacer if exists
        if hasattr(self, '_vertical_action_spacer') and self._vertical_action_spacer:
            # Remove from horizontalLayout_actions_container
            idx = self.horizontalLayout_actions_container.indexOf(self._vertical_action_spacer)
            if idx >= 0:
                self.horizontalLayout_actions_container.takeAt(idx)
            self._vertical_action_spacer = None
        
        # Reset tracking flags
        self._side_action_bar_active = False
        self._side_action_bar_position = None
        self._side_action_bar_alignment = None

    def _restore_original_layout(self):
        """
        Restore original layout when switching from side (left/right) to top/bottom position.
        
        This method cleans up the side action bar setup and moves frame_actions back
        to its original position in horizontalLayout_actions_container.
        """
        # First clean up the side action bar setup (spacers, position)
        self._restore_side_action_bar_layout()
        
        # Ensure frame_actions is in horizontalLayout_actions_container
        # Remove from any layout it might be in
        if self.frame_actions.parent():
            parent_layout = self.frame_actions.parent().layout()
            if parent_layout:
                idx = parent_layout.indexOf(self.frame_actions)
                if idx >= 0:
                    parent_layout.removeWidget(self.frame_actions)
        
        # Re-add to horizontalLayout_actions_container if not already there
        if self.horizontalLayout_actions_container.indexOf(self.frame_actions) < 0:
            self.frame_actions.setParent(self.dockWidgetContents)
            self.horizontalLayout_actions_container.addWidget(self.frame_actions)
        
        logger.info("Restored original layout from side action bar")

    def _setup_exploring_tab_widgets(self):
        """
        Configure widgets for the Exploring tab.
        
        Sets up checkableComboBox for feature selection and configures mFieldExpressionWidget
        for single/multiple/custom selection modes. Layer initialization is deferred to
        manage_interactions() to prevent blocking during project load.
        """
        # Insert the checkableComboBox into the horizontal layout for multiple selection
        # The layout contains the order by button, we insert the combobox before it
        layout = self.horizontalLayout_exploring_multiple_feature_picker
        layout.insertWidget(0, self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection)

        # Configure QgsFieldExpressionWidget to allow all field types (except geometry)
        # QgsFieldProxyModel.AllTypes includes all field types
        # We exclude only geometry fields using ~SkipGeometry filter
        field_filters = QgsFieldProxyModel.AllTypes
        self.mFieldExpressionWidget_exploring_single_selection.setFilters(field_filters)
        self.mFieldExpressionWidget_exploring_multiple_selection.setFilters(field_filters)
        self.mFieldExpressionWidget_exploring_custom_selection.setFilters(field_filters)
        
        # NOTE: setLayer() calls are deferred to manage_interactions() via _deferred_manage_interactions()
        # to prevent blocking during project load. The old synchronous calls here caused freezes.
        
        # Setup direct signal connections for fieldChanged -> display expression sync
        # These bypass the unreliable manageSignal/isSignalConnected system
        self._setup_expression_widget_direct_connections()

    def _setup_expression_widget_direct_connections(self):
        """
        Setup direct signal connections for all QgsFieldExpressionWidget widgets.
        
        This method establishes direct connections between fieldChanged signals and
        the display expression update for associated FeaturePicker widgets.
        
        We bypass the manageSignal/isSignalConnected system because isSignalConnected()
        is unreliable for tracking specific handler connections.
        
        PERFORMANCE: Uses debounced handlers to prevent excessive recomputation
        when the user types quickly or makes rapid changes to complex expressions.
        """
        # SINGLE SELECTION: mFieldExpressionWidget -> mFeaturePickerWidget
        def on_single_field_changed(field_name):
            self._schedule_expression_change("single_selection", field_name)
        
        self.mFieldExpressionWidget_exploring_single_selection.fieldChanged.connect(on_single_field_changed)
        
        # MULTIPLE SELECTION: mFieldExpressionWidget -> checkableComboBoxFeaturesListPickerWidget
        def on_multiple_field_changed(field_name):
            self._schedule_expression_change("multiple_selection", field_name)
        
        self.mFieldExpressionWidget_exploring_multiple_selection.fieldChanged.connect(on_multiple_field_changed)
        
        # CUSTOM SELECTION: mFieldExpressionWidget (no FeaturePicker to update, but may have other uses)
        def on_custom_field_changed(field_name):
            self._schedule_expression_change("custom_selection", field_name)
        
        self.mFieldExpressionWidget_exploring_custom_selection.fieldChanged.connect(on_custom_field_changed)
    
    def _schedule_expression_change(self, groupbox: str, expression: str):
        """
        Schedule a debounced expression change.
        
        This method stores the pending change and restarts the debounce timer.
        The actual change will only be executed after the debounce delay (450ms)
        has passed without new changes, preventing excessive recomputation.
        
        Args:
            groupbox: The groupbox type ('single_selection', 'multiple_selection', 'custom_selection')
            expression: The new expression value
        """
        # Store pending change
        self._pending_expression_change = (groupbox, expression)
        
        # Show loading indicator immediately for user feedback
        self._set_expression_loading_state(True, groupbox)
        
        # Restart debounce timer
        self._expression_debounce_timer.start()
        
        logger.debug(f"Scheduled expression change for {groupbox}: {expression[:50] if expression else 'None'}...")
    
    def _execute_debounced_expression_change(self):
        """
        Execute the pending expression change after debounce delay.
        
        Called by the debounce timer when the user has stopped making changes.
        This method applies the expression change and triggers the appropriate
        data refresh operations.
        """
        if self._pending_expression_change is None:
            self._set_expression_loading_state(False)
            return
        
        groupbox, expression = self._pending_expression_change
        self._pending_expression_change = None
        
        logger.debug(f"Executing debounced expression change for {groupbox}")
        
        try:
            # Build property key for layer_property_changed
            property_key = f"{groupbox}_expression"
            
            # Create custom functions that trigger source params changed
            custom_functions = {
                "ON_CHANGE": lambda x: self._execute_expression_params_change(groupbox)
            }
            
            # Call the original handler
            self.layer_property_changed(property_key, expression, custom_functions)
            
        except Exception as e:
            logger.error(f"Error executing debounced expression change: {e}")
            self._set_expression_loading_state(False)
    
    def _execute_expression_params_change(self, groupbox: str):
        """
        Execute the expression params change with caching and optimization.
        
        This method is called after the debounce delay and handles:
        - Cache lookup to avoid redundant computations
        - Actual data refresh via exploring_source_params_changed
        - Loading state cleanup
        
        Args:
            groupbox: The groupbox type
        """
        try:
            # Call the standard source params changed
            self.exploring_source_params_changed(groupbox_override=groupbox)
        finally:
            # Clear loading state
            self._set_expression_loading_state(False, groupbox)
    
    def _set_expression_loading_state(self, loading: bool, groupbox: str = None):
        """
        Set the loading state for expression widgets.
        
        Updates the UI to show/hide loading indicators and provides
        visual feedback during complex expression evaluation.
        
        Args:
            loading: True to show loading state, False to hide
            groupbox: Optional groupbox to update (None for all)
        """
        self._expression_loading = loading
        
        try:
            # Update cursor for the relevant widgets
            cursor = Qt.WaitCursor if loading else Qt.PointingHandCursor
            
            widgets_to_update = []
            if groupbox == "single_selection" or groupbox is None:
                widgets_to_update.append(self.mFieldExpressionWidget_exploring_single_selection)
                widgets_to_update.append(self.mFeaturePickerWidget_exploring_single_selection)
            if groupbox == "multiple_selection" or groupbox is None:
                widgets_to_update.append(self.mFieldExpressionWidget_exploring_multiple_selection)
                widgets_to_update.append(self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection)
            if groupbox == "custom_selection" or groupbox is None:
                widgets_to_update.append(self.mFieldExpressionWidget_exploring_custom_selection)
            
            for widget in widgets_to_update:
                if widget and hasattr(widget, 'setCursor'):
                    widget.setCursor(cursor)
                    
        except Exception as e:
            logger.debug(f"Could not update loading state cursor: {e}")
    
    def _get_cached_expression_result(self, layer_id: str, expression: str):
        """
        Get cached result for an expression if available and not expired.
        
        Args:
            layer_id: The layer ID
            expression: The expression string
            
        Returns:
            Cached result tuple (features, timestamp) or None if not cached/expired
        """
        import time
        
        cache_key = (layer_id, expression)
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
        """
        Cache an expression evaluation result.
        
        Args:
            layer_id: The layer ID
            expression: The expression string
            features: The features result to cache
        """
        import time
        
        # Enforce cache size limit (LRU eviction)
        if len(self._expression_cache) >= self._expression_cache_max_size:
            # Remove oldest entry
            oldest_key = min(self._expression_cache.keys(), 
                           key=lambda k: self._expression_cache[k][1])
            del self._expression_cache[oldest_key]
        
        cache_key = (layer_id, expression)
        self._expression_cache[cache_key] = (features, time.time())
    
    def invalidate_expression_cache(self, layer_id: str = None):
        """
        Invalidate expression cache entries.
        
        Args:
            layer_id: If provided, only invalidate cache for this layer.
                     If None, invalidate entire cache.
        """
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
        """
        Configure widgets for the Filtering tab.
        
        Sets up comboBox_filtering_current_layer (VectorLayer filter), creates and configures
        checkableComboBoxLayer_filtering_layers_to_filter. Layer initialization is deferred
        to manage_interactions() to prevent blocking during project load.
        """
        # Filter comboBox_filtering_current_layer to show only vector layers
        self.comboBox_filtering_current_layer.setFilters(QgsMapLayerProxyModel.VectorLayer)
        
        # NOTE: setLayer() and backend indicator update are deferred to manage_interactions()
        # via _deferred_manage_interactions() to prevent blocking during project load.

        # Create custom checkable combobox for layers to filter
        # Parent must be dockWidgetContents, not self (the dock widget), to avoid widget appearing in dock title bar
        self.checkableComboBoxLayer_filtering_layers_to_filter = QgsCheckableComboBoxLayer(self.dockWidgetContents)
        
        # Insert into layout - position just above verticalSpacer_filtering_values_search_bottom (index 2)
        layout = self.verticalLayout_filtering_values
        layout.insertWidget(2, self.checkableComboBoxLayer_filtering_layers_to_filter)
        
        # Apply height constraints (these widgets are created before apply_dynamic_dimensions())
        from .modules.ui_config import UIConfig
        try:
            combobox_height = UIConfig.get_config('combobox', 'height')
            self.checkableComboBoxLayer_filtering_layers_to_filter.setMinimumHeight(combobox_height)
            self.checkableComboBoxLayer_filtering_layers_to_filter.setMaximumHeight(combobox_height)
            self.checkableComboBoxLayer_filtering_layers_to_filter.setSizePolicy(
                self.checkableComboBoxLayer_filtering_layers_to_filter.sizePolicy().horizontalPolicy(),
                QtWidgets.QSizePolicy.Fixed
            )
        except Exception as e:
            logger.debug(f"Could not set height for filtering checkable combobox: {e}")

    def _setup_exporting_tab_widgets(self):
        """
        Configure widgets for the Exporting tab.
        
        Creates and configures checkableComboBoxLayer_exporting_layers, inserts it into layout,
        and sets up map canvas selection color.
        """
        # Create custom checkable combobox for exporting layers
        # Parent must be EXPORTING widget, not self (the dock widget)
        self.checkableComboBoxLayer_exporting_layers = QgsCheckableComboBoxLayer(self.EXPORTING)
        
        # Insert into verticalLayout_exporting_values (the values column in EXPORTING tab)
        # verticalLayout_exporting_values contains: projection, spacer, styles, spacer, datatype, etc.
        # We insert at index 0 to put it at the top, then add a spacer to align with keys
        if hasattr(self, 'verticalLayout_exporting_values'):
            self.verticalLayout_exporting_values.insertWidget(0, self.checkableComboBoxLayer_exporting_layers)
            # Add spacer after combobox to align with keys spacer (Expanding like keys)
            spacer_after_layers = QtWidgets.QSpacerItem(20, 4, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
            self.verticalLayout_exporting_values.insertItem(1, spacer_after_layers)
            logger.debug("Exporting layers combobox inserted into verticalLayout_exporting_values")
        
        # Apply height constraints (these widgets are created before apply_dynamic_dimensions())
        from .modules.ui_config import UIConfig
        try:
            combobox_height = UIConfig.get_config('combobox', 'height')
            self.checkableComboBoxLayer_exporting_layers.setMinimumHeight(combobox_height)
            self.checkableComboBoxLayer_exporting_layers.setMaximumHeight(combobox_height)
            self.checkableComboBoxLayer_exporting_layers.setSizePolicy(
                self.checkableComboBoxLayer_exporting_layers.sizePolicy().horizontalPolicy(),
                QtWidgets.QSizePolicy.Fixed
            )
        except Exception as e:
            logger.debug(f"Could not set height for exporting checkable combobox: {e}")
        
        # Disable all EXPORTING pushbuttons by default (will be enabled when plugin is initialized)
        # This matches the behavior of FILTERING tab widgets
        if hasattr(self, 'pushButton_checkable_exporting_layers'):
            self.pushButton_checkable_exporting_layers.setEnabled(False)
        if hasattr(self, 'pushButton_checkable_exporting_projection'):
            self.pushButton_checkable_exporting_projection.setEnabled(False)
        if hasattr(self, 'pushButton_checkable_exporting_styles'):
            self.pushButton_checkable_exporting_styles.setEnabled(False)
        if hasattr(self, 'pushButton_checkable_exporting_datatype'):
            self.pushButton_checkable_exporting_datatype.setEnabled(False)
        if hasattr(self, 'pushButton_checkable_exporting_output_folder'):
            self.pushButton_checkable_exporting_output_folder.setEnabled(False)
        if hasattr(self, 'pushButton_checkable_exporting_zip'):
            self.pushButton_checkable_exporting_zip.setEnabled(False)
        
        # Configure map canvas selection color
        self.iface.mapCanvas().setSelectionColor(QColor(237, 97, 62, 75))

    def _index_to_combine_operator(self, index):
        """
        Convert combobox index to SQL combine operator.
        
        This ensures language-independent operator handling.
        The combobox items are:
          Index 0: AND
          Index 1: AND NOT
          Index 2: OR
        
        Args:
            index (int): Combobox index
            
        Returns:
            str: SQL operator ('AND', 'AND NOT', 'OR') or 'AND' as default
        """
        operators = {0: 'AND', 1: 'AND NOT', 2: 'OR'}
        return operators.get(index, 'AND')
    
    def _combine_operator_to_index(self, operator):
        """
        Convert SQL combine operator to combobox index.
        
        FIX v2.5.12: Handle translated operator values (ET, OU, NON) from
        older project files or when QGIS locale is non-English.
        
        Args:
            operator (str): SQL operator or translated equivalent
            
        Returns:
            int: Combobox index (0=AND, 1=AND NOT, 2=OR) or 0 as default
        """
        if not operator:
            return 0  # Default to AND
        
        op_upper = operator.upper().strip()
        
        # Map of all possible operator values (including translations) to indices
        operator_map = {
            # English (canonical)
            'AND': 0,
            'AND NOT': 1,
            'OR': 2,
            # French
            'ET': 0,
            'ET NON': 1,
            'OU': 2,
            # German
            'UND': 0,
            'UND NICHT': 1,
            'ODER': 2,
            # Spanish
            'Y': 0,
            'Y NO': 1,
            'O': 2,
            # Italian
            'E': 0,
            'E NON': 1,
            # Portuguese
            'E NÃO': 1,
        }
        
        return operator_map.get(op_upper, 0)

    def dockwidget_widgets_configuration(self):

        self.layer_properties_tuples_dict =   {
                                                "is":(("exploring","is_selecting"),("exploring","is_tracking"),("exploring","is_linking")),
                                                "selection_expression":(("exploring","single_selection_expression"),("exploring","multiple_selection_expression"),("exploring","custom_selection_expression")),
                                                "layers_to_filter":(("filtering","has_layers_to_filter"),("filtering","layers_to_filter")),
                                                "combine_operator":(("filtering", "has_combine_operator"), ("filtering", "source_layer_combine_operator"),("filtering", "other_layers_combine_operator")),
                                                "buffer_type":(("filtering","has_buffer_type"),("filtering","buffer_type"),("filtering","buffer_segments")),
                                                "buffer_value":(("filtering", "has_buffer_value"),("filtering","has_buffer_type"),("filtering", "buffer_value"),("filtering", "buffer_value_expression"),("filtering", "buffer_value_property")),
                                                "geometric_predicates":(("filtering","has_geometric_predicates"),("filtering","has_buffer_value"),("filtering","has_buffer_type"),("filtering","geometric_predicates"))
                                                }
        
        self.export_properties_tuples_dict =   {
                                                "layers_to_export":(("exporting","has_layers_to_export"),("exporting","layers_to_export")),
                                                "projection_to_export":(("exporting","has_projection_to_export"),("exporting","projection_to_export")),
                                                "styles_to_export":(("exporting","has_styles_to_export"),("exporting","styles_to_export")),
                                                "datatype_to_export":(("exporting","has_datatype_to_export"),("exporting","datatype_to_export")),
                                                "output_folder_to_export":(("exporting","has_output_folder_to_export"),("exporting","batch_output_folder"),("exporting","output_folder_to_export")),
                                                "zip_to_export":(("exporting", "has_zip_to_export"), ("exporting", "batch_zip"), ("exporting", "zip_to_export")),
                                                "batch_output_folder":(("exporting","has_output_folder_to_export"),("exporting","batch_output_folder"),("exporting","output_folder_to_export")),
                                                "batch_zip":(("exporting", "has_zip_to_export"), ("exporting", "batch_zip"), ("exporting", "zip_to_export"))
                                                }

        self.widgets = {"DOCK":{}, "ACTION":{}, "EXPLORING":{}, "FILTERING":{}, "EXPORTING":{}, "QGIS":{}}
            
        # CRITICAL: GroupBoxes use "toggled" signal to detect checkbox state changes
        # and "collapsedStateChanged" (arrow) signal for collapse/expand via arrow
        # The toggled signal receives 'checked' (bool) - True when checked, False when unchecked
        # We only activate a groupbox when it becomes CHECKED (checked=True)
        self.widgets["DOCK"] = {
                                "SINGLE_SELECTION":{"TYPE":"GroupBox", "WIDGET":self.mGroupBox_exploring_single_selection, "SIGNALS":[("toggled", lambda checked, x='single_selection': self._on_groupbox_clicked(x, checked)), ("collapsedStateChanged", lambda collapsed, x='single_selection': self._on_groupbox_collapse_changed(x, collapsed))]},
                                "MULTIPLE_SELECTION":{"TYPE":"GroupBox","WIDGET":self.mGroupBox_exploring_multiple_selection, "SIGNALS":[("toggled", lambda checked, x='multiple_selection': self._on_groupbox_clicked(x, checked)), ("collapsedStateChanged", lambda collapsed, x='multiple_selection': self._on_groupbox_collapse_changed(x, collapsed))]},
                                "CUSTOM_SELECTION":{"TYPE":"GroupBox","WIDGET":self.mGroupBox_exploring_custom_selection, "SIGNALS":[("toggled", lambda checked, x='custom_selection': self._on_groupbox_clicked(x, checked)), ("collapsedStateChanged", lambda collapsed, x='custom_selection': self._on_groupbox_collapse_changed(x, collapsed))]},
                                "CONFIGURATION_TREE_VIEW":{"TYPE":"JsonTreeView","WIDGET":self.config_view, "SIGNALS":[("collapsed", None),("expanded", None)]},
                                "CONFIGURATION_MODEL":{"TYPE":"JsonModel","WIDGET":self.config_model, "SIGNALS":[("itemChanged", None)]},
                                "CONFIGURATION_BUTTONBOX":{"TYPE":"DialogButtonBox","WIDGET":self.buttonBox, "SIGNALS":[("accepted", None),("rejected", None)]},
                                "TOOLS":{"TYPE":"ToolBox","WIDGET":self.toolBox_tabTools, "SIGNALS":[("currentChanged", self.select_tabTools_index)]}
                                }   

        self.widgets["ACTION"] = {
                                "FILTER":{"TYPE":"PushButton", "WIDGET":self.pushButton_action_filter, "SIGNALS":[("clicked", lambda state, x='filter': self.launchTaskEvent(state, x))], "ICON":None},
                                "UNDO_FILTER":{"TYPE":"PushButton", "WIDGET":self.pushButton_action_undo_filter, "SIGNALS":[("clicked", lambda state, x='undo': self.launchTaskEvent(state, x))], "ICON":None},
                                "REDO_FILTER":{"TYPE":"PushButton", "WIDGET":self.pushButton_action_redo_filter, "SIGNALS":[("clicked", lambda state, x='redo': self.launchTaskEvent(state, x))], "ICON":None},
                                "UNFILTER":{"TYPE":"PushButton", "WIDGET":self.pushButton_action_unfilter, "SIGNALS":[("clicked", lambda state, x='unfilter': self.launchTaskEvent(state, x))], "ICON":None},
                                "EXPORT":{"TYPE":"PushButton", "WIDGET":self.pushButton_action_export, "SIGNALS":[("clicked", lambda state, x='export': self.launchTaskEvent(state, x))], "ICON":None},
                                "ABOUT":{"TYPE":"PushButton", "WIDGET":self.pushButton_action_about, "SIGNALS":[("clicked", self.open_project_page)], "ICON":None}
                                }        


        self.widgets["EXPLORING"] = {
                                    "IDENTIFY":{"TYPE":"PushButton", "WIDGET":self.pushButton_exploring_identify, "SIGNALS":[("clicked", self.exploring_identify_clicked)], "ICON":None},
                                    "ZOOM":{"TYPE":"PushButton", "WIDGET":self.pushButton_exploring_zoom, "SIGNALS":[("clicked", self.exploring_zoom_clicked)], "ICON":None},
                                    "IS_SELECTING":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exploring_selecting, "SIGNALS":[("toggled", lambda state, x='is_selecting', custom_functions={"ON_TRUE": lambda x: self.exploring_select_features(), "ON_FALSE": lambda x: self.exploring_deselect_features()}: self.layer_property_changed(x, state, custom_functions))], "ICON":None},
                                    "IS_TRACKING":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exploring_tracking, "SIGNALS":[("toggled", lambda state, x='is_tracking', custom_functions={"ON_TRUE": lambda x: self.exploring_zoom_clicked()}: self.layer_property_changed(x, state, custom_functions))], "ICON":None},
                                    "IS_LINKING":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exploring_linking_widgets, "SIGNALS":[("toggled", lambda state, x='is_linking', custom_functions={"ON_CHANGE": lambda x: self.exploring_link_widgets()}: self.layer_property_changed(x, state, custom_functions))], "ICON":None},
                                    "RESET_ALL_LAYER_PROPERTIES":{"TYPE":"PushButton", "WIDGET":self.pushButton_exploring_reset_layer_properties, "SIGNALS":[("clicked", lambda: self.resetLayerVariableEvent())], "ICON":None},
                                    
                                    "SINGLE_SELECTION_FEATURES":{"TYPE":"FeatureComboBox", "WIDGET":self.mFeaturePickerWidget_exploring_single_selection, "SIGNALS":[("featureChanged", self.exploring_features_changed)]},
                                    # NOTE: fieldChanged signal handled by _setup_expression_widget_direct_connections() with debounce
                                    "SINGLE_SELECTION_EXPRESSION":{"TYPE":"QgsFieldExpressionWidget", "WIDGET":self.mFieldExpressionWidget_exploring_single_selection, "SIGNALS":[("fieldChanged", None)]},
                                    
                                    "MULTIPLE_SELECTION_FEATURES":{"TYPE":"CustomCheckableFeatureComboBox", "WIDGET":self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection, "SIGNALS":[("updatingCheckedItemList", self.exploring_features_changed),("filteringCheckedItemList", lambda: self.exploring_source_params_changed(groupbox_override="multiple_selection"))]},
                                    # NOTE: fieldChanged signal handled by _setup_expression_widget_direct_connections() with debounce
                                    "MULTIPLE_SELECTION_EXPRESSION":{"TYPE":"QgsFieldExpressionWidget", "WIDGET":self.mFieldExpressionWidget_exploring_multiple_selection, "SIGNALS":[("fieldChanged", None)]},
                                    
                                    # NOTE: fieldChanged signal handled by _setup_expression_widget_direct_connections() with debounce
                                    "CUSTOM_SELECTION_EXPRESSION":{"TYPE":"QgsFieldExpressionWidget", "WIDGET":self.mFieldExpressionWidget_exploring_custom_selection, "SIGNALS":[("fieldChanged", None)]}
                                    }


        self.widgets["FILTERING"] = {
                                    "AUTO_CURRENT_LAYER":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_filtering_auto_current_layer, "SIGNALS":[("clicked", lambda state : self.filtering_auto_current_layer_changed(state))], "ICON":None},
                                    "HAS_LAYERS_TO_FILTER":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_filtering_layers_to_filter, "SIGNALS":[("clicked", lambda state, x='has_layers_to_filter': self.layer_property_changed(x, state))], "ICON":None},
                                    "HAS_COMBINE_OPERATOR":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_filtering_current_layer_combine_operator, "SIGNALS":[("clicked", lambda state, x='has_combine_operator': self.layer_property_changed(x, state))], "ICON":None},
                                    "HAS_GEOMETRIC_PREDICATES":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_filtering_geometric_predicates, "SIGNALS":[("clicked", lambda state, x='has_geometric_predicates': self.layer_property_changed(x, state))], "ICON":None},
                                    "HAS_BUFFER_VALUE":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_filtering_buffer_value, "SIGNALS":[("clicked", lambda state, x='has_buffer_value', custom_functions={"ON_CHANGE": lambda x: self.filtering_buffer_property_changed()}: self.layer_property_changed(x, state, custom_functions))], "ICON":None},
                                    "HAS_BUFFER_TYPE":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_filtering_buffer_type, "SIGNALS":[("clicked", lambda state, x='has_buffer_type', custom_functions={"ON_CHANGE": lambda x: self.filtering_buffer_property_changed()}: self.layer_property_changed(x, state, custom_functions))], "ICON":None},
                                    "CURRENT_LAYER":{"TYPE":"ComboBox", "WIDGET":self.comboBox_filtering_current_layer, "SIGNALS":[("layerChanged", self.current_layer_changed)]},
                                    "LAYERS_TO_FILTER":{"TYPE":"CustomCheckableLayerComboBox", "WIDGET":self.checkableComboBoxLayer_filtering_layers_to_filter, "CUSTOM_LOAD_FUNCTION": lambda x: self.get_layers_to_filter(), "SIGNALS":[("checkedItemsChanged", lambda state, custom_functions={"CUSTOM_DATA": lambda x: self.get_layers_to_filter()}, x='layers_to_filter': self.layer_property_changed(x, state, custom_functions))]},
                                    "SOURCE_LAYER_COMBINE_OPERATOR":{"TYPE":"ComboBox", "WIDGET":self.comboBox_filtering_source_layer_combine_operator, "SIGNALS":[("currentIndexChanged", lambda index, x='source_layer_combine_operator': self.layer_property_changed(x, self._index_to_combine_operator(index)))]},
                                    "OTHER_LAYERS_COMBINE_OPERATOR":{"TYPE":"ComboBox", "WIDGET":self.comboBox_filtering_other_layers_combine_operator, "SIGNALS":[("currentIndexChanged", lambda index, x='other_layers_combine_operator': self.layer_property_changed(x, self._index_to_combine_operator(index)))]},
                                    "GEOMETRIC_PREDICATES":{"TYPE":"CheckableComboBox", "WIDGET":self.comboBox_filtering_geometric_predicates, "SIGNALS":[("checkedItemsChanged", lambda state, x='geometric_predicates': self.layer_property_changed(x, state))]},
                                    "BUFFER_VALUE":{"TYPE":"QgsDoubleSpinBox", "WIDGET":self.mQgsDoubleSpinBox_filtering_buffer_value, "SIGNALS":[("valueChanged", lambda state, x='buffer_value': self.layer_property_changed_with_buffer_style(x, state))]},
                                    "BUFFER_VALUE_PROPERTY":{"TYPE":"PropertyOverrideButton", "WIDGET":self.mPropertyOverrideButton_filtering_buffer_value_property, "SIGNALS":[("changed", lambda state=None, x='buffer_value_property', custom_functions={"ON_CHANGE": lambda x: self.filtering_buffer_property_changed(), "CUSTOM_DATA": lambda x: self.get_buffer_property_state()}: self.layer_property_changed(x, state, custom_functions))]},
                                    "BUFFER_TYPE":{"TYPE":"ComboBox", "WIDGET":self.comboBox_filtering_buffer_type, "SIGNALS":[("currentTextChanged", lambda state, x='buffer_type': self.layer_property_changed(x, state))]},
                                    "BUFFER_SEGMENTS":{"TYPE":"QgsSpinBox", "WIDGET":self.mQgsSpinBox_filtering_buffer_segments, "SIGNALS":[("valueChanged", lambda state, x='buffer_segments': self.layer_property_changed(x, state))]},
                                    }
        
        self.widgets["EXPORTING"] = {
                                    "HAS_LAYERS_TO_EXPORT":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exporting_layers, "SIGNALS":[("clicked", lambda state, x='has_layers_to_export': self.project_property_changed(x, state))], "ICON":None},
                                    "HAS_PROJECTION_TO_EXPORT":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exporting_projection, "SIGNALS":[("clicked", lambda state, x='has_projection_to_export': self.project_property_changed(x, state))], "ICON":None},
                                    "HAS_STYLES_TO_EXPORT":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exporting_styles, "SIGNALS":[("clicked", lambda state, x='has_styles_to_export': self.project_property_changed(x, state))], "ICON":None},
                                    "HAS_DATATYPE_TO_EXPORT":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exporting_datatype, "SIGNALS":[("clicked", lambda state, x='has_datatype_to_export': self.project_property_changed(x, state))], "ICON":None},
                                    "HAS_OUTPUT_FOLDER_TO_EXPORT":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exporting_output_folder, "SIGNALS":[("clicked", lambda state, x='has_output_folder_to_export', custom_functions={"ON_CHANGE": lambda x: self.dialog_export_output_path()}: self.project_property_changed(x, state, custom_functions))], "ICON":None},
                                    "HAS_ZIP_TO_EXPORT":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exporting_zip, "SIGNALS":[("clicked", lambda state, x='has_zip_to_export', custom_functions={"ON_CHANGE": lambda x: self.dialog_export_output_pathzip()}: self.project_property_changed(x, state, custom_functions))], "ICON":None},
                                    "BATCH_OUTPUT_FOLDER":{"TYPE":"CheckBox", "WIDGET":self.checkBox_batch_exporting_output_folder, "SIGNALS":[("stateChanged", lambda state, x='batch_output_folder': self.project_property_changed(x, bool(state)))], "ICON":None},
                                    "BATCH_ZIP":{"TYPE":"CheckBox", "WIDGET":self.checkBox_batch_exporting_zip, "SIGNALS":[("stateChanged", lambda state, x='batch_zip': self.project_property_changed(x, bool(state)))], "ICON":None},
                                    "LAYERS_TO_EXPORT":{"TYPE":"CustomCheckableLayerComboBox", "WIDGET":self.checkableComboBoxLayer_exporting_layers, "CUSTOM_LOAD_FUNCTION": lambda x: self.get_layers_to_export(), "SIGNALS":[("checkedItemsChanged", lambda state, custom_functions={"CUSTOM_DATA": lambda x: self.get_layers_to_export()}, x='layers_to_export': self.project_property_changed(x, state, custom_functions))]},
                                    "PROJECTION_TO_EXPORT":{"TYPE":"QgsProjectionSelectionWidget", "WIDGET":self.mQgsProjectionSelectionWidget_exporting_projection, "SIGNALS":[("crsChanged", lambda state, x='projection_to_export', custom_functions={"CUSTOM_DATA": lambda x: self.get_current_crs_authid()}: self.project_property_changed(x, state, custom_functions))]},
                                    "STYLES_TO_EXPORT":{"TYPE":"ComboBox", "WIDGET":self.comboBox_exporting_styles, "SIGNALS":[("currentTextChanged", lambda state, x='styles_to_export': self.project_property_changed(x, state))]},
                                    "DATATYPE_TO_EXPORT":{"TYPE":"ComboBox", "WIDGET":self.comboBox_exporting_datatype, "SIGNALS":[("currentTextChanged", lambda state, x='datatype_to_export': self.project_property_changed(x, state))]},
                                    "OUTPUT_FOLDER_TO_EXPORT":{"TYPE":"LineEdit", "WIDGET":self.lineEdit_exporting_output_folder, "SIGNALS":[("textEdited", lambda state, x='output_folder_to_export', custom_functions={"ON_CHANGE": lambda x: self.reset_export_output_path()}: self.project_property_changed(x, state, custom_functions))]},
                                    "ZIP_TO_EXPORT":{"TYPE":"LineEdit", "WIDGET":self.lineEdit_exporting_zip, "SIGNALS":[("textEdited", lambda state, x='zip_to_export', custom_functions={"ON_CHANGE": lambda x: self.reset_export_output_pathzip()}: self.project_property_changed(x, state, custom_functions))]}
                                    }
            

    
        self.widgets["QGIS"] = {
                                "LAYER_TREE_VIEW":{"TYPE":"LayerTreeView", "WIDGET":self.iface.layerTreeView(), "SIGNALS":[("currentLayerChanged", self.current_layer_changed)]}
                                }
        
        self.widgets_initialized = True
        logger.info(f"✓ Widgets fully initialized with {len(self.PROJECT_LAYERS)} layers")
        
        # CRITICAL FIX: Connect selectionChanged signal for initial current_layer
        # This ensures tracking/selecting works even without changing layers first
        if self.current_layer is not None and self.current_layer_selection_connection is None:
            try:
                self.current_layer.selectionChanged.connect(self.on_layer_selection_changed)
                self.current_layer_selection_connection = True
                logger.info(f"Connected selectionChanged signal for initial layer '{self.current_layer.name()}'")
            except (TypeError, RuntimeError) as e:
                logger.warning(f"Could not connect selectionChanged for initial layer: {e}")
        
        # NEW: Emit signal to notify that widgets are ready
        # This allows FilterMateApp to safely proceed with layer operations
        logger.debug("Emitting widgetsInitialized signal")
        self.widgetsInitialized.emit()
        
        # STABILITY IMPROVEMENT: Add F5 shortcut to force reload layers
        # This helps users recover when project change doesn't properly reload layers
        self._setup_keyboard_shortcuts()
        
        # CRITICAL: If layers were updated before widgets_initialized, refresh UI now
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
        """Track configuration changes without applying them immediately"""

        if self.widgets_initialized is True:

            index = input_data.index()
            item = input_data

            item_key = self.config_view.model.itemFromIndex(index.siblingAtColumn(0))

            items_keys_values_path = []

            while item_key is not None:
                items_keys_values_path.append(item_key.data(QtCore.Qt.DisplayRole))
                item_key = item_key.parent()

            items_keys_values_path.reverse()
            
            # Store change for later application
            self.pending_config_changes.append({
                'path': items_keys_values_path,
                'index': index,
                'item': item
            })
            self.config_changes_pending = True
            
            # Enable OK/Cancel buttons when changes are pending
            if hasattr(self, 'buttonBox'):
                self.buttonBox.setEnabled(True)
                logger.info("Configuration buttons enabled (changes pending)")
            
            # Mark that changes are pending (visual feedback could be added)
            logger.info(f"Configuration change pending: {' → '.join(items_keys_values_path)}")
            
            # Note: Changes are NOT applied immediately
            # They will be applied when user clicks OK button
    
    def _apply_theme_change(self, change, changes_summary):
        """
        Apply ACTIVE_THEME configuration change.
        
        Detects theme from config change and applies it using StyleLoader.
        Supports 'auto', 'default', 'dark', and 'light' themes.
        """
        items_keys_values_path = change['path']
        index = change['index']
        
        if 'ACTIVE_THEME' not in items_keys_values_path:
            return
        
        try:
            # Get the new theme value from the edited item
            value_item = self.config_view.model.itemFromIndex(index.siblingAtColumn(1))
            value_data = value_item.data(QtCore.Qt.UserRole)
            
            # Handle ChoicesType format (dict with 'value' and 'choices')
            if isinstance(value_data, dict) and 'value' in value_data:
                new_theme_value = value_data['value']
            else:
                # Fallback for string format (backward compatibility)
                new_theme_value = value_item.data(QtCore.Qt.DisplayRole) if value_item else None
            
            if new_theme_value:
                logger.info(f"ACTIVE_THEME changed to: {new_theme_value}")
                
                # Apply new theme
                from .modules.ui_styles import StyleLoader
                
                if new_theme_value == 'auto':
                    # Auto-detect theme from QGIS
                    detected_theme = StyleLoader.detect_qgis_theme()
                    logger.info(f"Auto-detected QGIS theme: {detected_theme}")
                    StyleLoader.set_theme_from_config(self.dockWidgetContents, self.CONFIG_DATA, detected_theme)
                else:
                    # Apply specified theme (default, dark, light)
                    StyleLoader.set_theme_from_config(self.dockWidgetContents, self.CONFIG_DATA, new_theme_value)
                
                changes_summary.append(f"Theme: {new_theme_value}")
                
        except Exception as e:
            logger.error(f"Error applying ACTIVE_THEME change: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _apply_ui_profile_change(self, change, changes_summary):
        """
        Apply UI_PROFILE configuration change.
        
        Updates UIConfig with new profile (compact/normal/auto) and re-applies
        dynamic dimensions. Shows confirmation message to user.
        """
        items_keys_values_path = change['path']
        index = change['index']
        
        if 'UI_PROFILE' not in items_keys_values_path:
            return
        
        try:
            # Get the new profile value from the edited item
            value_item = self.config_view.model.itemFromIndex(index.siblingAtColumn(1))
            value_data = value_item.data(QtCore.Qt.UserRole)
            
            # Handle ChoicesType format (dict with 'value' and 'choices')
            if isinstance(value_data, dict) and 'value' in value_data:
                new_profile_value = value_data['value']
            else:
                # Fallback for string format (backward compatibility)
                new_profile_value = value_item.data(QtCore.Qt.DisplayRole) if value_item else None
            
            if new_profile_value:
                logger.info(f"UI_PROFILE changed to: {new_profile_value}")
                
                # Update UIConfig with new profile
                if UI_CONFIG_AVAILABLE:
                    from .modules.ui_config import UIConfig, DisplayProfile
                    
                    if new_profile_value == 'compact':
                        UIConfig.set_profile(DisplayProfile.COMPACT)
                        logger.info("Switched to COMPACT profile")
                    elif new_profile_value == 'normal':
                        UIConfig.set_profile(DisplayProfile.NORMAL)
                        logger.info("Switched to NORMAL profile")
                    elif new_profile_value == 'auto':
                        # Detect optimal profile based on screen size
                        detected_profile = UIConfig.detect_optimal_profile()
                        UIConfig.set_profile(detected_profile)
                        logger.info(f"Auto-detected profile: {detected_profile.value}")
                    
                    # Re-apply dynamic dimensions with new profile
                    self.apply_dynamic_dimensions()
                    
                    # Message removed - profile change is visible in UI
                    profile_display = UIConfig.get_profile_name().upper()
                    logger.info(f"UI profile changed to {profile_display} mode")
                    
                    changes_summary.append(f"Profile: {new_profile_value}")
                else:
                    logger.warning("UI_CONFIG not available - cannot apply profile changes")
                    
        except Exception as e:
            logger.error(f"Error applying UI_PROFILE change: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _apply_action_bar_position_change(self, change, changes_summary):
        """
        Apply ACTION_BAR_POSITION or ACTION_BAR_VERTICAL_ALIGNMENT configuration change.
        
        Updates the action bar layout position/alignment dynamically.
        """
        items_keys_values_path = change['path']
        index = change['index']
        
        # Check if this is a position or alignment change
        is_position_change = 'ACTION_BAR_POSITION' in items_keys_values_path and 'VERTICAL' not in items_keys_values_path
        is_alignment_change = 'ACTION_BAR_VERTICAL_ALIGNMENT' in items_keys_values_path
        
        if not is_position_change and not is_alignment_change:
            return
        
        try:
            # Get the new value from the edited item
            value_item = self.config_view.model.itemFromIndex(index.siblingAtColumn(1))
            value_data = value_item.data(QtCore.Qt.UserRole)
            
            # Handle ChoicesType format (dict with 'value' and 'choices')
            if isinstance(value_data, dict) and 'value' in value_data:
                new_value = value_data['value']
            else:
                # Fallback for string format (backward compatibility)
                new_value = value_item.data(QtCore.Qt.DisplayRole) if value_item else None
            
            if new_value:
                if is_position_change:
                    logger.info(f"ACTION_BAR_POSITION changed to: {new_value}")
                    
                    # Update the config data in memory using helper (handles v1.0 and v2.0 formats)
                    set_config_value(self.CONFIG_DATA, new_value, "APP", "DOCKWIDGET", "ACTION_BAR_POSITION")
                    
                    # Apply the new position
                    self._apply_action_bar_position(new_value)
                    changes_summary.append(f"Action bar position: {new_value}")
                    
                    # Show message that reload is recommended
                    show_info(
                        "FilterMate",
                        QCoreApplication.translate("FilterMateDockWidget", 
                            "Action bar position changed. Use 'Reload Plugin' button for best results.")
                    )
                    
                elif is_alignment_change:
                    logger.info(f"ACTION_BAR_VERTICAL_ALIGNMENT changed to: {new_value}")
                    
                    # Update the config data in memory using helper (handles v1.0 and v2.0 formats)
                    set_config_value(self.CONFIG_DATA, new_value, "APP", "DOCKWIDGET", "ACTION_BAR_VERTICAL_ALIGNMENT")
                    
                    # Re-apply the current position to update alignment
                    current_position = self._get_action_bar_position()
                    if current_position in ('left', 'right'):
                        self._apply_action_bar_position(current_position)
                    changes_summary.append(f"Action bar alignment: {new_value}")
                
                # Show confirmation message
                show_info(
                    "FilterMate",
                    f"Action bar updated successfully."
                )
                    
        except Exception as e:
            logger.error(f"Error applying action bar change: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _apply_export_style_change(self, change, changes_summary):
        """
        Apply STYLES_TO_EXPORT configuration change.
        
        Updates the export style combobox with new value.
        """
        items_keys_values_path = change['path']
        index = change['index']
        
        if 'STYLES_TO_EXPORT' not in items_keys_values_path:
            return
        
        try:
            # Get the new style value from the edited item
            value_item = self.config_view.model.itemFromIndex(index.siblingAtColumn(1))
            value_data = value_item.data(QtCore.Qt.UserRole)
            
            # Handle ChoicesType format (dict with 'value' and 'choices')
            if isinstance(value_data, dict) and 'value' in value_data:
                new_style_value = value_data['value']
            else:
                # Fallback for string format (backward compatibility)
                new_style_value = value_item.data(QtCore.Qt.DisplayRole) if value_item else None
            
            if new_style_value and 'STYLES_TO_EXPORT' in self.widgets.get('EXPORTING', {}):
                logger.info(f"STYLES_TO_EXPORT changed to: {new_style_value}")
                
                # Update the combobox selection
                style_combo = self.widgets["EXPORTING"]["STYLES_TO_EXPORT"]["WIDGET"]
                index_to_set = style_combo.findText(new_style_value)
                if index_to_set >= 0:
                    style_combo.setCurrentIndex(index_to_set)
                    logger.info(f"Export style updated to: {new_style_value}")
                    # Message removed - change visible in combobox
                    
                    changes_summary.append(f"Style: {new_style_value}")
                
        except Exception as e:
            logger.error(f"Error applying STYLES_TO_EXPORT change: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _apply_export_format_change(self, change, changes_summary):
        """
        Apply DATATYPE_TO_EXPORT configuration change.
        
        Updates the export format combobox with new value.
        """
        items_keys_values_path = change['path']
        index = change['index']
        
        if 'DATATYPE_TO_EXPORT' not in items_keys_values_path:
            return
        
        try:
            # Get the new format value from the edited item
            value_item = self.config_view.model.itemFromIndex(index.siblingAtColumn(1))
            value_data = value_item.data(QtCore.Qt.UserRole)
            
            # Handle ChoicesType format (dict with 'value' and 'choices')
            if isinstance(value_data, dict) and 'value' in value_data:
                new_format_value = value_data['value']
            else:
                # Fallback for string format (backward compatibility)
                new_format_value = value_item.data(QtCore.Qt.DisplayRole) if value_item else None
            
            if new_format_value and 'DATATYPE_TO_EXPORT' in self.widgets.get('EXPORTING', {}):
                logger.info(f"DATATYPE_TO_EXPORT changed to: {new_format_value}")
                
                # Update the combobox selection
                format_combo = self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"]
                index_to_set = format_combo.findText(new_format_value)
                if index_to_set >= 0:
                    format_combo.setCurrentIndex(index_to_set)
                    logger.info(f"Export format updated to: {new_format_value}")
                    # Message removed - change visible in combobox
                    
                    changes_summary.append(f"Format: {new_format_value}")
                
        except Exception as e:
            logger.error(f"Error applying DATATYPE_TO_EXPORT change: {e}")
            import traceback
            logger.error(traceback.format_exc())


    def apply_pending_config_changes(self):
        """
        Apply all pending configuration changes when OK button is clicked.
        
        Orchestrates the application of different config change types by delegating
        to specialized methods.
        """
        if not self.config_changes_pending or not self.pending_config_changes:
            logger.info("No pending configuration changes to apply")
            return
        
        logger.info(f"Applying {len(self.pending_config_changes)} pending configuration change(s)")
        
        changes_summary = []
        
        for change in self.pending_config_changes:
            items_keys_values_path = change['path']
            
            # Handle ICONS changes
            if 'ICONS' in items_keys_values_path:
                self.set_widget_icon(items_keys_values_path)
                changes_summary.append(f"Icon: {' → '.join(items_keys_values_path[-2:])}")
            
            # Apply specialized change handlers
            self._apply_theme_change(change, changes_summary)
            self._apply_ui_profile_change(change, changes_summary)
            self._apply_action_bar_position_change(change, changes_summary)
            self._apply_export_style_change(change, changes_summary)
            self._apply_export_format_change(change, changes_summary)
            
            # Save configuration after each change
            self.save_configuration_model()
        
        # Clear pending changes after applying them
        self.pending_config_changes = []
        self.config_changes_pending = False
        
        # Disable OK/Cancel buttons after changes have been applied
        if hasattr(self, 'buttonBox'):
            self.buttonBox.setEnabled(False)
            logger.info("Configuration buttons disabled (changes applied)")
        
        logger.info("All pending configuration changes have been applied and saved")


    def cancel_pending_config_changes(self):
        """Cancel pending configuration changes when Cancel button is clicked"""
        
        if not self.config_changes_pending or not self.pending_config_changes:
            logger.info("No pending configuration changes to cancel")
            return
        
        logger.info(f"Cancelling {len(self.pending_config_changes)} pending configuration change(s)")
        
        # Reload configuration from file to revert changes in tree view
        try:
            config_json_path = ENV_VARS.get('CONFIG_JSON_PATH', self.plugin_dir + '/config/config.json')
            with open(config_json_path, 'r') as infile:
                self.CONFIG_DATA = json.load(infile)
            
            # Recreate model with original data
            self.config_model = JsonModel(
                data=self.CONFIG_DATA, 
                editable_keys=False, 
                editable_values=True, 
                plugin_dir=self.plugin_dir
            )
            
            # Update view
            if hasattr(self, 'config_view') and self.config_view is not None:
                self.config_view.setModel(self.config_model)
                self.config_view.model = self.config_model
            
            # Clear pending changes
            self.pending_config_changes = []
            self.config_changes_pending = False
            
            # Disable buttons after cancelling changes
            if hasattr(self, 'buttonBox'):
                self.buttonBox.setEnabled(False)
                logger.info("Configuration buttons disabled (changes cancelled)")
            
            # Message removed - button state change is sufficient feedback
            logger.info("Configuration changes cancelled successfully")
            
        except Exception as e:
            logger.error(f"Error cancelling configuration changes: {e}")
            import traceback
            logger.error(traceback.format_exc())
            show_error(
                "FilterMate",
                f"Error cancelling changes: {str(e)}"
            )


    def on_config_buttonbox_accepted(self):
        """Called when OK button is clicked"""
        logger.info("Configuration OK button clicked")
        self.apply_pending_config_changes()


    def on_config_buttonbox_rejected(self):
        """Called when Cancel button is clicked"""
        logger.info("Configuration Cancel button clicked")
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
        """Manage the qtreeview model configuration"""

        try:
            # Create model with data
            self.config_model = JsonModel(data=self.CONFIG_DATA, editable_keys=False, editable_values=True, plugin_dir=self.plugin_dir)

            # Create view with model - setModel() is called in JsonView.__init__()
            self.config_view = JsonView(self.config_model, self.plugin_dir)
            
            # Insert into layout
            self.CONFIGURATION.layout().insertWidget(0, self.config_view)

            # Note: setModel() is already called in JsonView constructor - do NOT call again
            # Calling setModel() after insertion can cause Qt crashes

            self.config_view.setAnimated(True)
            self.config_view.setEnabled(True)
            self.config_view.show()
            
            # CRITICAL: Connect itemChanged signal immediately after model creation
            # This ensures changes are detected and OK button is enabled
            self.config_model.itemChanged.connect(self.data_changed_configuration_model)
            logger.info("Configuration model itemChanged signal connected")
            
            # Add Reload Plugin button
            self._setup_reload_button()
            
            # Disable OK/Cancel buttons by default (no changes pending)
            if hasattr(self, 'buttonBox'):
                self.buttonBox.setEnabled(False)
                logger.info("Configuration buttons disabled (no pending changes)")
            
            # Connect OK/Cancel button signals
            if hasattr(self, 'buttonBox'):
                self.buttonBox.accepted.connect(self.on_config_buttonbox_accepted)
                self.buttonBox.rejected.connect(self.on_config_buttonbox_rejected)
                logger.info("Configuration button signals connected")
        except Exception as e:
            logger.error(f"Error creating configuration model: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _setup_reload_button(self):
        """
        Setup the Reload Plugin button in the configuration panel.
        
        This button allows users to reload the plugin to apply layout changes.
        """
        try:
            # Create reload button
            self.pushButton_reload_plugin = QtWidgets.QPushButton("🔄 Reload Plugin")
            self.pushButton_reload_plugin.setObjectName("pushButton_reload_plugin")
            self.pushButton_reload_plugin.setToolTip(QCoreApplication.translate("FilterMate", "Reload the plugin to apply layout changes (action bar position)"))
            self.pushButton_reload_plugin.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
            
            # Style the button
            self.pushButton_reload_plugin.setMinimumHeight(30)
            
            # Connect signal
            self.pushButton_reload_plugin.clicked.connect(self._on_reload_button_clicked)
            
            # Add to configuration layout (before buttonBox)
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
        from qgis.utils import iface
        
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

        self.predicates = ["Intersect","Contain","Disjoint","Equal","Touch","Overlap","Are within","Cross"]
        self.widgets["FILTERING"]["GEOMETRIC_PREDICATES"]["WIDGET"].clear()
        self.widgets["FILTERING"]["GEOMETRIC_PREDICATES"]["WIDGET"].addItems(self.predicates)

    def filtering_populate_buffer_type_combobox(self):
        """Initialize buffer_type combobox with end cap style options."""
        buffer_types = ["Round", "Flat", "Square"]
        self.widgets["FILTERING"]["BUFFER_TYPE"]["WIDGET"].clear()
        self.widgets["FILTERING"]["BUFFER_TYPE"]["WIDGET"].addItems(buffer_types)
        # Set default to Round if not already set
        if self.widgets["FILTERING"]["BUFFER_TYPE"]["WIDGET"].currentText() == "":
            self.widgets["FILTERING"]["BUFFER_TYPE"]["WIDGET"].setCurrentIndex(0)


    def filtering_populate_layers_chekableCombobox(self, layer=None):

        if self.widgets_initialized is True:

            if layer is None:
                layer = self.current_layer
            else:
                if not isinstance(layer, QgsVectorLayer):
                    logger.error(f"filtering_populate_layers_chekableCombobox: Expected QgsVectorLayer, got {type(layer).__name__}")
                    return
            try:    
                self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].clear()
                
                # CRITICAL: Check if layer exists in PROJECT_LAYERS before accessing
                if layer.id() not in self.PROJECT_LAYERS:
                    logger.info(f"Layer {layer.name()} not in PROJECT_LAYERS yet, skipping")
                    return
                
                layer_props = self.PROJECT_LAYERS[layer.id()]

                if layer_props["filtering"]["has_layers_to_filter"]:
                    i = 0
                    
                    # Create a copy of keys to avoid RuntimeError if dictionary changes during iteration
                    for key in list(self.PROJECT_LAYERS.keys()):
                        # Verify required keys exist in layer info
                        if key not in self.PROJECT_LAYERS or "infos" not in self.PROJECT_LAYERS[key]:
                            continue
                        
                        layer_info = self.PROJECT_LAYERS[key]["infos"]
                        required_keys = ["layer_id", "layer_name", "layer_crs_authid", "layer_geometry_type"]
                        if any(k not in layer_info or layer_info[k] is None for k in required_keys):
                            continue
                        
                        if layer_info["is_already_subset"] is False:
                            layer_info["subset_history"] = []

                        layer_id = layer_info["layer_id"]
                        layer_name = layer_info["layer_name"]
                        layer_crs_authid = layer_info["layer_crs_authid"]
                        layer_icon = self.icon_per_geometry_type(layer_info["layer_geometry_type"])

                        # Only add usable vector layers (skip raster and broken layers)
                        layer_obj = self.PROJECT.mapLayer(layer_id)
                        if (key != layer.id()
                            and layer_obj and isinstance(layer_obj, QgsVectorLayer)
                            and is_layer_source_available(layer_obj, require_psycopg2=False)):
                            self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].addItem(layer_icon, layer_name + ' [%s]' % (layer_crs_authid), {"layer_id": key, "layer_geometry_type": layer_info["layer_geometry_type"]})
                            item = self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].model().item(i)
                            if len(layer_props["filtering"]["layers_to_filter"]) > 0:
                                if layer_id in list(layer_id for layer_id in list(layer_props["filtering"]["layers_to_filter"])):
                                    item.setCheckState(Qt.Checked)
                                else:
                                    item.setCheckState(Qt.Unchecked) 
                            else:
                                item.setCheckState(Qt.Unchecked)
                            i += 1    
                else:
                    i = 0
                    # Create a copy of keys to avoid RuntimeError if dictionary changes during iteration
                    for key in list(self.PROJECT_LAYERS.keys()):
                        # Verify required keys exist in layer info
                        if key not in self.PROJECT_LAYERS or "infos" not in self.PROJECT_LAYERS[key]:
                            continue
                        
                        layer_info = self.PROJECT_LAYERS[key]["infos"]
                        required_keys = ["layer_id", "layer_name", "layer_crs_authid", "layer_geometry_type"]
                        if any(k not in layer_info or layer_info[k] is None for k in required_keys):
                            continue
                        
                        layer_id = layer_info["layer_id"]
                        layer_name = layer_info["layer_name"]
                        layer_crs_authid = layer_info["layer_crs_authid"]
                        layer_icon = self.icon_per_geometry_type(layer_info["layer_geometry_type"])
                        
                        # Only add usable vector layers (skip raster and broken layers)
                        layer_obj = self.PROJECT.mapLayer(layer_id)
                        if (key != layer.id()
                            and layer_obj and isinstance(layer_obj, QgsVectorLayer)
                            and is_layer_source_available(layer_obj, require_psycopg2=False)):
                            self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].addItem(layer_icon, layer_name + ' [%s]' % (layer_crs_authid), {"layer_id": key, "layer_geometry_type": layer_info["layer_geometry_type"]})
                            item = self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].model().item(i)
                            item.setCheckState(Qt.Unchecked)
                            i += 1    
            
            except Exception as e:
                # Log the error without storing in self.exception
                logger.warning(f"Error in filtering_populate_layers_chekableCombobox: {type(e).__name__}: {e}")
                
                # Check if layer is still valid (not deleted)
                try:
                    if layer is not None and not sip.isdeleted(layer):
                        # Pass explicitly typed empty list for properties parameter
                        empty_properties = []
                        self.resetLayerVariableOnErrorEvent(layer, empty_properties)
                    else:
                        # Layer has been deleted
                        logger.debug("Cannot reset layer variable - layer has been deleted")
                except RuntimeError as runtime_err:
                    # Layer C++ object is deleted
                    logger.debug(f"Cannot reset layer variable - layer C++ object deleted: {runtime_err}")

    def exporting_populate_combobox(self):

        if self.widgets_initialized is True and self.has_loaded_layers is True:

            layers_to_export = []
            datatype_to_export = ''

            if self.project_props['EXPORTING']['HAS_LAYERS_TO_EXPORT'] is True:
                layers_to_export = self.project_props['EXPORTING']['LAYERS_TO_EXPORT']
            
            if self.project_props['EXPORTING']['HAS_DATATYPE_TO_EXPORT'] is True:
                datatype_to_export = self.project_props['EXPORTING']['DATATYPE_TO_EXPORT']

            # Import REMOTE_PROVIDERS constant for detecting remote layers
            from .modules.constants import REMOTE_PROVIDERS
            
            # Debug: Log PROJECT_LAYERS count vs QGIS project layers count
            qgis_layers = [l for l in self.PROJECT.mapLayers().values() if isinstance(l, QgsVectorLayer)]
            postgres_layers = [l for l in qgis_layers if l.providerType() == 'postgres']
            # Remote layers: WFS, ArcGIS Feature Service, etc.
            remote_layers = [l for l in qgis_layers if l.providerType() in REMOTE_PROVIDERS]
            postgres_in_project_layers = sum(1 for lid in self.PROJECT_LAYERS.keys() 
                                             if self.PROJECT.mapLayer(lid) and 
                                             self.PROJECT.mapLayer(lid).providerType() == 'postgres')
            logger.info(f"exporting_populate_combobox: PROJECT_LAYERS has {len(self.PROJECT_LAYERS)} entries ({postgres_in_project_layers} PostgreSQL), QGIS project has {len(qgis_layers)} vector layers ({len(postgres_layers)} PostgreSQL, {len(remote_layers)} remote)")
            
            # Check for PostgreSQL layers missing from PROJECT_LAYERS
            missing_postgres = [l for l in postgres_layers if l.id() not in self.PROJECT_LAYERS]
            if missing_postgres:
                logger.warning(f"exporting_populate_combobox: {len(missing_postgres)} PostgreSQL layer(s) in QGIS project but NOT in PROJECT_LAYERS: {[l.name() for l in missing_postgres]}")
            
            # Check for remote layers (WFS, ArcGIS, etc.) missing from PROJECT_LAYERS
            missing_remote = [l for l in remote_layers if l.id() not in self.PROJECT_LAYERS]
            if missing_remote:
                logger.warning(f"exporting_populate_combobox: {len(missing_remote)} remote layer(s) in QGIS project but NOT in PROJECT_LAYERS: {[l.name() for l in missing_remote]}")

            self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].clear()
            item_index = 0  # Track actual item position in widget
            skipped_postgres_count = 0  # Track skipped PostgreSQL layers
            # Create a copy of keys to avoid RuntimeError if dictionary changes during iteration
            for key in list(self.PROJECT_LAYERS.keys()):
                # Verify required keys exist in layer info
                if key not in self.PROJECT_LAYERS or "infos" not in self.PROJECT_LAYERS[key]:
                    logger.debug(f"exporting_populate_combobox: Skipping layer {key} - missing from PROJECT_LAYERS or no 'infos' key")
                    continue
                
                layer_info = self.PROJECT_LAYERS[key]["infos"]
                required_keys = ["layer_id", "layer_name", "layer_crs_authid", "layer_geometry_type"]
                if any(k not in layer_info or layer_info[k] is None for k in required_keys):
                    missing_keys = [k for k in required_keys if k not in layer_info or layer_info[k] is None]
                    logger.debug(f"exporting_populate_combobox: Skipping layer {key} - missing required keys: {missing_keys}")
                    continue
                
                layer_id = layer_info["layer_id"]
                layer_name = layer_info["layer_name"]
                layer_crs_authid = layer_info["layer_crs_authid"]
                layer_icon = self.icon_per_geometry_type(layer_info["layer_geometry_type"])
                
                # Only add usable vector layers (skip raster and broken layers)
                # Note: require_psycopg2=False because export uses QGIS API (QgsVectorFileWriter)
                # which handles PostgreSQL connections internally, without needing psycopg2
                layer_obj = self.PROJECT.mapLayer(layer_id)
                if layer_obj and isinstance(layer_obj, QgsVectorLayer) and is_layer_source_available(layer_obj, require_psycopg2=False):
                    layer_name = layer_name + ' [%s]' % (layer_crs_authid)
                    self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].addItem(layer_icon, layer_name, key)
                    item = self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].model().item(item_index)
                    if key in layers_to_export:
                        item.setCheckState(Qt.Checked)
                    else:
                        item.setCheckState(Qt.Unchecked)
                    item_index += 1  # Increment only when item is actually added
                else:
                    # Debug: Log why layer was skipped
                    if not layer_obj:
                        logger.debug(f"exporting_populate_combobox: Skipping layer '{layer_name}' ({layer_id}) - layer_obj is None (not in QGIS project)")
                    elif not isinstance(layer_obj, QgsVectorLayer):
                        logger.debug(f"exporting_populate_combobox: Skipping layer '{layer_name}' ({layer_id}) - not a QgsVectorLayer")
                    else:
                        # More detailed logging for source availability issues
                        provider_type = layer_obj.providerType() if layer_obj else 'unknown'
                        is_valid = layer_obj.isValid() if layer_obj else False
                        logger.debug(f"exporting_populate_combobox: Skipping layer '{layer_name}' ({layer_id}) - is_layer_source_available returned False (provider={provider_type}, isValid={is_valid})")
                        if provider_type == 'postgres':
                            skipped_postgres_count += 1
            
            # FIX: Add PostgreSQL layers that are in QGIS project but missing from PROJECT_LAYERS
            # These layers can still be exported using QGIS API (QgsVectorFileWriter)
            for postgres_layer in missing_postgres:
                if postgres_layer.isValid() and is_layer_source_available(postgres_layer, require_psycopg2=False):
                    layer_name_display = f"{postgres_layer.name()} [{postgres_layer.crs().authid()}]"
                    # Convert geometry type integer to legacy string format for icon_per_geometry_type
                    geom_type_str = get_geometry_type_string(postgres_layer.geometryType(), legacy_format=True)
                    layer_icon = self.icon_per_geometry_type(geom_type_str)
                    self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].addItem(layer_icon, layer_name_display, postgres_layer.id())
                    item = self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].model().item(item_index)
                    if postgres_layer.id() in layers_to_export:
                        item.setCheckState(Qt.Checked)
                    else:
                        item.setCheckState(Qt.Unchecked)
                    item_index += 1
                    logger.info(f"exporting_populate_combobox: Added missing PostgreSQL layer '{postgres_layer.name()}' to export list")
            
            # FIX v2.3.13: Add remote layers (WFS, ArcGIS, etc.) that are in QGIS project but missing from PROJECT_LAYERS
            for remote_layer in missing_remote:
                if remote_layer.isValid() and is_layer_source_available(remote_layer, require_psycopg2=False):
                    layer_name_display = f"{remote_layer.name()} [{remote_layer.crs().authid()}]"
                    # Convert geometry type integer to legacy string format for icon_per_geometry_type
                    geom_type_str = get_geometry_type_string(remote_layer.geometryType(), legacy_format=True)
                    layer_icon = self.icon_per_geometry_type(geom_type_str)
                    self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].addItem(layer_icon, layer_name_display, remote_layer.id())
                    item = self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].model().item(item_index)
                    if remote_layer.id() in layers_to_export:
                        item.setCheckState(Qt.Checked)
                    else:
                        item.setCheckState(Qt.Unchecked)
                    item_index += 1
                    logger.info(f"exporting_populate_combobox: Added missing remote layer '{remote_layer.name()}' (provider={remote_layer.providerType()}) to export list")
            
            logger.info(f"exporting_populate_combobox: Added {item_index} layers to export combobox")
            if skipped_postgres_count > 0:
                logger.warning(f"exporting_populate_combobox: {skipped_postgres_count} PostgreSQL layer(s) skipped - check layer validity")
            
            ogr_driver_list = [ogr.GetDriver(i).GetDescription() for i in range(ogr.GetDriverCount())]
            ogr_driver_list.sort()
            self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"].clear()
            self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"].addItems(ogr_driver_list)
        
            if datatype_to_export != '':
                self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"].setCurrentIndex(self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"].findText(datatype_to_export))
            else:
                self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"].setCurrentIndex(self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"].findText('GPKG'))


    def _apply_auto_configuration(self):
        """
        Auto-detect and apply UI profile and theme based on environment.
        
        Detects UI profile from screen resolution and theme from QGIS settings.
        Logs configuration results for debugging.
        
        Returns:
            dict: Auto-configuration results with detected profile and theme
        """
        if not UI_CONFIG_AVAILABLE:
            return {}
        
        auto_config_result = ui_utils.auto_configure_from_environment(self.CONFIG_DATA)
        
        # Log auto-configuration results
        logger.info(f"FilterMate auto-configuration completed:")
        logger.info(f"  - Profile: {auto_config_result.get('profile_detected')} "
                   f"({auto_config_result.get('profile_source')})")
        logger.info(f"  - Theme: {auto_config_result.get('theme_detected')} "
                   f"({auto_config_result.get('theme_source')})")
        logger.info(f"  - Resolution: {auto_config_result.get('screen_resolution')}")
        
        return auto_config_result

    def _apply_stylesheet(self):
        """
        Apply stylesheet using StyleLoader with config colors.
        
        Theme is automatically detected from config.json ACTIVE_THEME or QGIS.
        StyleLoader handles QSS loading, color replacement, and caching.
        """
        StyleLoader.set_theme_from_config(
            self.dockWidgetContents, 
            self.CONFIG_DATA
        )

    def _configure_pushbuttons(self, pushButton_config, icons_sizes, font):
        """
        Configure all push button widgets with icons, sizes, and cursors.
        
        Applies dynamic dimensions based on button type (action/tool/default).
        Sets proper size policies and icon sizes from UIConfig or fallback values.
        
        Args:
            pushButton_config (dict): Push button configuration from config.json
            icons_sizes (dict): Icon size dictionary with ACTION and OTHERS keys
            font (QFont): Font to apply to buttons
        """
        pushButton_config_path = ['APP', 'DOCKWIDGET', 'PushButton']
        
        for widget_group in self.widgets:
            for widget_name in self.widgets[widget_group]:
                widget_type = self.widgets[widget_group][widget_name]["TYPE"]
                widget_obj = self.widgets[widget_group][widget_name]["WIDGET"]
                
                if widget_type == "PushButton":
                    self.set_widget_icon(pushButton_config_path + ["ICONS", widget_group, widget_name])
                    widget_obj.setCursor(Qt.PointingHandCursor)
                    
                    # Set tooltips for exploring buttons
                    if widget_group == "EXPLORING":
                        exploring_tooltips = {
                            "IDENTIFY": self.tr("Identify selected feature"),
                            "ZOOM": self.tr("Zoom to selected feature"),
                            "IS_SELECTING": self.tr("Toggle feature selection on map"),
                            "IS_TRACKING": self.tr("Auto-zoom when feature changes"),
                            "IS_LINKING": self.tr("Link exploring widgets together"),
                            "RESET_ALL_LAYER_PROPERTIES": self.tr("Reset all layer exploring properties")
                        }
                        if widget_name in exploring_tooltips:
                            widget_obj.setToolTip(exploring_tooltips[widget_name])
                    
                    icon_size = icons_sizes.get(widget_group, icons_sizes["OTHERS"])
                    
                    # Apply dynamic dimensions based on button type
                    if UI_CONFIG_AVAILABLE:
                        # Determine button type for dynamic sizing
                        if widget_group == "ACTION":
                            button_height = UIConfig.get_button_height("action_button")
                            button_icon_size = UIConfig.get_icon_size("action_button")
                        elif widget_group in ["EXPLORING", "FILTERING", "EXPORTING"]:
                            button_height = UIConfig.get_button_height("tool_button")
                            button_icon_size = UIConfig.get_icon_size("tool_button")
                        else:
                            button_height = UIConfig.get_button_height("button")
                            button_icon_size = UIConfig.get_icon_size("button")
                        
                        widget_obj.setMinimumHeight(button_height)
                        widget_obj.setMaximumHeight(button_height)
                        widget_obj.setMinimumWidth(button_height)
                        widget_obj.setMaximumWidth(button_height)
                        widget_obj.setIconSize(QtCore.QSize(button_icon_size, button_icon_size))
                        
                        # CRITICAL: Force Fixed size policy for sidebar buttons
                        if widget_group in ["EXPLORING", "FILTERING", "EXPORTING"]:
                            widget_obj.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
                    else:
                        # Fallback to normal profile defaults
                        widget_obj.setIconSize(QtCore.QSize(icon_size, icon_size))
                        
                        if widget_group in ["EXPLORING", "FILTERING", "EXPORTING"]:
                            fallback_size = 36
                            widget_obj.setMinimumHeight(fallback_size)
                            widget_obj.setMaximumHeight(fallback_size)
                            widget_obj.setMinimumWidth(fallback_size)
                            widget_obj.setMaximumWidth(fallback_size)
                        else:
                            widget_obj.setMinimumHeight(icon_size * 2)
                            widget_obj.setMaximumHeight(icon_size * 2)
                            widget_obj.setMinimumWidth(icon_size * 2)
                            widget_obj.setMaximumWidth(icon_size * 2)
                    
                    widget_obj.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
                    widget_obj.setFont(font)

    def _configure_other_widgets(self, font):
        """
        Configure non-button widgets (comboboxes, text inputs, etc.).
        
        Sets cursors and fonts for ComboBox, LineEdit, QgsFieldExpressionWidget,
        PropertyOverrideButton, and other widget types.
        
        Args:
            font (QFont): Font to apply to widgets
        """
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
        """
        Configure sizes for key widgets (widget_keys and frame_actions).
        
        Uses UIConfig for dynamic dimensions or falls back to hardcoded values.
        Sets fixed size policies for widget_keys to prevent unwanted resizing.
        
        Args:
            icons_sizes (dict): Icon size dictionary with ACTION and OTHERS keys
        """
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
        """
        Load and apply plugin stylesheet using StyleLoader with auto-detection.
        
        Orchestrates UI styling by:
        1. Auto-detecting UI profile and theme
        2. Applying stylesheet via StyleLoader
        3. Initializing theme and icon manager
        4. Configuring push buttons
        5. Configuring other widgets
        6. Setting key widget sizes
        7. Starting QGIS theme watcher for automatic dark/light mode switching
        
        Benefits:
        - Centralized style management
        - Automatic adaptation to screen size and QGIS theme
        - Proper error handling and fallbacks
        - Easy theme customization via config.json
        - Automatic theme sync when QGIS theme changes
        """
        # Auto-configure UI profile and theme
        self._apply_auto_configuration()
        
        # Apply stylesheet
        self._apply_stylesheet()
        
        # Initialize IconThemeManager with current QGIS theme BEFORE configuring icons
        if ICON_THEME_AVAILABLE:
            current_theme = StyleLoader.detect_qgis_theme()
            IconThemeManager.set_theme(current_theme)
            logger.info(f"IconThemeManager pre-initialized with theme: {current_theme}")
        
        # Get configuration
        pushButton_config_path = ['APP', 'DOCKWIDGET', 'PushButton']
        pushButton_config = self.CONFIG_DATA[pushButton_config_path[0]][pushButton_config_path[1]][pushButton_config_path[2]]
        
        icons_sizes = {
            "ACTION": pushButton_config.get("ICONS_SIZES", {}).get("ACTION", 20),
            "OTHERS": pushButton_config.get("ICONS_SIZES", {}).get("OTHERS", 20),
        }
        
        font = QFont("Segoe UI Semibold", 8)
        font.setBold(True)
        
        # Configure widgets (icons will now use correct theme)
        self._configure_pushbuttons(pushButton_config, icons_sizes, font)
        self._configure_other_widgets(font)
        self._configure_key_widgets_sizes(icons_sizes)
        
        # Start theme watcher for automatic dark/light mode switching
        self._setup_theme_watcher()
        
        logger.debug("UI stylesheet loaded and applied successfully")
    
    def _setup_theme_watcher(self):
        """
        Setup QGIS theme watcher for automatic dark/light mode switching.
        
        Connects to QGIS paletteChanged signal to detect theme changes.
        When QGIS theme changes (e.g., user switches to Night Mapping),
        the plugin automatically updates its stylesheet and icons.
        """
        try:
            # Get or create theme watcher singleton
            self._theme_watcher = QGISThemeWatcher.get_instance()
            
            # Detect current theme and initialize IconThemeManager
            current_theme = StyleLoader.detect_qgis_theme()
            if ICON_THEME_AVAILABLE:
                IconThemeManager.set_theme(current_theme)
                logger.info(f"IconThemeManager initialized with theme: {current_theme}")
            
            # Add our callback for theme changes
            self._theme_watcher.add_callback(self._on_qgis_theme_changed)
            
            # Start watching if not already
            if not self._theme_watcher.is_watching:
                self._theme_watcher.start_watching()
            
            # Refresh icons for initial theme (important for dark mode at startup)
            if current_theme == 'dark':
                self._refresh_icons_for_theme()
            
            logger.info(f"Theme watcher initialized - current theme: {current_theme}")
            
        except Exception as e:
            logger.warning(f"Could not setup theme watcher: {e}")
    
    def _on_qgis_theme_changed(self, new_theme: str):
        """
        Handle QGIS theme change event.
        
        Called automatically when QGIS theme changes (e.g., user switches
        between default and Night Mapping themes).
        
        Args:
            new_theme: New theme name ('dark' or 'default')
        """
        logger.info(f"QGIS theme changed to: {new_theme}")
        
        try:
            # Update IconThemeManager
            if ICON_THEME_AVAILABLE:
                IconThemeManager.set_theme(new_theme)
            
            # Reapply stylesheet with new theme
            StyleLoader.set_theme_from_config(
                self.dockWidgetContents,
                self.CONFIG_DATA,
                new_theme
            )
            
            # Refresh all button icons for new theme
            self._refresh_icons_for_theme()
            
            # Update JsonView (config editor) theme
            if hasattr(self, 'config_view') and self.config_view is not None:
                is_dark = (new_theme == 'dark')
                self.config_view.refresh_theme_stylesheet(force_dark=is_dark)
                logger.debug("JsonView theme updated")
            
            # Show brief notification
            theme_name = "Mode sombre" if new_theme == 'dark' else "Mode clair"
            show_info("FilterMate", f"Thème adapté: {theme_name}")
            
        except Exception as e:
            logger.error(f"Error applying theme change: {e}")
    
    def _refresh_icons_for_theme(self):
        """
        Refresh all button icons for the current theme.
        
        Iterates through all PushButton widgets and reapplies their icons
        using the IconThemeManager to get theme-appropriate versions.
        """
        if not ICON_THEME_AVAILABLE:
            return
        
        if not self.widgets_initialized:
            return
        
        try:
            # Refresh toolbox icons
            toolbox_icons = {
                0: "filter_multi.png",   # FILTERING tab
                1: "save.png",           # EXPORTING tab
                2: "parameters.png"      # CONFIGURATION tab
            }
            for index, icon_file in toolbox_icons.items():
                icon_path = os.path.join(self.plugin_dir, "icons", icon_file)
                if os.path.exists(icon_path):
                    themed_icon = get_themed_icon(icon_path)
                    self.toolBox_tabTools.setItemIcon(index, themed_icon)
            
            # Refresh pushbutton icons
            pushButton_config_path = ['APP', 'DOCKWIDGET', 'PushButton']
            
            for widget_group in self.widgets:
                for widget_name in self.widgets[widget_group]:
                    widget_info = self.widgets[widget_group][widget_name]
                    widget_type = widget_info.get("TYPE")
                    
                    if widget_type == "PushButton":
                        widget_obj = widget_info.get("WIDGET")
                        
                        # Get icon path from stored config
                        icon_path = widget_info.get("ICON")
                        if not icon_path:
                            icon_path = widget_info.get("ICON_ON_FALSE")
                        
                        if icon_path and os.path.exists(icon_path):
                            # Apply themed icon
                            themed_icon = get_themed_icon(icon_path)
                            widget_obj.setIcon(themed_icon)
                            
                            # Store path for future reference
                            widget_obj.setProperty('icon_path', icon_path)
            
            logger.debug(f"Refreshed icons for theme: {StyleLoader.get_current_theme()}")
            
        except Exception as e:
            logger.error(f"Error refreshing icons: {e}")


    def set_widgets_enabled_state(self, state):
        """
        Enable or disable all plugin widgets.
        
        Iterates through all registered widgets and sets their enabled state.
        Special handling for checkable buttons and collapsible groupboxes.
        
        Args:
            state (bool): True to enable widgets, False to disable
            
        Notes:
            - Excludes JsonTreeView, LayerTreeView, JsonModel, ToolBox from state changes
            - Checkable buttons are unchecked when disabled
            - GroupBoxes are collapsed when disabled
            - Called during initialization and when layers are added/removed
            - Central method for UI responsiveness control
            - SAFETY: Blocks all signals during state changes to prevent race conditions
        """
        logger.debug(f"set_widgets_enabled_state({state}) called")
        widget_count = 0
        for widget_group in self.widgets:
            for widget_name in self.widgets[widget_group]:
                if self.widgets[widget_group][widget_name]["TYPE"] not in ("JsonTreeView","LayerTreeView","JsonModel","ToolBox"):
                    widget = self.widgets[widget_group][widget_name]["WIDGET"]
                    
                    # SAFETY: Block signals to prevent race conditions during state changes
                    # This prevents setChecked(False) from triggering toggled signals
                    # that could cause access violations when layers are being destroyed
                    was_blocked = widget.blockSignals(True)
                    try:
                        if self.widgets[widget_group][widget_name]["TYPE"] in ("PushButton", "GroupBox"):
                            if widget.isCheckable():
                                if state is False:
                                    widget.setChecked(state)
                                    if self.widgets[widget_group][widget_name]["TYPE"] == "GroupBox":
                                        widget.setCollapsed(True)
                        widget.setEnabled(state)
                    finally:
                        # Always restore signal blocking state
                        widget.blockSignals(was_blocked)
                    
                    widget_count += 1
        logger.debug(f"{widget_count} widgets set to enabled={state}")



    def connect_widgets_signals(self):
        """
        Connect all widget signals to their respective slot handlers.
        
        Iterates through widget registry and establishes signal-slot connections
        using manageSignal(). Errors are silently caught as some widgets may not
        have signals available.
        
        Notes:
            - Skips QGIS widget group (handled separately)
            - Uses manageSignal() for centralized signal management
            - Safe to call multiple times (idempotent)
            - Called after layers are loaded or project changes
            - Pairs with disconnect_widgets_signals()
        """
        for widget_group in self.widgets:
            if widget_group != 'QGIS':
                for widget in self.widgets[widget_group]:
                    try:
                        self.manageSignal([widget_group, widget], 'connect')
                    except (AttributeError, RuntimeError, TypeError, SignalStateChangeError) as e:
                        # Widget may not exist or signal not available
                        pass

    def disconnect_widgets_signals(self):
        """
        Safely disconnect all widget signals.
        
        Critical for preventing Qt access violations during task execution.
        
        Notes:
            - CRITICAL FIX: Prevents crashes during task execution
            - Handles already-deleted widgets gracefully
            - Called before long-running tasks or layer removal
            - Essential for plugin stability
            - Pairs with connect_widgets_signals()
            
        Raises:
            No exceptions propagated - all errors caught and logged
        """
        # CRITICAL FIX: Protect against Qt access violations during task execution
        # DO NOT call processEvents() inside the loop - it can trigger widget destruction
        # during iteration, causing access violations
        
        for widget_group in self.widgets:
            if widget_group != 'QGIS':
                for widget in self.widgets[widget_group]:
                    try:
                        self.manageSignal([widget_group, widget], 'disconnect')
                    except (AttributeError, RuntimeError, TypeError, SignalStateChangeError) as e:
                        # Widget may not exist, already deleted, or signal not connected
                        logger.debug(f"Could not disconnect signal for {widget_group}.{widget}: {e}")
                        pass


    def manage_interactions(self):
        """
        Initialize widget interactions and default values.
        
        Sets up initial widget states, default values, and connects signals
        if layers are already loaded. Called once during dockwidget construction.
        """
        """INIT"""
        self.coordinateReferenceSystem = QgsCoordinateReferenceSystem()
        
        self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"].setExpressionsEnabled(True)
        self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"].setClearValue(0.0)
        
        if self.PROJECT:
            self.widgets["EXPORTING"]["PROJECTION_TO_EXPORT"]["WIDGET"].setCrs(self.PROJECT.crs())
        
        # Only enable widgets if PROJECT_LAYERS is already populated
        # Otherwise, wait for get_project_layers_from_app() to enable them when data is ready
        if self.has_loaded_layers is True and len(self.PROJECT_LAYERS) > 0:
            self.set_widgets_enabled_state(True)
            self.connect_widgets_signals()
        else:
            self.set_widgets_enabled_state(False)
            # CRITICAL: Connect DOCK groupbox signals even when no layers loaded
            # These widgets control UI state and don't depend on layer data
            try:
                self.manageSignal(["DOCK", "SINGLE_SELECTION"], 'connect')
                self.manageSignal(["DOCK", "MULTIPLE_SELECTION"], 'connect')
                self.manageSignal(["DOCK", "CUSTOM_SELECTION"], 'connect')
            except (AttributeError, RuntimeError, TypeError, SignalStateChangeError) as e:
                logger.debug(f"Could not connect DOCK groupbox signals (no layers): {type(e).__name__}: {e}")
        
        # CRITICAL FIX: Connect groupbox signals DIRECTLY to ensure they work
        # This bypasses the manageSignal system which may have caching issues
        self._connect_groupbox_signals_directly()
        
        self.filtering_populate_predicates_chekableCombobox()
        
        self.filtering_populate_buffer_type_combobox()

        # Note: DOCK widget signals (SINGLE_SELECTION, MULTIPLE_SELECTION, CUSTOM_SELECTION, TOOLS)
        # are already connected via connect_widgets_signals() above.
        # No need for manual connection to avoid double signal firing.
        
        # Configuration model signal is now connected in manage_configuration_model()
        # to ensure it's connected immediately after model creation
        # self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].filterExpressionChanged()
        
        # self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].contextMenuEvent
        # self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].contextMenuEvent

        if self.init_layer is not None and isinstance(self.init_layer, QgsVectorLayer):
            logger.info(f"FilterMate manage_interactions: init_layer found: {self.init_layer.name()}")
            self.manage_output_name()
            logger.debug("FilterMate manage_interactions: manage_output_name() done")
            self.manageSignal(["EXPORTING","LAYERS_TO_EXPORT"], 'disconnect')
            self.exporting_populate_combobox()
            logger.debug("FilterMate manage_interactions: exporting_populate_combobox() done")
            self.manageSignal(["EXPORTING","LAYERS_TO_EXPORT"], 'connect', 'checkedItemsChanged')
            self.set_exporting_properties()
            logger.debug("FilterMate manage_interactions: set_exporting_properties() done")
            self.exploring_groupbox_init()
            logger.debug("FilterMate manage_interactions: exploring_groupbox_init() done")
            self.current_layer_changed(self.init_layer)
            logger.debug("FilterMate manage_interactions: current_layer_changed() done")
            self.filtering_auto_current_layer_changed()
            logger.info("FilterMate manage_interactions: init_layer processing complete")

            
    def select_tabTools_index(self):
        
        if self.widgets_initialized is True:

            self.tabTools_current_index = self.widgets["DOCK"]["TOOLS"]["WIDGET"].currentIndex()
            
            # Index 0: FILTERING panel active
            if self.tabTools_current_index == 0:
                # Enable filter, undo, redo, unfilter buttons
                self.widgets["ACTION"]["FILTER"]["WIDGET"].setEnabled(True)
                self.widgets["ACTION"]["UNDO_FILTER"]["WIDGET"].setEnabled(True)
                self.widgets["ACTION"]["REDO_FILTER"]["WIDGET"].setEnabled(True)
                self.widgets["ACTION"]["UNFILTER"]["WIDGET"].setEnabled(True)
                # Disable export button
                self.widgets["ACTION"]["EXPORT"]["WIDGET"].setEnabled(False)
                # Keep about button enabled
                self.widgets["ACTION"]["ABOUT"]["WIDGET"].setEnabled(True)
            
            # Index 1: EXPORTING panel active
            elif self.tabTools_current_index == 1:
                # Disable filter, undo, redo, unfilter buttons
                self.widgets["ACTION"]["FILTER"]["WIDGET"].setEnabled(False)
                self.widgets["ACTION"]["UNDO_FILTER"]["WIDGET"].setEnabled(False)
                self.widgets["ACTION"]["REDO_FILTER"]["WIDGET"].setEnabled(False)
                self.widgets["ACTION"]["UNFILTER"]["WIDGET"].setEnabled(False)
                # Enable export button
                self.widgets["ACTION"]["EXPORT"]["WIDGET"].setEnabled(True)
                # Keep about button enabled
                self.widgets["ACTION"]["ABOUT"]["WIDGET"].setEnabled(True)
            
            # Index 2: CONFIGURATION panel active
            elif self.tabTools_current_index == 2:
                # Disable filter, undo, redo, unfilter, export buttons
                self.widgets["ACTION"]["FILTER"]["WIDGET"].setEnabled(False)
                self.widgets["ACTION"]["UNDO_FILTER"]["WIDGET"].setEnabled(False)
                self.widgets["ACTION"]["REDO_FILTER"]["WIDGET"].setEnabled(False)
                self.widgets["ACTION"]["UNFILTER"]["WIDGET"].setEnabled(False)
                self.widgets["ACTION"]["EXPORT"]["WIDGET"].setEnabled(False)
                # Keep only about button enabled
                self.widgets["ACTION"]["ABOUT"]["WIDGET"].setEnabled(True)

            self.set_exporting_properties()

    def _connect_groupbox_signals_directly(self):
        """
        Connect groupbox signals directly without going through manageSignal.
        
        This ensures the toggled and collapsedStateChanged signals are properly
        connected for exclusive groupbox behavior.
        """
        logger.debug("_connect_groupbox_signals_directly called")
        
        try:
            single_gb = self.mGroupBox_exploring_single_selection
            multiple_gb = self.mGroupBox_exploring_multiple_selection
            custom_gb = self.mGroupBox_exploring_custom_selection
            
            # CRITICAL FIX: Disconnect all receivers using blockSignals instead of disconnect()
            # disconnect() can cause freeze if called during initialization
            # blockSignals is safer and non-blocking
            for gb in [single_gb, multiple_gb, custom_gb]:
                # Temporarily block to reset connections safely
                was_blocked = gb.signalsBlocked()
                gb.blockSignals(True)
                try:
                    # Try to disconnect but don't block if it fails
                    gb.toggled.disconnect()
                except (TypeError, RuntimeError):
                    pass
                try:
                    gb.collapsedStateChanged.disconnect()
                except (TypeError, RuntimeError):
                    pass
                finally:
                    # Restore signal state
                    gb.blockSignals(was_blocked)
            
            logger.debug("Groupbox signals disconnected safely")
            
            # Connect toggled signals
            single_gb.toggled.connect(lambda checked: self._on_groupbox_clicked('single_selection', checked))
            multiple_gb.toggled.connect(lambda checked: self._on_groupbox_clicked('multiple_selection', checked))
            custom_gb.toggled.connect(lambda checked: self._on_groupbox_clicked('custom_selection', checked))
            
            # Connect collapsedStateChanged signals
            single_gb.collapsedStateChanged.connect(lambda collapsed: self._on_groupbox_collapse_changed('single_selection', collapsed))
            multiple_gb.collapsedStateChanged.connect(lambda collapsed: self._on_groupbox_collapse_changed('multiple_selection', collapsed))
            custom_gb.collapsedStateChanged.connect(lambda collapsed: self._on_groupbox_collapse_changed('custom_selection', collapsed))
            
            logger.debug("Groupbox signals connected successfully")
            
        except Exception as e:
            logger.error(f"Error connecting groupbox signals directly: {e}", exc_info=True)

    def _force_exploring_groupbox_exclusive(self, active_groupbox):
        """
        Force exclusive state for exploring groupboxes.
        
        Ensures only the specified groupbox is checked and expanded,
        while all others are unchecked and collapsed.
        
        Args:
            active_groupbox (str): The groupbox to activate ('single_selection', 'multiple_selection', or 'custom_selection')
        """
        # Prevent recursive calls
        if self._updating_groupbox:
            return
        
        logger.debug(f"_force_exploring_groupbox_exclusive called: active_groupbox={active_groupbox}")
        
        # Set lock to prevent recursion
        self._updating_groupbox = True
        
        try:
            single_gb = self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"]
            multiple_gb = self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"]
            custom_gb = self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"]
            
            # Block all signals to avoid recursive calls
            single_gb.blockSignals(True)
            multiple_gb.blockSignals(True)
            custom_gb.blockSignals(True)
            
            # Set states based on active groupbox
            if active_groupbox == "single_selection":
                single_gb.setChecked(True)
                single_gb.setCollapsed(False)
                multiple_gb.setChecked(False)
                multiple_gb.setCollapsed(True)
                custom_gb.setChecked(False)
                custom_gb.setCollapsed(True)
            elif active_groupbox == "multiple_selection":
                single_gb.setChecked(False)
                single_gb.setCollapsed(True)
                multiple_gb.setChecked(True)
                multiple_gb.setCollapsed(False)
                custom_gb.setChecked(False)
                custom_gb.setCollapsed(True)
            elif active_groupbox == "custom_selection":
                single_gb.setChecked(False)
                single_gb.setCollapsed(True)
                multiple_gb.setChecked(False)
                multiple_gb.setCollapsed(True)
                custom_gb.setChecked(True)
                custom_gb.setCollapsed(False)
            
            logger.debug(f"After setting - single: checked={single_gb.isChecked()}, collapsed={single_gb.isCollapsed()}")
            logger.debug(f"After setting - multiple: checked={multiple_gb.isChecked()}, collapsed={multiple_gb.isCollapsed()}")
            logger.debug(f"After setting - custom: checked={custom_gb.isChecked()}, collapsed={custom_gb.isCollapsed()}")
            
            # Restore signals
            single_gb.blockSignals(False)
            multiple_gb.blockSignals(False)
            custom_gb.blockSignals(False)
        finally:
            # Always release the lock
            self._updating_groupbox = False

    def _on_groupbox_clicked(self, groupbox, state):
        """
        Handle toggled signal from exploring groupbox checkbox.
        
        This method is called when the user clicks on the checkbox of a groupbox.
        The 'state' parameter indicates whether the checkbox is now checked (True)
        or unchecked (False).
        
        For exclusive behavior:
        - If state=True: This groupbox was checked, make it the active one
        - If state=False: User tried to uncheck, but we need at least one active.
          Check if any other groupbox is checked; if not, force this one to stay checked.
        
        Args:
            groupbox (str): The groupbox identifier ('single_selection', 'multiple_selection', or 'custom_selection')
            state (bool): True if the checkbox was checked, False if unchecked
        """
        # Prevent recursive calls
        if self._updating_groupbox:
            return
        
        # SAFETY: Don't process if widgets not initialized or if we're in an invalid state
        # This prevents access violations during cleanup when layers are being destroyed
        if not self.widgets_initialized or not hasattr(self, 'widgets'):
            logger.debug(f"_on_groupbox_clicked ignored: widgets not ready")
            return
        
        logger.debug(f"_on_groupbox_clicked called: groupbox={groupbox}, state={state}, widgets_initialized={self.widgets_initialized}")
        
        if self.widgets_initialized is True:
            if state:
                # User checked this groupbox - make it the active one
                self.exploring_groupbox_changed(groupbox)
            else:
                # User unchecked this groupbox - check if any other is checked
                # SAFETY: Verify widgets exist before accessing them
                try:
                    single_gb = self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"]
                    multiple_gb = self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"]
                    custom_gb = self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"]
                except (KeyError, AttributeError) as e:
                    logger.debug(f"Groupbox widgets not accessible: {e}")
                    return
                
                # Check if at least one other groupbox is checked
                other_checked = False
                if groupbox == "single_selection":
                    other_checked = multiple_gb.isChecked() or custom_gb.isChecked()
                elif groupbox == "multiple_selection":
                    other_checked = single_gb.isChecked() or custom_gb.isChecked()
                elif groupbox == "custom_selection":
                    other_checked = single_gb.isChecked() or multiple_gb.isChecked()
                
                if not other_checked:
                    # No other groupbox is checked - force this one to stay checked
                    # Block signal to avoid recursive call
                    triggering_widget = None
                    if groupbox == "single_selection":
                        triggering_widget = single_gb
                    elif groupbox == "multiple_selection":
                        triggering_widget = multiple_gb
                    elif groupbox == "custom_selection":
                        triggering_widget = custom_gb
                    
                    if triggering_widget:
                        triggering_widget.blockSignals(True)
                        triggering_widget.setChecked(True)
                        triggering_widget.setCollapsed(False)
                        triggering_widget.blockSignals(False)
                else:
                    # Another groupbox is checked - find which one and activate it
                    if single_gb.isChecked():
                        self.exploring_groupbox_changed("single_selection")
                    elif multiple_gb.isChecked():
                        self.exploring_groupbox_changed("multiple_selection")
                    elif custom_gb.isChecked():
                        self.exploring_groupbox_changed("custom_selection")

    def _on_groupbox_collapse_changed(self, groupbox, collapsed):
        """
        Handle collapsedStateChanged signal from exploring groupboxes.
        
        When a groupbox is EXPANDED (collapsed=False via arrow click),
        force exclusive behavior to make it the active one.
        When a groupbox is COLLAPSED, do nothing to avoid conflicts.
        
        Args:
            groupbox (str): The groupbox identifier ('single_selection', 'multiple_selection', or 'custom_selection')
            collapsed (bool): True if the groupbox was collapsed, False if expanded
        """
        # Prevent recursive calls - if we're already updating groupboxes, ignore this signal
        if self._updating_groupbox:
            return
        
        logger.debug(f"_on_groupbox_collapse_changed called: groupbox={groupbox}, collapsed={collapsed}, widgets_initialized={self.widgets_initialized}")
        
        if self.widgets_initialized is True:
            # Only react when a groupbox is EXPANDED (user clicked arrow to open it)
            if not collapsed:
                # Force this groupbox to be the exclusive active one
                self.exploring_groupbox_changed(groupbox)

    def exploring_groupbox_init(self):

        if self.widgets_initialized is True:
            self.properties_group_state_enabler(self.layer_properties_tuples_dict["selection_expression"]) 

            exploring_groupbox = "single_selection"  # Default
            
            # Try to restore from PROJECT_LAYERS if current_layer exists
            if self.current_layer is not None and self.current_layer.id() in self.PROJECT_LAYERS:
                layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
                if "current_exploring_groupbox" in layer_props.get("exploring", {}):
                    saved_groupbox = layer_props["exploring"]["current_exploring_groupbox"]
                    if saved_groupbox:
                        exploring_groupbox = saved_groupbox
            
            # Fallback: detect from UI state
            if not exploring_groupbox or exploring_groupbox == "single_selection":
                if self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].isChecked() is True or self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].isCollapsed() is False:
                    exploring_groupbox = "single_selection"

                elif self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].isChecked() is True or self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].isCollapsed() is False:
                    exploring_groupbox = "multiple_selection"  

                elif self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].isChecked() is True or self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].isCollapsed() is False:
                    exploring_groupbox = "custom_selection"

            self.exploring_groupbox_changed(exploring_groupbox)

    def _configure_single_selection_groupbox(self):
        """
        Configure UI for single feature selection mode.
        
        Sets groupbox states (expand single, collapse others), persists to PROJECT_LAYERS,
        disconnects signals, updates widgets with current layer, reconnects signals,
        and triggers feature update.
        
        Note: When the layer already has a filter (subsetString), the filter is preserved
        if no feature is selected in the widget. This prevents unintended filter removal
        when switching between groupboxes.
        
        Returns:
            bool: True if configuration succeeded, False if layer not in PROJECT_LAYERS
        """
        self.current_exploring_groupbox = "single_selection"
        
        # Save to PROJECT_LAYERS for persistence
        if self.current_layer is not None and self.current_layer.id() in self.PROJECT_LAYERS:
            self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["current_exploring_groupbox"] = "single_selection"

        if self.current_layer is not None:
            # CRITICAL: Use safe getter to validate layer exists in PROJECT_LAYERS
            layer_props = self._safe_get_layer_props(self.current_layer)
            if layer_props is None:
                logger.warning(f"Cannot initialize single_selection exploring - layer not in PROJECT_LAYERS. Skipping.")
                return False
            
            # CRITICAL: Disconnect signals BEFORE updating widgets
            self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')
            self.manageSignal(["EXPLORING","SINGLE_SELECTION_EXPRESSION"], 'disconnect')
            
            self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setEnabled(True)
            self.widgets["EXPLORING"]["SINGLE_SELECTION_EXPRESSION"]["WIDGET"].setEnabled(True)
            
            # CRITICAL FIX: Update widget to use current layer
            try:
                self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setLayer(self.current_layer)
                self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setDisplayExpression(layer_props["exploring"]["single_selection_expression"])
                # SPATIALITE FIX: Allow the model to populate before further operations
                self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setAllowNull(True)
            except (AttributeError, KeyError, RuntimeError) as e:
                logger.error(f"Error setting single selection features widget: {type(e).__name__}: {e}")
            
            try:
                self.widgets["EXPLORING"]["SINGLE_SELECTION_EXPRESSION"]["WIDGET"].setLayer(self.current_layer)
            except (AttributeError, KeyError, RuntimeError) as e:
                logger.error(f"Error setting single selection expression widget: {type(e).__name__}: {e}")
            
            # CRITICAL: Reconnect signals AFTER updating widgets
            # DEBUG: Use direct connection instead of manageSignal to ensure signal works
            picker_widget = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
            
            # First try to disconnect any existing connection (ignore errors)
            try:
                picker_widget.featureChanged.disconnect(self.exploring_features_changed)
            except TypeError:
                pass  # Not connected
            
            # Now connect directly
            picker_widget.featureChanged.connect(self.exploring_features_changed)
            
            # NOTE: fieldChanged signal is already connected in _setup_expression_widget_direct_connections()
            # No need to reconnect here - it would create duplicate handlers
            
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'filteringCheckedItemList')
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'updatingCheckedItemList')

            # Trigger features update and link widgets
            self.exploring_link_widgets()
            
            # Update feature selection state if there's a selected feature
            selected_feature = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].feature()
            if selected_feature is not None and selected_feature.isValid():
                self.exploring_features_changed(selected_feature)
        else:
            self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')
        
        return True

    def _configure_multiple_selection_groupbox(self):
        """
        Configure UI for multiple features selection mode.
        
        Sets groupbox states (expand multiple, collapse others), persists to PROJECT_LAYERS,
        disconnects signals, updates widgets with current layer, reconnects signals,
        and triggers features update.
        
        Note: When the layer already has a filter (subsetString), the filter is preserved
        if no features are selected in the widget. This prevents unintended filter removal
        when switching between groupboxes.
        
        Returns:
            bool: True if configuration succeeded
        """
        self.current_exploring_groupbox = "multiple_selection"
        
        # Save to PROJECT_LAYERS for persistence
        if self.current_layer is not None and self.current_layer.id() in self.PROJECT_LAYERS:
            self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["current_exploring_groupbox"] = "multiple_selection"

        if self.current_layer is not None:
            # CRITICAL: Disconnect ALL signals BEFORE updating widgets
            self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_EXPRESSION"], 'disconnect')

            self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setEnabled(True)
            self.widgets["EXPLORING"]["MULTIPLE_SELECTION_EXPRESSION"]["WIDGET"].setEnabled(True)
            
            try:
                self.widgets["EXPLORING"]["MULTIPLE_SELECTION_EXPRESSION"]["WIDGET"].setLayer(self.current_layer)
            except (AttributeError, KeyError, RuntimeError) as e:
                logger.error(f"Error setting multiple selection expression widget: {type(e).__name__}: {e}")

            # STABILITY FIX: Guard against KeyError if layer not in PROJECT_LAYERS
            if self.current_layer.id() not in self.PROJECT_LAYERS:
                logger.warning(f"exploring_multiple_selection: layer {self.current_layer.name()} not in PROJECT_LAYERS")
                return
            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
            try:
                # FIX v2.5.14: setLayer already handles setDisplayExpression internally
                # when the expression differs - no need to call it again here.
                # Calling it twice was causing task cancellation issues where
                # "Building features list" and "Loading features" were canceled
                # immediately after being launched.
                self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setLayer(self.current_layer, layer_props)
                # NOTE: Removed duplicate setDisplayExpression call - setLayer handles it
            except (AttributeError, KeyError, RuntimeError) as e:
                logger.error(f"Error setting multiple selection features widget: {type(e).__name__}: {e}")
            
            # CRITICAL: Reconnect signals AFTER updating widgets
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect')
            
            # NOTE: fieldChanged signal is already connected in _setup_expression_widget_direct_connections()
            # No need to reconnect here - it would create duplicate handlers

            # Trigger features update and link widgets
            self.exploring_link_widgets()
            
            # Update feature selection state if there are selected features
            selected_features = self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].currentSelectedFeatures()
            if selected_features:
                self.exploring_features_changed(selected_features, True)
        else:
            self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')
        
        return True

    def _configure_custom_selection_groupbox(self):
        """
        Configure UI for custom expression-based selection mode.
        
        Sets groupbox states (expand custom, collapse others), persists to PROJECT_LAYERS,
        disconnects signals, updates expression widget with current layer, reconnects signals,
        and triggers custom selection.
        
        Note: When the layer already has a filter (subsetString), the filter is preserved
        if no custom expression is set. This prevents unintended filter removal when
        switching between groupboxes.
        
        Returns:
            bool: True if configuration succeeded
        """
        self.current_exploring_groupbox = "custom_selection"
        
        # Save to PROJECT_LAYERS for persistence
        if self.current_layer is not None and self.current_layer.id() in self.PROJECT_LAYERS:
            self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["current_exploring_groupbox"] = "custom_selection"

        if self.current_layer is not None:
            # CRITICAL: Disconnect ALL signals BEFORE updating widgets
            self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')
            self.manageSignal(["EXPLORING","CUSTOM_SELECTION_EXPRESSION"], 'disconnect')

            self.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"].setEnabled(True)
            try:
                self.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"].setLayer(self.current_layer)
            except (AttributeError, KeyError, RuntimeError) as e:
                logger.error(f"Error setting custom selection expression widget: {type(e).__name__}: {e}")
            
            # CRITICAL: Reconnect signals AFTER updating widgets
            self.manageSignal(["EXPLORING","CUSTOM_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'filteringCheckedItemList')
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'updatingCheckedItemList')
            
            # Trigger link
            self.exploring_link_widgets()
            
            # PRESERVE FILTER FIX: Only call exploring_custom_selection if there's a custom expression
            # OR if the layer has no existing filter. This prevents clearing the filter when
            # switching groupboxes on an already-filtered layer.
            # STABILITY FIX: Guard against KeyError if layer not in PROJECT_LAYERS
            if self.current_layer.id() not in self.PROJECT_LAYERS:
                logger.warning(f"exploring_groupbox_changed: layer {self.current_layer.name()} not in PROJECT_LAYERS")
                return
            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
            custom_expression = layer_props["exploring"].get("custom_selection_expression", "")
            current_filter = self.current_layer.subsetString()
            
            if custom_expression or not current_filter:
                # Either we have an expression to apply, or there's no existing filter to preserve
                self.exploring_custom_selection()
            else:
                # Layer has an existing filter and no custom expression - preserve the filter
                logger.debug(f"Preserving existing filter on groupbox change: {current_filter[:60]}...")
        else:
            self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')
        
        return True

    def exploring_groupbox_changed(self, groupbox):
        """
        Handle exploring groupbox selection change with exclusive behavior.
        
        When a groupbox is clicked and becomes checked (activated), it expands and 
        all other exploring groupboxes are unchecked and collapsed.
        If a groupbox is unchecked, we still enforce exclusive behavior by checking it
        (preventing all groupboxes from being unchecked simultaneously).
        
        The configuration methods (_configure_*_selection_groupbox) handle the 
        exclusive state by checking/unchecking groupboxes and expanding/collapsing them.
        
        Args:
            groupbox (str): Selected groupbox ('single_selection', 'multiple_selection', or 'custom_selection')
        """
        if self.widgets_initialized is True:
            # CACHE INVALIDATION: When groupbox changes, invalidate cache for the previous groupbox
            # because the user is switching to a different selection mode
            if hasattr(self, '_exploring_cache') and self.current_layer:
                layer_id = self.current_layer.id()
                old_groupbox = self.current_exploring_groupbox
                if old_groupbox and old_groupbox != groupbox:
                    self._exploring_cache.invalidate(layer_id, old_groupbox)
                    logger.debug(f"exploring_groupbox_changed: Invalidated cache for {layer_id[:8]}.../{old_groupbox}")
            
            # Get the widget that was clicked
            triggering_widget = None
            if groupbox == "single_selection":
                triggering_widget = self.mGroupBox_exploring_single_selection
            elif groupbox == "multiple_selection":
                triggering_widget = self.mGroupBox_exploring_multiple_selection
            elif groupbox == "custom_selection":
                triggering_widget = self.mGroupBox_exploring_custom_selection
            
            if triggering_widget is None:
                return
            
            # CRITICAL FIX: Always force exclusive behavior when a groupbox is clicked
            # Even if the user is trying to uncheck, we force it to stay checked
            # (there must always be one active groupbox)
            
            # First, force this groupbox to be the active one (checked and expanded)
            # This also handles the case where user tries to uncheck the current groupbox
            self._force_exploring_groupbox_exclusive(groupbox)
            
            # Then call the appropriate configuration method to set up widgets
            if groupbox == "single_selection":
                self._configure_single_selection_groupbox()
            elif groupbox == "multiple_selection":
                self._configure_multiple_selection_groupbox()
            elif groupbox == "custom_selection":
                self._configure_custom_selection_groupbox()


    def exploring_identify_clicked(self):
        """
        Flash the currently selected features on the map canvas.
        
        This method uses cached feature IDs when available for optimal performance.
        The flash animation highlights the selected features with a red pulse effect.
        """
        if self.widgets_initialized is True and self.current_layer is not None:

            # CRITICAL: Check if layer C++ object has been deleted
            try:
                if sip.isdeleted(self.current_layer):
                    logger.debug("exploring_identify_clicked: current_layer C++ object deleted")
                    self.current_layer = None
                    return
            except (RuntimeError, TypeError):
                self.current_layer = None
                return

            layer_id = self.current_layer.id()
            groupbox_type = self.current_exploring_groupbox
            
            # OPTIMIZATION: Try to get cached feature IDs directly for fast flash
            if hasattr(self, '_exploring_cache') and groupbox_type:
                feature_ids = self._exploring_cache.get_feature_ids(layer_id, groupbox_type)
                if feature_ids:
                    logger.debug(f"exploring_identify_clicked: Using cached feature_ids ({len(feature_ids)} features)")
                    self.iface.mapCanvas().flashFeatureIds(
                        self.current_layer, 
                        feature_ids, 
                        startColor=QColor(235, 49, 42, 255), 
                        endColor=QColor(237, 97, 62, 25), 
                        flashes=6, 
                        duration=400
                    )
                    return
            
            # Fallback: get features from widgets (will also populate cache)
            features, expression = self.get_current_features()
            
            if len(features) == 0:
                return
            else:
                self.iface.mapCanvas().flashFeatureIds(
                    self.current_layer, 
                    [feature.id() for feature in features], 
                    startColor=QColor(235, 49, 42, 255), 
                    endColor=QColor(237, 97, 62, 25), 
                    flashes=6, 
                    duration=400
                )


    def get_current_features(self, use_cache: bool = True):
        """
        Get the currently selected features based on the active exploring groupbox.
        
        This method retrieves features from the appropriate widget (single selection,
        multiple selection, or custom expression) and caches them for subsequent
        operations like flash, zoom, and identify.
        
        Args:
            use_cache: If True, return cached features if available (default: True).
                       Set to False to force refresh from widgets.
        
        Returns:
            tuple: (features, expression) where features is a list of QgsFeature
                   and expression is the QGIS expression string used for selection.
        """
        if self.widgets_initialized is True and self.current_layer is not None:

            # CRITICAL: Check if layer C++ object has been deleted
            try:
                if sip.isdeleted(self.current_layer):
                    logger.debug("get_current_features: current_layer C++ object deleted")
                    self.current_layer = None
                    return [], ''
            except (RuntimeError, TypeError):
                self.current_layer = None
                return [], ''

            layer_id = self.current_layer.id()
            groupbox_type = self.current_exploring_groupbox
            
            # CACHE CHECK: Try to get cached features if use_cache is True
            if use_cache and hasattr(self, '_exploring_cache') and groupbox_type:
                cached = self._exploring_cache.get(layer_id, groupbox_type)
                if cached:
                    logger.debug(f"get_current_features: CACHE HIT for {layer_id[:8]}.../{groupbox_type}")
                    return cached['features'], cached['expression'] or ''

            features = []    
            expression = ''

            # Log current groupbox state for filtering diagnostics (debug level to reduce noise)
            logger.debug(f"get_current_features: groupbox='{self.current_exploring_groupbox}', layer='{self.current_layer.name()}'")
            
            if self.current_exploring_groupbox == "single_selection":
                input = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].feature()
                
                # NOTE: QgsFeaturePickerWidget emits featureChanged with invalid features during
                # typing/searching. This is normal behavior - only log at debug level.
                # Only log at info level when a valid feature is actually selected.
                if input is None or (hasattr(input, 'isValid') and not input.isValid()):
                    # Normal behavior during search - log at debug level only
                    logger.debug(f"   SINGLE_SELECTION: awaiting valid feature selection (input={type(input).__name__})")
                    return [], ''
                
                # Valid feature selected - log at info level
                logger.info(f"   SINGLE_SELECTION valid feature: id={input.id()}")
                if hasattr(input, 'geometry') and input.hasGeometry():
                    geom = input.geometry()
                    bbox = geom.boundingBox()
                    logger.debug(f"      geometry bbox = ({bbox.xMinimum():.1f},{bbox.yMinimum():.1f})-({bbox.xMaximum():.1f},{bbox.yMaximum():.1f})")
                
                features, expression = self.get_exploring_features(input, True)
                logger.debug(f"   RESULT: features count = {len(features)}, expression = '{expression}'")

            elif self.current_exploring_groupbox == "multiple_selection":
                input = self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].checkedItems()
                logger.debug(f"   MULTIPLE_SELECTION checked items: {len(input) if input else 0}")
                features, expression = self.get_exploring_features(input, True)
                logger.debug(f"   RESULT: features count = {len(features)}, expression = '{expression}'")

            elif self.current_exploring_groupbox == "custom_selection":
                expression = self.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"].expression()
                logger.debug(f"   CUSTOM_SELECTION expression: '{expression}'")
                
                # Save expression to layer_props before calling exploring_custom_selection
                if self.current_layer.id() in self.PROJECT_LAYERS:
                    self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["custom_selection_expression"] = expression
                
                # Process expression (whether field or complex expression)
                features, expression = self.exploring_custom_selection()
                logger.debug(f"   RESULT: features count = {len(features)}, expression = '{expression}'")

            else:
                logger.warning(f"   ⚠️ current_exploring_groupbox '{self.current_exploring_groupbox}' does not match any known groupbox!")
            
            # CACHE UPDATE: Store features in cache for subsequent operations
            if features and hasattr(self, '_exploring_cache') and groupbox_type:
                self._exploring_cache.put(layer_id, groupbox_type, features, expression)
                logger.debug(f"get_current_features: Cached {len(features)} features for {layer_id[:8]}.../{groupbox_type}")
                
            return features, expression
        
        logger.warning(f"🔍 get_current_features: widgets_initialized={self.widgets_initialized}, current_layer={self.current_layer}")
        return [], ''
        

    def exploring_zoom_clicked(self, features=[], expression=None):
        """
        Zoom the map canvas to the currently selected features.
        
        This method uses cached bounding boxes when available for optimal performance.
        If the bounding box is cached, the zoom is nearly instantaneous.
        
        Args:
            features: Optional list of features to zoom to (if empty, uses current selection)
            expression: Optional expression string associated with the features
        """
        if self.widgets_initialized is True and self.current_layer is not None:

            # CRITICAL: Check if layer C++ object has been deleted
            try:
                if sip.isdeleted(self.current_layer):
                    logger.debug("exploring_zoom_clicked: current_layer C++ object deleted")
                    self.current_layer = None
                    return
            except (RuntimeError, TypeError):
                self.current_layer = None
                return

            layer_id = self.current_layer.id()
            groupbox_type = self.current_exploring_groupbox
            
            # OPTIMIZATION: Try to use cached bounding box for instant zoom
            if not features or len(features) == 0:
                if hasattr(self, '_exploring_cache') and groupbox_type:
                    cached_bbox = self._exploring_cache.get_bbox(layer_id, groupbox_type)
                    if cached_bbox and not cached_bbox.isEmpty():
                        logger.debug(f"exploring_zoom_clicked: Using cached bbox for instant zoom")
                        # Apply padding to bbox (10% or minimum 5 units)
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
                
                # Fallback: get features from widgets (will also populate cache)
                features, expression = self.get_current_features()
            
            self.zooming_to_features(features, expression)


    def get_filtered_layer_extent(self, layer):
        """
        Calculate the actual bounding box of filtered features in a layer.
        
        This method correctly calculates the extent of only the visible/filtered
        features, rather than using the cached layer extent which may include
        features that are filtered out.
        
        Args:
            layer (QgsVectorLayer): Layer to calculate extent for
            
        Returns:
            QgsRectangle: Bounding box of filtered features, or layer extent if empty
        """
        if layer is None:
            return None
            
        try:
            # Force recalculation of extent for filtered features
            layer.updateExtents()
            
            # Get extent from provider with current subset filter applied
            extent = QgsRectangle()
            
            # Iterate through all filtered features to compute real extent
            request = QgsFeatureRequest().setNoAttributes().setFlags(QgsFeatureRequest.NoGeometry)
            # We need geometry for extent calculation, so remove NoGeometry flag
            request = QgsFeatureRequest().setNoAttributes()
            
            feature_count = 0
            for feature in layer.getFeatures(request):
                if feature.hasGeometry() and not feature.geometry().isEmpty():
                    if extent.isEmpty():
                        extent = feature.geometry().boundingBox()
                    else:
                        extent.combineExtentWith(feature.geometry().boundingBox())
                    feature_count += 1
                    
            if extent.isEmpty():
                # Fallback to layer extent if no features with geometry
                logger.debug(f"get_filtered_layer_extent: No features with geometry, using layer extent")
                return layer.extent()
                
            logger.debug(f"get_filtered_layer_extent: Calculated extent from {feature_count} filtered features")
            return extent
            
        except Exception as e:
            logger.warning(f"get_filtered_layer_extent error: {e}, falling back to layer extent")
            return layer.extent()

    def _compute_zoom_extent_for_mode(self):
        """
        Compute the appropriate zoom extent based on the current exploring mode.
        
        For single selection: zoom to the selected feature's bounding box
        For multiple selection: zoom to the combined extent of selected features
        For custom selection: zoom to the combined extent of features matching the expression
        
        Returns:
            QgsRectangle: The computed extent, or None if no features found
        """
        if not self.widgets_initialized or self.current_layer is None:
            return None
            
        try:
            extent = QgsRectangle()
            features_found = 0
            
            if self.current_exploring_groupbox == "single_selection":
                # Single selection: get the feature from the picker widget
                feature_picker = self.widgets.get("EXPLORING", {}).get("SINGLE_SELECTION_FEATURES", {}).get("WIDGET")
                if feature_picker:
                    feature = feature_picker.feature()
                    if feature and feature.isValid():
                        # Reload feature to ensure geometry is available
                        try:
                            reloaded = self.current_layer.getFeature(feature.id())
                            if reloaded.isValid() and reloaded.hasGeometry() and not reloaded.geometry().isEmpty():
                                extent = reloaded.geometry().boundingBox()
                                features_found = 1
                                logger.debug(f"_compute_zoom_extent_for_mode: Single feature extent computed")
                        except Exception as e:
                            logger.warning(f"_compute_zoom_extent_for_mode: Error reloading single feature: {e}")
                            
            elif self.current_exploring_groupbox == "multiple_selection":
                # Multiple selection: get checked items and compute combined extent
                combo = self.widgets.get("EXPLORING", {}).get("MULTIPLE_SELECTION_FEATURES", {}).get("WIDGET")
                if combo:
                    checked_items = combo.checkedItems()
                    if checked_items:
                        # Try to get features by their IDs
                        layer_props = self.PROJECT_LAYERS.get(self.current_layer.id(), {})
                        pk_name = layer_props.get("infos", {}).get("primary_key_name")
                        pk_is_numeric = layer_props.get("infos", {}).get("primary_key_is_numeric", True)
                        
                        for item in checked_items:
                            try:
                                # item format: (display_value, pk_value, ...)
                                if isinstance(item, (list, tuple)) and len(item) > 1:
                                    pk_value = item[1]
                                    # Build expression to fetch this feature
                                    if pk_name:
                                        if pk_is_numeric:
                                            expr = f'"{pk_name}" = {pk_value}'
                                        else:
                                            expr = f'"{pk_name}" = \'{pk_value}\''
                                        qgs_expr = QgsExpression(expr)
                                        if qgs_expr.isValid():
                                            for feat in self.current_layer.getFeatures(QgsFeatureRequest(qgs_expr)):
                                                if feat.hasGeometry() and not feat.geometry().isEmpty():
                                                    if extent.isEmpty():
                                                        extent = feat.geometry().boundingBox()
                                                    else:
                                                        extent.combineExtentWith(feat.geometry().boundingBox())
                                                    features_found += 1
                                                    break  # Only one feature per pk_value
                            except Exception as e:
                                logger.debug(f"_compute_zoom_extent_for_mode: Error processing multiple item: {e}")
                                
            elif self.current_exploring_groupbox == "custom_selection":
                # Custom selection: get expression and fetch matching features
                expr_widget = self.widgets.get("EXPLORING", {}).get("CUSTOM_SELECTION_EXPRESSION", {}).get("WIDGET")
                if expr_widget:
                    expression = expr_widget.expression()
                    if expression:
                        qgs_expr = QgsExpression(expression)
                        # Only process if it's a filter expression (not just a field name)
                        if qgs_expr.isValid() and not qgs_expr.isField():
                            try:
                                request = QgsFeatureRequest(qgs_expr)
                                for feat in self.current_layer.getFeatures(request):
                                    if feat.hasGeometry() and not feat.geometry().isEmpty():
                                        if extent.isEmpty():
                                            extent = feat.geometry().boundingBox()
                                        else:
                                            extent.combineExtentWith(feat.geometry().boundingBox())
                                        features_found += 1
                            except Exception as e:
                                logger.warning(f"_compute_zoom_extent_for_mode: Error fetching custom features: {e}")
            
            if features_found > 0 and not extent.isEmpty():
                # Add small padding (10% of extent size, minimum 10 units)
                width_padding = max(extent.width() * 0.1, 10)
                height_padding = max(extent.height() * 0.1, 10)
                extent.grow(max(width_padding, height_padding))
                logger.debug(f"_compute_zoom_extent_for_mode: Computed extent from {features_found} features for mode '{self.current_exploring_groupbox}'")
                return extent
            else:
                # Fallback to filtered layer extent
                logger.debug(f"_compute_zoom_extent_for_mode: No features found for mode '{self.current_exploring_groupbox}', using filtered layer extent")
                return self.get_filtered_layer_extent(self.current_layer)
                
        except Exception as e:
            logger.warning(f"_compute_zoom_extent_for_mode error: {e}")
            return self.get_filtered_layer_extent(self.current_layer)

    def zooming_to_features(self, features, expression=None):
        
        if self.widgets_initialized is True and self.current_layer is not None:

            # CRITICAL: Check if layer C++ object has been deleted
            try:
                if sip.isdeleted(self.current_layer):
                    logger.debug("zooming_to_features: current_layer C++ object deleted")
                    self.current_layer = None
                    return
            except (RuntimeError, TypeError):
                self.current_layer = None
                return

            # DIAGNOSTIC: Log incoming features
            logger.info(f"🔍 zooming_to_features DIAGNOSTIC:")
            logger.info(f"   features count: {len(features) if features else 0}")
            logger.info(f"   expression: '{expression}'")
            if features and len(features) > 0:
                for i, f in enumerate(features[:3]):
                    has_geom = f.hasGeometry() if hasattr(f, 'hasGeometry') else 'N/A'
                    fid = f.id() if hasattr(f, 'id') else 'N/A'
                    logger.info(f"   feature[{i}]: id={fid}, hasGeometry={has_geom}")
                    if has_geom and f.hasGeometry():
                        geom = f.geometry()
                        logger.info(f"      geometry: type={geom.type()}, isEmpty={geom.isEmpty()}")
            
            # IMPROVED: If features list is empty but we have an expression, try to fetch features
            if (not features or not isinstance(features, list) or len(features) == 0) and expression:
                logger.debug(f"zooming_to_features: Empty features list, trying to fetch from expression: {expression}")
                try:
                    qgs_expr = QgsExpression(expression)
                    if qgs_expr.isValid():
                        request = QgsFeatureRequest(qgs_expr)
                        features = list(self.current_layer.getFeatures(request))
                        logger.debug(f"zooming_to_features: Fetched {len(features)} features from expression")
                except Exception as e:
                    logger.warning(f"zooming_to_features: Failed to fetch features from expression: {e}")
            
            # Safety check: ensure features is a list
            if not features or not isinstance(features, list) or len(features) == 0:
                # IMPROVED: Zoom to extent based on current exploring mode
                logger.debug("zooming_to_features: No features provided, computing extent based on mode")
                extent = self._compute_zoom_extent_for_mode()
                if extent and not extent.isEmpty():
                    self.iface.mapCanvas().zoomToFeatureExtent(extent)
                else:
                    logger.debug("zooming_to_features: Empty extent, using canvas refresh")
                    self.iface.mapCanvas().refresh() 

            else: 
                # CRITICAL FIX: For features without geometry, try to reload from layer
                features_with_geometry = []
                for feature in features:
                    if feature.hasGeometry() and not feature.geometry().isEmpty():
                        features_with_geometry.append(feature)
                    else:
                        # Try to reload feature with geometry from layer
                        try:
                            reloaded = self.current_layer.getFeature(feature.id())
                            if reloaded.isValid() and reloaded.hasGeometry() and not reloaded.geometry().isEmpty():
                                features_with_geometry.append(reloaded)
                                logger.debug(f"Reloaded feature {feature.id()} with geometry for zoom")
                            else:
                                logger.warning(f"Could not reload feature {feature.id()} with valid geometry")
                        except Exception as e:
                            logger.warning(f"Error reloading feature {feature.id()}: {e}")

                logger.info(f"   features_with_geometry count: {len(features_with_geometry)}")

                if len(features_with_geometry) == 0:
                    # IMPROVED: Zoom to extent based on current exploring mode
                    logger.debug("zooming_to_features: No features have geometry, computing extent based on mode")
                    extent = self._compute_zoom_extent_for_mode()
                    if extent and not extent.isEmpty():
                        self.iface.mapCanvas().zoomToFeatureExtent(extent)
                    return

                if len(features_with_geometry) == 1:
                    feature = features_with_geometry[0]
                    # CRITICAL: Create a copy to avoid modifying the original geometry
                    geom = QgsGeometry(feature.geometry())
                    
                    # Get CRS information
                    layer_crs = self.current_layer.crs()
                    canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
                    
                    # IMPROVED v2.5.7: Use crs_utils for better CRS detection
                    if CRS_UTILS_AVAILABLE:
                        is_geographic = is_geographic_crs(layer_crs)
                    else:
                        is_geographic = layer_crs.isGeographic()
                    
                    # CRITICAL: For geographic coordinates, switch to a metric CRS for buffer calculations
                    # This ensures accurate buffer distances in meters instead of imprecise degrees
                    if is_geographic:
                        # IMPROVED v2.5.7: Use optimal metric CRS (UTM or Web Mercator)
                        if CRS_UTILS_AVAILABLE:
                            metric_crs_authid = get_optimal_metric_crs(
                                project=QgsProject.instance(),
                                source_crs=layer_crs,
                                extent=geom.boundingBox(),
                                prefer_utm=True
                            )
                            work_crs = QgsCoordinateReferenceSystem(metric_crs_authid)
                            logger.debug(f"FilterMate: Using optimal metric CRS {metric_crs_authid} for zoom buffer")
                        else:
                            # Fallback to Web Mercator
                            work_crs = QgsCoordinateReferenceSystem(DEFAULT_METRIC_CRS)
                            logger.debug(f"FilterMate: Using Web Mercator ({DEFAULT_METRIC_CRS}) for zoom buffer")
                        
                        to_metric = QgsCoordinateTransform(layer_crs, work_crs, QgsProject.instance())
                        geom.transform(to_metric)
                    else:
                        # Already in projected coordinates, use layer CRS
                        work_crs = layer_crs
                    
                    if str(feature.geometry().type()) == 'GeometryType.Point':
                        # Points need a buffer since they have no bounding box
                        buffer_distance = 50  # 50 meters for all points
                        box = geom.buffer(buffer_distance, 5).boundingBox()
                    else:
                        # IMPROVED: For polygons/lines, zoom to the actual feature bounding box
                        # with a small percentage-based padding for better visibility
                        box = geom.boundingBox()
                        if not box.isEmpty():
                            # Add 10% padding based on feature size (minimum 5 meters)
                            width_padding = max(box.width() * 0.1, 5)
                            height_padding = max(box.height() * 0.1, 5)
                            box.grow(max(width_padding, height_padding))
                        else:
                            # Fallback for empty bounding box
                            box.grow(10)
                    
                    # Transform box to canvas CRS if needed
                    if work_crs != canvas_crs:
                        transform = QgsCoordinateTransform(work_crs, canvas_crs, QgsProject.instance())
                        box = transform.transformBoundingBox(box)

                    self.iface.mapCanvas().zoomToFeatureExtent(box)
                else:
                    self.iface.mapCanvas().zoomToFeatureIds(self.current_layer, [feature.id() for feature in features_with_geometry])

            self.iface.mapCanvas().refresh()


    def on_layer_selection_changed(self, selected, deselected, clearAndSelect):
        """
        Slot appelé lorsque la sélection de la couche change.
        Synchronise la sélection QGIS avec les widgets FilterMate si is_selecting est activé.
        Si is_tracking est activé, zoom sur les features sélectionnées.
        
        Args:
            selected: List of added feature IDs
            deselected: List of removed feature IDs  
            clearAndSelect: Boolean indicating if selection was cleared
            
        Note:
            La synchronisation QGIS → widgets n'est active QUE si is_selecting est coché.
            Cela garantit une synchronisation bidirectionnelle cohérente.
        """
        try:
            # CRITICAL: Prevent infinite recursion - skip if we're the ones updating QGIS
            if self._syncing_from_qgis:
                logger.debug("on_layer_selection_changed: Skipping (sync in progress)")
                return
            
            if self.widgets_initialized is True and self.current_layer is not None:
                layer_props = self.PROJECT_LAYERS.get(self.current_layer.id())
                
                if not layer_props:
                    logger.warning(f"on_layer_selection_changed: No layer_props for {self.current_layer.name()}")
                    return
                
                # Get flags
                is_selecting = layer_props.get("exploring", {}).get("is_selecting", False)
                is_tracking = layer_props.get("exploring", {}).get("is_tracking", False)
                
                logger.info(f"on_layer_selection_changed: layer={self.current_layer.name()}, is_selecting={is_selecting}, is_tracking={is_tracking}")
                
                # SYNCHRONISATION: Update FilterMate widgets when QGIS selection changes
                # Active SEULEMENT si is_selecting est coché pour synchronisation bidirectionnelle
                if is_selecting is True:
                    self._sync_widgets_from_qgis_selection()
                
                # TRACKING: Zoom to selected features if tracking is enabled
                if is_tracking is True:
                    # Get currently selected features with geometry
                    selected_feature_ids = self.current_layer.selectedFeatureIds()
                    
                    logger.info(f"TRACKING MODE: {len(selected_feature_ids)} features selected")
                    
                    if len(selected_feature_ids) > 0:
                        # CRITICAL: Fetch features with geometry explicitly
                        request = QgsFeatureRequest().setFilterFids(selected_feature_ids)
                        selected_features = list(self.current_layer.getFeatures(request))
                        
                        logger.info(f"Tracking: zooming to {len(selected_features)} features (IDs: {list(selected_feature_ids)[:5]})")
                        self.zooming_to_features(selected_features)
                    else:
                        logger.debug("on_layer_selection_changed: No features selected for tracking")
                else:
                    logger.debug(f"on_layer_selection_changed: Tracking disabled (is_tracking={is_tracking})")
            else:
                logger.warning(f"on_layer_selection_changed: widgets_initialized={self.widgets_initialized}, current_layer={self.current_layer}")
        except (AttributeError, KeyError, RuntimeError) as e:
            logger.warning(f"Error in on_layer_selection_changed: {type(e).__name__}: {e}")

    
    def _sync_widgets_from_qgis_selection(self):
        """
        Synchronise les widgets single et multiple selection avec la sélection QGIS.
        
        Cette méthode est appelée quand la sélection QGIS change ET que is_selecting est activé.
        Cela permet une synchronisation bidirectionnelle cohérente.
        
        COMPORTEMENT v2.5.9+:
        - Synchronise TOUJOURS les DEUX widgets (single ET multiple) quelle que soit la groupbox active
        - Single selection: sélectionne la première feature si au moins une est sélectionnée
        - Multiple selection: synchronisation complète (coche/décoche toutes les features)
        - Custom selection: pas de synchronisation automatique (basé sur expression)
        
        COMPORTEMENT v2.5.11+:
        - Si plusieurs features sont sélectionnées depuis le canvas ET que le groupbox actif
          est 'single_selection', bascule automatiquement vers 'multiple_selection'
        - Cela garantit que get_current_features() utilise le bon widget
        
        Note:
            Le bouton is_selecting active la synchronisation bidirectionnelle:
            - widgets → QGIS : sélection dans QGIS quand widget change
            - QGIS → widgets : mise à jour widget quand sélection QGIS change
        """
        try:
            if not self.current_layer or not self.widgets_initialized:
                return
            
            # Get selected features from QGIS
            selected_features = self.current_layer.selectedFeatures()
            selected_count = len(selected_features)
            
            # Get layer properties
            layer_props = self.PROJECT_LAYERS.get(self.current_layer.id())
            if not layer_props:
                return
            
            # FIX v2.5.11: Auto-switch to multiple_selection groupbox when multiple features
            # are selected from the canvas while in single_selection mode.
            # This ensures get_current_features() reads from the correct widget.
            if selected_count > 1 and self.current_exploring_groupbox == "single_selection":
                logger.info(f"_sync_widgets_from_qgis_selection: {selected_count} features selected, "
                           f"switching from single_selection to multiple_selection groupbox")
                # Switch groupbox to multiple_selection
                # Use _syncing_from_qgis flag to prevent recursive QGIS selection updates
                # during the groupbox configuration
                self._syncing_from_qgis = True
                try:
                    self._force_exploring_groupbox_exclusive("multiple_selection")
                    self._configure_multiple_selection_groupbox()
                finally:
                    self._syncing_from_qgis = False
            
            # SYNC BOTH WIDGETS regardless of active groupbox (v2.5.9+)
            # This ensures both widgets always reflect the current QGIS selection
            self._sync_single_selection_from_qgis(selected_features, selected_count)
            self._sync_multiple_selection_from_qgis(selected_features, selected_count)
            
        except Exception as e:
            logger.warning(f"Error in _sync_widgets_from_qgis_selection: {type(e).__name__}: {e}")

    
    def _sync_single_selection_from_qgis(self, selected_features, selected_count):
        """
        Synchronise le widget single selection avec la sélection QGIS.
        Appelé AUTOMATIQUEMENT quand is_selecting est actif.
        
        Comportement v2.5.9+:
        - ≥1 feature sélectionnée : synchronise le widget avec la PREMIÈRE feature
        - 0 features : ne modifie pas le widget (garde la valeur actuelle)
        
        IMPORTANT: On n'utilise PAS blockSignals() car cela empêche aussi la mise à jour
        visuelle interne du widget. Le flag _syncing_from_qgis est utilisé dans
        exploring_features_changed() pour éviter les boucles infinies.
        """
        try:
            # Single selection: sync with first feature if at least 1 is selected
            if selected_count >= 1:
                feature = selected_features[0]
                feature_id = feature.id()
                
                feature_picker = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
                
                # Vérifier si la feature est déjà sélectionnée pour éviter des mises à jour inutiles
                current_feature = feature_picker.feature()
                
                if current_feature and current_feature.isValid() and current_feature.id() == feature_id:
                    logger.debug(f"_sync_single_selection_from_qgis: Feature {feature_id} already selected, skipping")
                    return
                
                logger.info(f"_sync_single_selection_from_qgis: Syncing widget to feature ID {feature_id} (first of {selected_count} selected)")
                
                # CRITICAL FIX: Set _syncing_from_qgis flag to prevent infinite loops
                # The signal featureChanged will be emitted and call exploring_features_changed,
                # but that function checks _syncing_from_qgis and won't update QGIS selection
                self._syncing_from_qgis = True
                try:
                    # Set the feature by ID - this triggers internal model update and visual refresh
                    # DO NOT use blockSignals() as it prevents the widget's internal visual update
                    feature_picker.setFeature(feature_id)
                finally:
                    self._syncing_from_qgis = False
                
                # Verify the update worked
                updated_feature = feature_picker.feature()
                if updated_feature and updated_feature.isValid():
                    logger.info(f"_sync_single_selection_from_qgis: Widget now shows feature ID {updated_feature.id()}")
                else:
                    logger.warning(f"_sync_single_selection_from_qgis: Widget update may have failed - feature() returned invalid")
                
        except Exception as e:
            logger.warning(f"Error in _sync_single_selection_from_qgis: {type(e).__name__}: {e}")

    
    def _sync_multiple_selection_from_qgis(self, selected_features, selected_count):
        """
        Synchronise AUTOMATIQUEMENT le widget multiple selection avec la sélection QGIS.
        Appelé automatiquement quand la groupbox multiple_selection est active.
        
        Comportement de synchronisation COMPLÈTE (v2.5.6+):
        - COCHE les features sélectionnées dans QGIS
        - DÉCOCHE les features NON sélectionnées dans QGIS
        - Synchronisation bidirectionnelle complète pour refléter exactement l'état QGIS
        
        Note:
            Contrairement aux versions précédentes qui étaient additives,
            cette synchronisation reflète maintenant EXACTEMENT la sélection QGIS.
        """
        try:
            # Multiple selection: check all selected features in the widget
            multiple_widget = self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"]
            
            if not hasattr(multiple_widget, 'list_widgets'):
                logger.debug("_sync_multiple_selection_from_qgis: No list_widgets attribute")
                return
                
            if self.current_layer.id() not in multiple_widget.list_widgets:
                logger.debug(f"_sync_multiple_selection_from_qgis: Layer {self.current_layer.id()} not in list_widgets")
                return
            
            list_widget = multiple_widget.list_widgets[self.current_layer.id()]
            
            # Get layer properties to find the primary key field name
            layer_props = self.PROJECT_LAYERS.get(self.current_layer.id(), {})
            pk_field_name = layer_props.get("infos", {}).get("primary_key_name", None)
            
            if not pk_field_name:
                logger.warning("_sync_multiple_selection_from_qgis: No primary_key_name found")
                return
            
            # Also get the identifier field name from the widget itself for comparison
            widget_identifier_field = list_widget.getIdentifierFieldName() if hasattr(list_widget, 'getIdentifierFieldName') else None
            
            logger.info(f"_sync_multiple_selection_from_qgis: pk_field_name={pk_field_name}, widget_identifier_field={widget_identifier_field}, selected_count={selected_count}")
            
            # CRITICAL: Use the widget's identifier field name if it differs from pk_field_name
            # The widget stores data using its own identifier_field_name setting
            effective_pk_field = widget_identifier_field if widget_identifier_field else pk_field_name
            
            # Get selected PRIMARY KEY VALUES from QGIS (NOT feature IDs!)
            # data(3) in the widget stores primary key values, not feature.id()
            # CRITICAL: Convert to strings for consistent comparison since widget stores string values
            selected_pk_values = set()
            for f in selected_features:
                try:
                    pk_value = f[effective_pk_field]
                    # Convert to string for consistent comparison with widget data
                    selected_pk_values.add(str(pk_value) if pk_value is not None else pk_value)
                    logger.debug(f"  Selected feature: {effective_pk_field}={pk_value} (type: {type(pk_value).__name__})")
                except (KeyError, IndexError) as e:
                    # Fallback to feature ID if attribute not found
                    logger.warning(f"  Could not get field '{effective_pk_field}' from feature (available: {[field.name() for field in f.fields()]}): {e}")
                    selected_pk_values.add(str(f.id()))
            
            logger.info(f"_sync_multiple_selection_from_qgis: selected_pk_values={selected_pk_values}")
            
            # DEBUG: Show first few widget items for comparison
            if list_widget.count() > 0:
                sample_items = []
                for i in range(min(3, list_widget.count())):
                    item = list_widget.item(i)
                    sample_items.append(f"'{item.data(0)}': pk={item.data(3)} (type={type(item.data(3)).__name__})")
                logger.info(f"_sync_multiple_selection_from_qgis: Widget sample items: {sample_items}")
            
            # SYNCHRONISATION COMPLÈTE: reflète exactement la sélection QGIS
            # - COCHE les features dont la PK est sélectionnée dans QGIS
            # - DÉCOCHE les features dont la PK n'est PAS sélectionnée dans QGIS
            checked_count = 0
            unchecked_count = 0
            found_pk_values = set()
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                item_pk_value = item.data(3)  # data(3) contains PRIMARY KEY value
                # Convert to string for consistent comparison
                item_pk_str = str(item_pk_value) if item_pk_value is not None else item_pk_value
                found_pk_values.add(item_pk_str)
                
                if item_pk_str in selected_pk_values:
                    # CHECK features sélectionnées dans QGIS
                    if item.checkState() != Qt.Checked:
                        item.setCheckState(Qt.Checked)
                        checked_count += 1
                        logger.debug(f"  CHECKING item: {item.data(0)} (pk={item_pk_str})")
                else:
                    # UNCHECK features NON sélectionnées dans QGIS
                    if item.checkState() == Qt.Checked:
                        item.setCheckState(Qt.Unchecked)
                        unchecked_count += 1
                        logger.debug(f"  UNCHECKING item: {item.data(0)} (pk={item_pk_str})")
            
            logger.info(f"_sync_multiple_selection_from_qgis: checked={checked_count}, unchecked={unchecked_count}")
            
            # Update display if any changes were made
            if checked_count > 0 or unchecked_count > 0:
                
                # Set sync flag BEFORE updating to prevent recursion
                self._syncing_from_qgis = True
                try:
                    # Manually update the items display and emit signal
                    # (similar to what updateFeatures does in the task)
                    selection_data = []
                    for i in range(list_widget.count()):
                        item = list_widget.item(i)
                        if item.checkState() == Qt.Checked:
                            selection_data.append([item.data(0), item.data(3), bool(item.data(4))])
                    
                    selection_data.sort(key=lambda k: k[0])
                    multiple_widget.items_le.setText(', '.join([data[0] for data in selection_data]))
                    list_widget.setSelectedFeaturesList(selection_data)
                    
                    # Emit the signal to notify exploring_features_changed
                    # This ensures FilterMate updates its internal state
                    # NOTE: This could trigger exploring_features_changed which might update QGIS selection
                    # if is_selecting is active. The _syncing_from_qgis flag prevents infinite loops.
                    multiple_widget.updatingCheckedItemList.emit(selection_data, True)
                finally:
                    # Always clear the sync flag
                    self._syncing_from_qgis = False
                
        except Exception as e:
            print(f"[FilterMate] ERROR in _sync_multiple_selection_from_qgis: {type(e).__name__}: {e}")
            logger.warning(f"Error in _sync_multiple_selection_from_qgis: {type(e).__name__}: {e}")


    def exploring_source_params_changed(self, expression=None, groupbox_override=None):
        """
        Handle changes to source parameters for exploring features.
        
        PERFORMANCE OPTIMIZATIONS (v2.5.x):
        - Uses debounced handlers to prevent excessive recomputation
        - Caches expression results to avoid redundant evaluations
        - Skips unnecessary updates when expression hasn't changed
        - Provides visual loading feedback during complex operations
        """
        if self.widgets_initialized is True and self.current_layer is not None:

            logger.debug(f"exploring_source_params_changed called with expression={expression}, groupbox_override={groupbox_override}")

            # STABILITY FIX: Verify layer exists in PROJECT_LAYERS before access
            if self.current_layer.id() not in self.PROJECT_LAYERS:
                logger.warning(f"exploring_source_params_changed: layer {self.current_layer.name()} not in PROJECT_LAYERS")
                return

            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]

            # Use groupbox_override if provided, otherwise fall back to current_exploring_groupbox
            target_groupbox = groupbox_override if groupbox_override is not None else self.current_exploring_groupbox
            logger.debug(f"target_groupbox={target_groupbox}")

            if target_groupbox == "single_selection":

                expression = self.widgets["EXPLORING"]["SINGLE_SELECTION_EXPRESSION"]["WIDGET"].expression()
                logger.debug(f"single_selection expression from widget: {expression}")
                if expression is not None:
                    # PERFORMANCE: Skip update if expression hasn't changed
                    current_expression = layer_props["exploring"]["single_selection_expression"]
                    if current_expression == expression:
                        logger.debug("single_selection: Expression unchanged, skipping setDisplayExpression")
                    else:
                        # Update stored expression
                        self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["single_selection_expression"] = expression
                        self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setDisplayExpression(expression)
                        # CRITICAL: Update linked widgets when single selection expression changes
                        self.exploring_link_widgets()
                        # Invalidate cache for this layer since expression changed
                        self.invalidate_expression_cache(self.current_layer.id())

            elif target_groupbox == "multiple_selection":

                expression = self.widgets["EXPLORING"]["MULTIPLE_SELECTION_EXPRESSION"]["WIDGET"].expression()
                if expression is not None:
                    # PERFORMANCE: Skip update if expression hasn't changed
                    current_expression = layer_props["exploring"]["multiple_selection_expression"]
                    if current_expression == expression:
                        logger.debug("multiple_selection: Expression unchanged, skipping setDisplayExpression")
                    else:
                        # Update stored expression
                        self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["multiple_selection_expression"] = expression
                        logger.debug(f"Calling setDisplayExpression with: {expression}")
                        self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setDisplayExpression(expression)
                        # CRITICAL: Update linked widgets when multiple selection expression changes
                        self.exploring_link_widgets()
                        # Invalidate cache for this layer since expression changed
                        self.invalidate_expression_cache(self.current_layer.id())

            elif target_groupbox == "custom_selection":

                expression = self.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"].expression()
                if expression is not None:
                    current_expression = layer_props["exploring"]["custom_selection_expression"]
                    if current_expression != expression:
                        self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["custom_selection_expression"] = expression
                        # PERFORMANCE FIX (v2.5.x): Do NOT call exploring_link_widgets() here
                        # It triggers setFilterExpression which rebuilds the entire feature list
                        # synchronously, freezing QGIS for complex expressions/large datasets.
                        # Link widgets will be updated when user performs an action.
                        # self.exploring_link_widgets(expression)  # DISABLED for performance
                        # Invalidate cache for this layer since expression changed
                        self.invalidate_expression_cache(self.current_layer.id())
                        # PERFORMANCE FIX (v2.5.x): Do NOT call get_current_features() here
                        # Custom expressions can be very complex and evaluating them synchronously
                        # freezes QGIS. Features will be fetched on-demand when user clicks
                        # Filter, Zoom, Flash, or other action buttons.
                        logger.debug("custom_selection: Expression stored, skipping immediate feature evaluation and link_widgets")
                        self._update_buffer_validation()
                        return  # Skip get_current_features() for custom_selection

            self.get_current_features()
            
            # Update buffer validation based on source layer geometry type
            self._update_buffer_validation()

 


    def exploring_custom_selection(self):

        if self.widgets_initialized is True and self.current_layer is not None:

            # CRITICAL: Verify layer exists in PROJECT_LAYERS before access
            if self.current_layer.id() not in self.PROJECT_LAYERS:
                logger.warning(f"exploring_custom_selection: Layer {self.current_layer.name()} not in PROJECT_LAYERS")
                return [], ''

            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
            expression = layer_props["exploring"].get("custom_selection_expression", "")
            features = []
            
            # Check if expression is just a field name (no comparison operators)
            # In this case, we should NOT retrieve features - just pass the expression
            # This allows "FIELD-BASED GEOMETRIC FILTER MODE" to work correctly:
            # - The source layer keeps its existing subset filter
            # - Distant layers are filtered by intersection with filtered source geometries
            is_simple_field = False
            if expression:
                qgs_expr = QgsExpression(expression)
                is_simple_field = qgs_expr.isField() and not any(
                    op in expression for op in ['=', '>', '<', '!', 'IN', 'LIKE', 'AND', 'OR']
                )
            
            if is_simple_field:
                # Field-only expression: return empty features list
                # The filter task will use the existing subset string for source geometry
                logger.debug(f"exploring_custom_selection: Field-only expression '{expression}' - returning empty features list")
                return [], expression
            
            # PERFORMANCE: Check cache for complex expressions
            layer_id = self.current_layer.id()
            cached_features = self._get_cached_expression_result(layer_id, expression)
            if cached_features is not None:
                logger.debug(f"exploring_custom_selection: Using cached result for expression ({len(cached_features)} features)")
                return cached_features, expression
            
            # Complex expression: get matching features
            features = self.exploring_features_changed([], False, expression)
            
            # PERFORMANCE: Cache the result for future use
            if features:
                self._set_cached_expression_result(layer_id, expression, features)
                logger.debug(f"exploring_custom_selection: Cached {len(features)} features for expression")

            return features, expression
        
        return [], ''
    

    def exploring_deselect_features(self):

        if self.widgets_initialized is True and self.current_layer is not None:

            # CRITICAL: Check if layer C++ object has been deleted
            try:
                if sip.isdeleted(self.current_layer):
                    logger.debug("exploring_deselect_features: current_layer C++ object deleted")
                    self.current_layer = None
                    return
            except (RuntimeError, TypeError):
                self.current_layer = None
                return
            
            self.current_layer.removeSelection()
        

    def exploring_select_features(self):
        """
        Select features from the active exploration groupbox.
        
        When IS_SELECTING button is activated, this method retrieves features
        from the current exploration mode (single/multiple/custom) and selects
        them on the layer.
        """
        if self.widgets_initialized is True and self.current_layer is not None:
            
            # CRITICAL: Check if layer C++ object has been deleted
            try:
                if sip.isdeleted(self.current_layer):
                    logger.debug("exploring_select_features: current_layer C++ object deleted")
                    self.current_layer = None
                    return
            except (RuntimeError, TypeError):
                self.current_layer = None
                return
            
            # Get features from the active groupbox
            features, expression = self.get_current_features()
            
            # Select features on the layer
            if len(features) > 0:
                self.current_layer.removeSelection()
                self.current_layer.select([feature.id() for feature in features])


    
    def exploring_features_changed(self, input=[], identify_by_primary_key_name=False, custom_expression=None, preserve_filter_if_empty=False):
        """
        Handle feature selection changes in exploration widgets.
        
        NOTE: This function no longer automatically applies or clears layer filters.
        Filters are only applied via pushbutton actions (Filter, Unfilter, Reset).
        This function only handles feature selection, tracking (zoom), and expression storage.
        
        Args:
            input: Features or feature list to process
            identify_by_primary_key_name: Use primary key for identification
            custom_expression: Custom filter expression
            preserve_filter_if_empty: DEPRECATED - no longer needed since filters aren't auto-applied
        """
        if self.widgets_initialized is True and self.current_layer is not None and isinstance(self.current_layer, QgsVectorLayer):
            
            # CACHE INVALIDATION: Selection is changing, invalidate cache for current groupbox
            # This ensures that subsequent flash/zoom operations use fresh data
            if hasattr(self, '_exploring_cache') and self.current_exploring_groupbox:
                layer_id = self.current_layer.id()
                self._exploring_cache.invalidate(layer_id, self.current_exploring_groupbox)
                logger.debug(f"exploring_features_changed: Invalidated cache for {layer_id[:8]}.../{self.current_exploring_groupbox}")
            
            # Update buffer validation when source features/layer changes
            try:
                self._update_buffer_validation()
            except Exception as e:
                logger.debug(f"Could not update buffer validation: {e}")
            
            # CRITICAL: Check if layer C++ object has been deleted
            try:
                if sip.isdeleted(self.current_layer):
                    logger.debug("exploring_features_changed: current_layer C++ object deleted")
                    self.current_layer = None
                    return []
            except (RuntimeError, TypeError):
                self.current_layer = None
                return []
            
            # Guard: Check if current_layer is in PROJECT_LAYERS
            if self.current_layer.id() not in self.PROJECT_LAYERS:
                logger.warning(f"exploring_features_changed: Layer {self.current_layer.name()} not in PROJECT_LAYERS")
                return []
            
            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
            features, expression = self.get_exploring_features(input, identify_by_primary_key_name, custom_expression)
            
            # PERFORMANCE (v2.5.10): Handle async evaluation for large layers with custom expressions
            # When get_exploring_features returns empty features but valid expression for large layers,
            # it means we should use async evaluation to prevent UI freeze
            if (len(features) == 0 and expression is not None 
                and custom_expression is not None
                and self.should_use_async_expression(custom_expression)):
                
                logger.info(f"exploring_features_changed: Using async evaluation for large layer")
                
                # Define callback to continue processing after async evaluation
                def _on_async_complete(async_features, async_expression, layer_id):
                    """Process features after async evaluation completes."""
                    if layer_id != self.current_layer.id():
                        logger.debug("Async evaluation completed for different layer, ignoring")
                        return
                    
                    # Continue with normal flow using async results
                    self._handle_exploring_features_result(
                        async_features, 
                        async_expression, 
                        layer_props,
                        identify_by_primary_key_name
                    )
                
                def _on_async_error(error_msg, layer_id):
                    """Handle async evaluation errors."""
                    show_warning(
                        self.tr("Expression Evaluation"),
                        self.tr(f"Error evaluating expression: {error_msg}")
                    )
                
                # Start async evaluation
                self.get_exploring_features_async(
                    expression=expression,
                    on_complete=_on_async_complete,
                    on_error=_on_async_error
                )
                
                # Store expression even though features aren't loaded yet
                if expression:
                    layer_props["filtering"]["current_filter_expression"] = expression
                
                return []  # Features will be processed in callback
     
            # Normal synchronous flow for smaller layers or non-custom expressions
            # Process results directly
            return self._handle_exploring_features_result(
                features, expression, layer_props, identify_by_primary_key_name
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
        Handle the result of get_exploring_features (sync or async).
        
        This method processes the features and expression returned by get_exploring_features,
        handling selection, tracking, and expression storage.
        
        Args:
            features: List of QgsFeature objects
            expression: Filter expression string
            layer_props: Layer properties dict from PROJECT_LAYERS
            identify_by_primary_key_name: Whether primary key was used
            
        Returns:
            List of features processed
        """
        if not self.widgets_initialized or self.current_layer is None:
            return []
     
        # CRITICAL FIX: Only call exploring_link_widgets if is_linking is enabled
        # When is_linking is False, calling link_widgets would refresh widgets unnecessarily
        # and potentially interrupt user selection in progress
        if layer_props["exploring"].get("is_linking", False):
            # CRITICAL: Block signals on widgets before calling exploring_link_widgets to prevent
            # recursive signal triggers when setFilterExpression modifies the feature picker
            single_widget = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
            multiple_widget = self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"]
            
            single_widget.blockSignals(True)
            multiple_widget.blockSignals(True)
            
            try:
                self.exploring_link_widgets()
            finally:
                # Always unblock signals
                single_widget.blockSignals(False)
                multiple_widget.blockSignals(False)

        # NOTE: Filter application is now ONLY triggered by pushbutton actions (Filter, Unfilter, Reset)
        # This function no longer automatically applies or clears filters when features change.
        # The expression is stored for use by the filter task when the user clicks Filter.
        if expression is not None and expression != '':
            # Store current expression for later use by filter task
            layer_props["filtering"]["current_filter_expression"] = expression
            logger.debug(f"_handle_exploring_features_result: Stored filter expression: {expression[:60]}...")

        if len(features) == 0:
            logger.debug("_handle_exploring_features_result: No features to process")
            # Only clear selection if is_selecting is active AND we're not syncing from QGIS
            if layer_props["exploring"].get("is_selecting", False) and not self._syncing_from_qgis:
                self.current_layer.removeSelection()
            return []
    
        # CRITICAL: Synchronize QGIS selection with FilterMate features when is_selecting is active
        # Skip if we're currently syncing FROM QGIS to prevent infinite loops
        if layer_props["exploring"].get("is_selecting", False) and not self._syncing_from_qgis:
            self.current_layer.removeSelection()
            self.current_layer.select([feature.id() for feature in features])
            logger.debug(f"_handle_exploring_features_result: Synchronized QGIS selection ({len(features)} features)")

        if layer_props["exploring"].get("is_tracking", False):
            logger.debug(f"_handle_exploring_features_result: Tracking {len(features)} features")
            self.zooming_to_features(features)  

        return features


    def get_exploring_features(self, input, identify_by_primary_key_name=False, custom_expression=None):

        if self.widgets_initialized and self.current_layer is not None:

            # CRITICAL: Check if layer C++ object has been deleted
            try:
                if sip.isdeleted(self.current_layer):
                    logger.debug("get_exploring_features: current_layer C++ object deleted")
                    self.current_layer = None
                    return [], None
            except (RuntimeError, TypeError):
                self.current_layer = None
                return [], None

            if self.current_layer is None:
                return [], None
            
            # Guard: Handle invalid input types (e.g., False from currentSelectedFeatures())
            if input is False or input is None:
                logger.debug("get_exploring_features: Input is False or None, returning empty")
                return [], None
            
            # STABILITY FIX: Verify layer exists in PROJECT_LAYERS before access
            if self.current_layer.id() not in self.PROJECT_LAYERS:
                logger.warning(f"get_exploring_features: Layer {self.current_layer.name()} not in PROJECT_LAYERS")
                return [], None
            
            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
            features = []
            expression = None

            if isinstance(input, QgsFeature):
                # Check if input feature is valid
                if not input.isValid():
                    logger.debug("get_exploring_features: Input feature is invalid, returning empty")
                    return [], None
                
                # DIAGNOSTIC: Log input feature state
                logger.debug(f"get_exploring_features: input feature id={input.id()}, hasGeometry={input.hasGeometry()}")
                    
                if identify_by_primary_key_name is True:
                    # CRITICAL FIX: Check if primary_key_name exists in layer properties
                    pk_name = layer_props["infos"].get("primary_key_name")
                    
                    if pk_name is None:
                        # Primary key not detected - use universal $id fallback
                        logger.debug(f"No primary_key_name in layer properties, using $id fallback")
                        provider_type = layer_props["infos"].get("layer_provider_type", "")
                        feature_id = input.id()
                        
                        # UNIVERSAL FALLBACK: Use $id which works for all providers
                        # $id is QGIS internal feature ID, works regardless of provider
                        expression = f'$id = {feature_id}'
                        logger.debug(f"Using universal $id fallback expression: {expression}")
                        
                        # For OGR layers, also try "fid" field as alternative
                        if provider_type == 'ogr':
                            # Check if fid field exists
                            fid_idx = self.current_layer.fields().indexFromName('fid')
                            if fid_idx >= 0:
                                expression = f'"fid" = {feature_id}'
                                logger.debug(f"OGR layer: using fid field expression: {expression}")
                        
                        # Always reload feature to ensure geometry is available
                        try:
                            reloaded_feature = self.current_layer.getFeature(input.id())
                            if reloaded_feature.isValid() and reloaded_feature.hasGeometry():
                                features = [reloaded_feature]
                                logger.debug(f"Reloaded feature {input.id()} with geometry")
                            else:
                                features = [input]
                                logger.warning(f"Could not reload feature {input.id()} with geometry")
                        except Exception as e:
                            logger.debug(f"Could not reload feature: {e}")
                            features = [input]
                        return features, expression
                    
                    # Try to get the primary key value using multiple methods
                    pk_value = None
                    try:
                        # First try with attribute() method
                        pk_value = input.attribute(pk_name)
                    except (KeyError, IndexError):
                        try:
                            # Fallback to field index
                            fields = input.fields()
                            idx = fields.indexFromName(pk_name)
                            if idx >= 0:
                                pk_value = input.attributes()[idx]
                        except (AttributeError, IndexError, KeyError) as e:
                            logger.warning(f"Could not get primary key value for feature: {type(e).__name__}: {e}")
                            logger.debug(f"pk_name: {pk_name}, feature fields: {[f.name() for f in input.fields()]}")
                    
                    if pk_value is not None:
                        pk_is_numeric = layer_props["infos"].get("primary_key_is_numeric", False)
                        provider_type = layer_props["infos"].get("layer_provider_type", "")
                        
                        # CRITICAL FIX: Field names must be quoted for QgsExpression to work
                        # This applies to ALL providers (PostgreSQL, OGR, Spatialite)
                        # Note: filter_task.py handles qualified names for PostgreSQL subsetString separately
                        if pk_is_numeric is True: 
                            expression = f'"{pk_name}" = {pk_value}'
                        else:
                            expression = f'"{pk_name}" = \'{pk_value}\''
                        logger.debug(f"Generated expression for {provider_type}: {expression}")
                        
                        # CRITICAL: Also reload feature to ensure geometry is available for zoom
                        try:
                            reloaded_feature = self.current_layer.getFeature(input.id())
                            if reloaded_feature.isValid() and reloaded_feature.hasGeometry():
                                features = [reloaded_feature]
                                logger.debug(f"Reloaded feature {input.id()} with geometry")
                            else:
                                features = [input]
                        except Exception as e:
                            logger.debug(f"Could not reload feature: {e}")
                            features = [input]
                    else:
                        # UNIVERSAL FALLBACK: If we can't get the primary key value, use $id
                        provider_type = layer_props["infos"].get("layer_provider_type", "")
                        feature_id = input.id()
                        
                        # Use $id as universal fallback - works for all providers
                        expression = f'$id = {feature_id}'
                        logger.debug(f"pk_value not found, using universal $id fallback: {expression}")
                        
                        # For OGR layers, also try "fid" field as alternative
                        if provider_type == 'ogr':
                            fid_idx = self.current_layer.fields().indexFromName('fid')
                            if fid_idx >= 0:
                                expression = f'"fid" = {feature_id}'
                                logger.debug(f"OGR layer fallback: using fid field expression: {expression}")
                        
                        # Reload feature from layer by ID for geometry
                        try:
                            reloaded_feature = self.current_layer.getFeature(input.id())
                            if reloaded_feature.isValid() and reloaded_feature.hasGeometry():
                                features = [reloaded_feature]
                            else:
                                features = [input]
                        except (RuntimeError, KeyError, AttributeError) as e:
                            features = [input]
                            logger.debug(f"Error reloading feature: {e}")
                        logger.debug(f"Could not access primary key '{pk_name}' in feature. "
                                    f"Available fields: {[f.name() for f in input.fields()]}. Using $id fallback.")
                else:
                    # CRITICAL: Reload feature from layer to ensure geometry is loaded
                    # QgsFeaturePickerWidget.featureChanged may emit features without geometry
                    try:
                        reloaded_feature = self.current_layer.getFeature(input.id())
                        if reloaded_feature.isValid() and reloaded_feature.hasGeometry():
                            features = [reloaded_feature]
                            logger.debug(f"Reloaded feature {input.id()} with geometry for tracking")
                        else:
                            features = [input]
                    except Exception as e:
                        logger.debug(f"Could not reload feature {input.id()}: {e}")
                        features = [input]

            elif isinstance(input, list):
                if len(input) == 0 and custom_expression is None:
                    return features, expression
                
                if identify_by_primary_key_name is True:
                    # FALLBACK FIX: Safely get primary key with fallback to feature ID ($id)
                    pk_name = layer_props["infos"].get("primary_key_name")
                    pk_is_numeric = layer_props["infos"].get("primary_key_is_numeric", True)
                    provider_type = layer_props["infos"].get("layer_provider_type", "")
                    
                    if pk_name is None:
                        # FALLBACK: Use feature IDs directly when no primary key is available
                        # input format from CustomCheckableFeatureComboBox: [(display_value, pk_value, ...), ...]
                        # When pk_name is None, feat[1] may be the feature id
                        logger.debug(f"No primary_key_name available for list input, using $id fallback")
                        try:
                            # Try to extract feature IDs from input
                            # Format depends on how the list was built
                            feature_ids = []
                            for feat in input:
                                if isinstance(feat, (list, tuple)) and len(feat) > 1:
                                    # Assume feat[1] contains an ID-like value
                                    feature_ids.append(str(feat[1]))
                                elif isinstance(feat, QgsFeature):
                                    feature_ids.append(str(feat.id()))
                            
                            if feature_ids:
                                expression = f'$id IN ({", ".join(feature_ids)})'
                                logger.debug(f"Generated $id fallback expression: {expression}")
                        except Exception as e:
                            logger.warning(f"Could not generate fallback expression for list: {e}")
                            # Return features directly without expression if we can't build one
                            for feat in input:
                                if isinstance(feat, QgsFeature):
                                    features.append(feat)
                            return features, None
                    else:
                        # CRITICAL FIX: Field names must be quoted for QgsExpression to work
                        # This applies to ALL providers (PostgreSQL, OGR, Spatialite)
                        if pk_is_numeric is True:
                            input_ids = [str(feat[1]) for feat in input]  
                            expression = f'"{pk_name}" IN ({", ".join(input_ids)})'
                        else:
                            input_ids = [str(feat[1]) for feat in input]
                            quoted_ids = "', '".join(input_ids)
                            expression = f'"{pk_name}" IN (\'{quoted_ids}\')'
                        logger.debug(f"Generated list expression for {provider_type}: {expression}")
                
            if custom_expression is not None:
                    expression = custom_expression

            if QgsExpression(expression).isValid():
                # PERFORMANCE (v2.5.10): Use async evaluation for large layers with complex expressions
                # This prevents UI freezes when evaluating expressions on 10k+ feature layers
                feature_count = self.current_layer.featureCount()
                use_async = (
                    ASYNC_EXPRESSION_AVAILABLE 
                    and self._expression_manager is not None
                    and feature_count > self._async_expression_threshold
                    and custom_expression is not None  # Only for custom expressions
                )
                
                if use_async:
                    # For large layers, return expression only - features will be loaded async
                    # The caller should use get_exploring_features_async for actual feature loading
                    logger.debug(
                        f"get_exploring_features: Large layer ({feature_count} features), "
                        f"returning expression only for async evaluation"
                    )
                    return [], expression
                
                # Synchronous evaluation for smaller layers
                features_iterator = self.current_layer.getFeatures(QgsFeatureRequest(QgsExpression(expression)))
                done_looping = False
                
                while not done_looping:
                    try:
                        feature = next(features_iterator)
                        features.append(feature)
                    except StopIteration:
                        done_looping = True
            else:
                expression = None

            return features, expression
    
    def get_exploring_features_async(
        self, 
        expression: str,
        on_complete=None,
        on_error=None,
        on_progress=None
    ):
        """
        Evaluate an expression asynchronously for large layers.
        
        This method uses QgsTask to evaluate expressions in a background thread,
        preventing UI freezes for large datasets with complex expressions.
        
        PERFORMANCE (v2.5.10): For layers with >10k features and custom expressions,
        this method should be used instead of the synchronous get_exploring_features.
        
        Args:
            expression: QGIS expression string to evaluate
            on_complete: Callback(features, expression, layer_id) called on success
            on_error: Callback(error_msg, layer_id) called on error
            on_progress: Callback(current, total, layer_id) for progress updates
            
        Returns:
            ExpressionEvaluationTask if started, None if not available or invalid
        """
        if not ASYNC_EXPRESSION_AVAILABLE or self._expression_manager is None:
            logger.warning("Async expression evaluation not available")
            if on_error:
                on_error("Async evaluation not available", "")
            return None
        
        if self.current_layer is None or not self.current_layer.isValid():
            logger.warning("Cannot evaluate expression: no valid layer")
            if on_error:
                on_error("No valid layer", "")
            return None
        
        if not expression:
            logger.warning("Cannot evaluate empty expression")
            if on_error:
                on_error("Empty expression", self.current_layer.id() if self.current_layer else "")
            return None
        
        # Set loading state
        self._set_expression_loading_state(True)
        
        # Wrap callbacks to handle UI state
        def _on_complete_wrapper(features, expr, layer_id):
            self._set_expression_loading_state(False)
            self._pending_async_evaluation = None
            
            # Cache the result
            if features and expr:
                self._set_cached_expression_result(layer_id, expr, features)
            
            if on_complete:
                on_complete(features, expr, layer_id)
        
        def _on_error_wrapper(error_msg, layer_id):
            self._set_expression_loading_state(False)
            self._pending_async_evaluation = None
            logger.error(f"Async expression evaluation failed: {error_msg}")
            if on_error:
                on_error(error_msg, layer_id)
        
        def _on_cancelled_wrapper(layer_id):
            self._set_expression_loading_state(False)
            self._pending_async_evaluation = None
            logger.debug(f"Async expression evaluation cancelled for {layer_id}")
        
        # Start async evaluation
        task = self._expression_manager.evaluate(
            layer=self.current_layer,
            expression=expression,
            on_complete=_on_complete_wrapper,
            on_error=_on_error_wrapper,
            on_progress=on_progress,
            on_cancelled=_on_cancelled_wrapper,
            cancel_existing=True,
            description=f"FilterMate: Evaluating expression on {self.current_layer.name()}"
        )
        
        if task:
            self._pending_async_evaluation = task
            logger.debug(f"Started async expression evaluation for {self.current_layer.name()}")
        
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
        
    
    def exploring_link_widgets(self, expression=None):

        if self.widgets_initialized and self.current_layer is not None:

            # CRITICAL: Verify layer exists in PROJECT_LAYERS before access
            if self.current_layer.id() not in self.PROJECT_LAYERS:
                logger.debug(f"exploring_link_widgets: Layer {self.current_layer.name()} not in PROJECT_LAYERS")
                return

            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
            custom_filter = None
            layer_features_source = self.current_layer.dataProvider().featureSource() 
            
            # Ensure is_linking property exists (backward compatibility)
            if "is_linking" not in layer_props["exploring"]:
                layer_props["exploring"]["is_linking"] = False
            
            # Helper function to set filter expression only if it changed
            # This prevents unnecessary widget refreshes that interrupt user selection
            def _safe_set_single_filter(new_filter):
                """Set filter expression on single selection widget only if changed."""
                single_widget = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
                current_filter = single_widget.filterExpression() if hasattr(single_widget, 'filterExpression') else ''
                # Normalize None to empty string for comparison
                new_filter = new_filter or ''
                current_filter = current_filter or ''
                if new_filter.strip() != current_filter.strip():
                    logger.debug(f"exploring_link_widgets: Updating single selection filter: '{current_filter[:30]}' -> '{new_filter[:30]}'")
                    single_widget.setFilterExpression(new_filter)
                    return True
                return False
            
            if layer_props["exploring"]["is_linking"]:
                   

                if QgsExpression(layer_props["exploring"]["custom_selection_expression"]).isValid():
                    if not QgsExpression(layer_props["exploring"]["custom_selection_expression"]).isField():
                        custom_filter = layer_props["exploring"]["custom_selection_expression"]
                        self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setFilterExpression(custom_filter, layer_props)
                if expression is not None:
                    _safe_set_single_filter(expression)
                elif self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].currentSelectedFeatures() is not False:
                    features, expression = self.get_exploring_features(self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].currentSelectedFeatures(), True)
                    if len(features) > 0 and expression is not None:
                        _safe_set_single_filter(expression)
                elif self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].currentVisibleFeatures() is not False:
                    features, expression = self.get_exploring_features(self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].currentVisibleFeatures(), True)
                    if len(features) > 0 and expression is not None:
                        _safe_set_single_filter(expression)
                elif custom_filter is not None:
                    _safe_set_single_filter(custom_filter)
                
                multiple_display_expression = layer_props["exploring"]["multiple_selection_expression"]
                if QgsExpression(multiple_display_expression).isField():
                    multiple_display_expression = multiple_display_expression.replace('"','')

                single_display_expression = layer_props["exploring"]["single_selection_expression"]
                if QgsExpression(single_display_expression).isField():
                    single_display_expression = single_display_expression.replace('"','')

                if QgsExpression(single_display_expression).isValid() and single_display_expression == layer_props["infos"]["primary_key_name"]:
                    if QgsExpression(multiple_display_expression).isValid() and multiple_display_expression != layer_props["infos"]["primary_key_name"]:
                        self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["single_selection_expression"] = multiple_display_expression
                        self.widgets["EXPLORING"]["SINGLE_SELECTION_EXPRESSION"]["WIDGET"].setExpression(multiple_display_expression)
                        self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setDisplayExpression(multiple_display_expression)

                if QgsExpression(multiple_display_expression).isValid() and multiple_display_expression == layer_props["infos"]["primary_key_name"]:
                    if QgsExpression(single_display_expression).isValid() and single_display_expression != layer_props["infos"]["primary_key_name"]:
                        self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["multiple_selection_expression"] = single_display_expression
                        self.widgets["EXPLORING"]["MULTIPLE_SELECTION_EXPRESSION"]["WIDGET"].setExpression(single_display_expression)
                        self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setDisplayExpression(single_display_expression)

            
            else:
                # NOTE: When is_linking is False, we only clear the filter expressions
                # if they are not already empty. This prevents unnecessary widget refreshes
                # that could interrupt user selection in progress.
                # CRITICAL FIX: Check if filter expression is already empty before clearing
                single_widget = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
                multiple_widget = self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"]
                
                # Only clear single selection filter if it's not already empty
                current_single_filter = single_widget.filterExpression() if hasattr(single_widget, 'filterExpression') else ''
                if current_single_filter and current_single_filter.strip() != '':
                    logger.debug(f"exploring_link_widgets: is_linking=False, clearing single selection filter (was: '{current_single_filter[:30]}...')")
                    single_widget.setFilterExpression('')
                
                # Only clear multiple selection filter if it's not already empty
                if self.current_layer is not None and hasattr(multiple_widget, 'list_widgets') and self.current_layer.id() in multiple_widget.list_widgets:
                    current_multiple_filter = multiple_widget.list_widgets[self.current_layer.id()].getFilterExpression()
                    if current_multiple_filter and current_multiple_filter.strip() != '':
                        logger.debug(f"exploring_link_widgets: is_linking=False, clearing multiple selection filter (was: '{current_multiple_filter[:30]}...')")
                        multiple_widget.setFilterExpression('', layer_props)


    def get_layers_to_filter(self):

        if self.widgets_initialized is True and self.current_layer is not None:

            checked_list_data = []
            widget = self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"]
            total_items = widget.count()
            
            logger.info(f"=== get_layers_to_filter DIAGNOSTIC ===")
            logger.info(f"  Total items in combobox: {total_items}")
            
            for i in range(total_items):
                item_text = widget.itemText(i)
                check_state = widget.itemCheckState(i)
                data = widget.itemData(i, Qt.UserRole)
                
                logger.debug(f"  Item {i}: '{item_text}' | checked={check_state == Qt.Checked} | data={data}")
                
                if check_state == Qt.Checked:
                    if isinstance(data, dict) and "layer_id" in data:
                        checked_list_data.append(data["layer_id"])
                        logger.info(f"  ✓ CHECKED: {item_text} -> layer_id={data['layer_id'][:8]}...")
                    elif isinstance(data, str):
                        # Backward compatibility with old format
                        checked_list_data.append(data)
                        logger.info(f"  ✓ CHECKED (legacy): {item_text} -> {data[:8]}...")
            
            logger.info(f"  Total checked layers: {len(checked_list_data)}")
            logger.info(f"=== END get_layers_to_filter ===")
            return checked_list_data

        return []


    def get_layers_to_export(self):

        if self.widgets_initialized is True and self.current_layer is not None:

            checked_list_data = []
            for i in range(self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].count()):
                if self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].itemCheckState(i) == Qt.Checked:
                    data = self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].itemData(i, Qt.UserRole)
                    if isinstance(data, str):
                        checked_list_data.append(data)
            return checked_list_data


    def get_current_crs_authid(self):
        
        if self.widgets_initialized is True and self.has_loaded_layers is True:

            return self.widgets["EXPORTING"]["PROJECTION_TO_EXPORT"]["WIDGET"].crs().authid()
    
    def _validate_and_prepare_layer(self, layer):
        """
        Validate layer and prepare for layer change operation.
        
        Returns tuple: (should_continue, layer, layer_props)
        - should_continue: False if layer change should be aborted
        - layer: The validated layer object
        - layer_props: Layer properties from PROJECT_LAYERS
        """
        # STABILITY FIX: Check if plugin is busy with critical operations
        if self._plugin_busy:
            logger.debug("Plugin is busy, deferring layer validation")
            return (False, None, None)
        
        # STABILITY FIX: Verify PROJECT_LAYERS is not empty
        if not self.PROJECT_LAYERS:
            logger.debug("PROJECT_LAYERS is empty, cannot validate layer")
            return (False, None, None)
        
        # Skip raster layers - FilterMate only handles vector layers
        if layer is not None and not isinstance(layer, QgsVectorLayer):
            return (False, None, None)
        
        # STABILITY FIX: Verify the layer C++ object is still valid
        if layer is not None:
            try:
                # Test if the layer is still valid (not a deleted C++ object)
                _ = layer.id()
            except RuntimeError:
                logger.warning("Layer object was deleted (C++ object invalid), skipping")
                return (False, None, None)
        
        # Reject invalid/broken-source layers to avoid selection
        if layer is None:
            return (False, None, None)
        try:
            if not is_layer_source_available(layer):
                logger.warning(f"current_layer_changed: rejecting invalid or missing-source layer '{layer.name()}'")
                try:
                    show_warning(
                        "FilterMate",
                        "La couche sélectionnée est invalide ou sa source est introuvable. Sélection annulée."
                    )
                except (RuntimeError, AttributeError) as e:
                    logger.debug(f"Could not show warning message: {e}")
                # Revert combo selection to previous valid layer if possible
                try:
                    prev = self.current_layer if isinstance(self.current_layer, QgsVectorLayer) and is_layer_source_available(self.current_layer) else None
                    self.manageSignal(["FILTERING","CURRENT_LAYER"], 'disconnect')
                    self.widgets["FILTERING"]["CURRENT_LAYER"]["WIDGET"].setLayer(prev)
                    self.manageSignal(["FILTERING","CURRENT_LAYER"], 'connect', 'layerChanged')
                except Exception as _e:
                    logger.debug(f"Could not revert current layer selection: {_e}")
                return (False, None, None)
        except Exception as _e:
            logger.debug(f"Error while validating layer availability: {_e}")
            return (False, None, None)

        # Note: Recursive call check is now done at the beginning of current_layer_changed()
        
        if not self.widgets_initialized:
            return (False, None, None)
        
        # Disconnect selectionChanged signal from previous layer
        if self.current_layer is not None and self.current_layer_selection_connection is not None:
            try:
                self.current_layer.selectionChanged.disconnect(self.on_layer_selection_changed)
                self.current_layer_selection_connection = None
            except (TypeError, RuntimeError) as e:
                logger.debug(f"Could not disconnect selectionChanged signal from previous layer: {type(e).__name__}: {e}")
                self.current_layer_selection_connection = None
        
        self.current_layer = layer
        
        # Verify layer exists in PROJECT_LAYERS before proceeding
        if self.current_layer.id() not in self.PROJECT_LAYERS:
            return (False, None, None)
        
        # Emit signal to notify app that current layer changed
        self.currentLayerChanged.emit()
        
        layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
        
        # DEBUG: Log layer_props to verify correct properties
        logger.debug(f"Layer {self.current_layer.name()} (id: {self.current_layer.id()}) properties:")
        logger.debug(f"  - primary_key: {layer_props.get('infos', {}).get('primary_key_name', 'N/A')}")
        logger.debug(f"  - single_selection_expression: {layer_props.get('exploring', {}).get('single_selection_expression', 'N/A')}")
        logger.debug(f"  - multiple_selection_expression: {layer_props.get('exploring', {}).get('multiple_selection_expression', 'N/A')}")
        
        return (True, layer, layer_props)
    
    def _reset_layer_expressions(self, layer_props):
        """
        Reset exploring expressions to primary_key_name of new layer when switching.
        
        This prevents KeyError when field names from previous layer don't exist in new layer.
        Normalizes expressions by removing quotes before comparison with layer fields.
        """
        primary_key = layer_props["infos"]["primary_key_name"]
        layer_fields = [field.name() for field in self.current_layer.fields()]
        
        logger.debug(f"_reset_layer_expressions: Layer '{self.current_layer.name()}', primary_key='{primary_key}', fields={layer_fields}")
        
        def normalize_field_name(expr):
            """Remove surrounding quotes from field expression for comparison."""
            if not expr:
                return ""
            # Remove surrounding double quotes (QGIS field syntax)
            normalized = expr.strip().strip('"')
            return normalized
        
        def is_valid_field_expression(expr, fields):
            """Check if expression is a valid field name for this layer."""
            if not expr:
                return False
            normalized = normalize_field_name(expr)
            # Check if it's a simple field name (not a complex expression)
            if normalized in fields:
                return True
            # Also check the original in case it's a valid expression
            if expr in fields:
                return True
            return False
        
        # Ensure primary_key itself is valid; if not, use the first available field
        fallback_field = primary_key
        if primary_key and primary_key not in layer_fields:
            if layer_fields:
                fallback_field = layer_fields[0]
                logger.warning(f"Primary key '{primary_key}' not found in layer '{self.current_layer.name()}'. Using fallback field '{fallback_field}'")
            else:
                logger.error(f"Layer '{self.current_layer.name()}' has no fields available")
                return
        
        # Reset single_selection_expression if invalid for current layer
        single_expr = layer_props["exploring"].get("single_selection_expression", "")
        logger.debug(f"Checking single_selection_expression: '{single_expr}' - valid: {is_valid_field_expression(single_expr, layer_fields)}")
        if not is_valid_field_expression(single_expr, layer_fields):
            logger.info(f"Resetting single_selection_expression from '{single_expr}' to '{fallback_field}' (field not in layer)")
            layer_props["exploring"]["single_selection_expression"] = fallback_field
        
        # Reset multiple_selection_expression if invalid for current layer
        multiple_expr = layer_props["exploring"].get("multiple_selection_expression", "")
        logger.debug(f"Checking multiple_selection_expression: '{multiple_expr}' - valid: {is_valid_field_expression(multiple_expr, layer_fields)}")
        if not is_valid_field_expression(multiple_expr, layer_fields):
            logger.info(f"Resetting multiple_selection_expression from '{multiple_expr}' to '{fallback_field}' (field not in layer)")
            layer_props["exploring"]["multiple_selection_expression"] = fallback_field
        
        # Reset custom_selection_expression if invalid for current layer
        custom_expr = layer_props["exploring"].get("custom_selection_expression", "")
        # For custom expressions, only reset if it's a field expression that doesn't exist
        if custom_expr:
            qgs_expr = QgsExpression(custom_expr)
            if qgs_expr.isField() and not is_valid_field_expression(custom_expr, layer_fields):
                logger.debug(f"Resetting custom_selection_expression from '{custom_expr}' to '{fallback_field}' (field not in layer)")
                layer_props["exploring"]["custom_selection_expression"] = fallback_field
        elif not custom_expr:
            layer_props["exploring"]["custom_selection_expression"] = fallback_field
    
    def _disconnect_layer_signals(self):
        """
        Disconnect all layer-related widget signals before updating.
        
        Returns list of widget paths that were disconnected (for later reconnection).
        """
        widgets_to_stop = [
            ["EXPLORING","SINGLE_SELECTION_FEATURES"],
            ["EXPLORING","SINGLE_SELECTION_EXPRESSION"],
            ["EXPLORING","MULTIPLE_SELECTION_FEATURES"],
            ["EXPLORING","MULTIPLE_SELECTION_EXPRESSION"],
            ["EXPLORING", "CUSTOM_SELECTION_EXPRESSION"],
            ["EXPLORING", "IS_SELECTING"],
            ["EXPLORING", "IS_TRACKING"],
            ["EXPLORING", "IS_LINKING"],
            ["EXPLORING", "RESET_ALL_LAYER_PROPERTIES"],
            ["FILTERING","CURRENT_LAYER"],
            ["FILTERING","HAS_LAYERS_TO_FILTER"],
            ["FILTERING", "LAYERS_TO_FILTER"],
            ["FILTERING","HAS_COMBINE_OPERATOR"],
            ["FILTERING","SOURCE_LAYER_COMBINE_OPERATOR"],
            ["FILTERING", "OTHER_LAYERS_COMBINE_OPERATOR"],
            ["FILTERING","HAS_GEOMETRIC_PREDICATES"],
            ["FILTERING", "GEOMETRIC_PREDICATES"],
            ["FILTERING","HAS_BUFFER_VALUE"],
            ["FILTERING","BUFFER_VALUE"],
            ["FILTERING","BUFFER_VALUE_PROPERTY"],
            ["FILTERING","HAS_BUFFER_TYPE"],
            ["FILTERING","BUFFER_TYPE"]
        ]
        
        for widget_path in widgets_to_stop:
            self.manageSignal(widget_path, 'disconnect')
        
        # STABILITY FIX: Clear expressions before layer change to prevent residual values
        try:
            if "SINGLE_SELECTION_EXPRESSION" in self.widgets.get("EXPLORING", {}):
                self.widgets["EXPLORING"]["SINGLE_SELECTION_EXPRESSION"]["WIDGET"].setExpression("")
            if "MULTIPLE_SELECTION_EXPRESSION" in self.widgets.get("EXPLORING", {}):
                self.widgets["EXPLORING"]["MULTIPLE_SELECTION_EXPRESSION"]["WIDGET"].setExpression("")
            if "CUSTOM_SELECTION_EXPRESSION" in self.widgets.get("EXPLORING", {}):
                self.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"].setExpression("")
        except Exception as e:
            logger.debug(f"Could not clear expressions before layer change: {e}")
        
        if self.project_props["OPTIONS"]["LAYERS"]["LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"] is True:
            widget_path = ["QGIS","LAYER_TREE_VIEW"]
            self.manageSignal(widget_path, 'disconnect')
        
        return widgets_to_stop
    
    def _detect_multi_step_filter(self, layer, layer_props):
        """
        Detect if source layer or distant layers already have a subsetString (existing filter).
        
        When existing filters are detected, automatically enable additive filter mode.
        Uses existing combinator params if set, otherwise defaults to AND operator.
        
        Args:
            layer: The current source layer
            layer_props: Layer properties dictionary
            
        Returns:
            bool: True if existing filters were detected and additive mode was enabled
        """
        try:
            has_existing_filter = False
            
            # Check source layer for existing subset
            if layer and hasattr(layer, 'subsetString'):
                source_subset = layer.subsetString()
                if source_subset and source_subset.strip():
                    has_existing_filter = True
                    logger.debug(f"Multi-step filter detected: source layer '{layer.name()}' has subset: {source_subset[:50]}...")
            
            # Check distant layers (layers_to_filter) for existing subsets
            if not has_existing_filter and layer_props.get("filtering", {}).get("has_layers_to_filter", False):
                layers_to_filter = layer_props.get("filtering", {}).get("layers_to_filter", [])
                for layer_id in layers_to_filter:
                    distant_layer = QgsProject.instance().mapLayer(layer_id)
                    if distant_layer and hasattr(distant_layer, 'subsetString'):
                        distant_subset = distant_layer.subsetString()
                        if distant_subset and distant_subset.strip():
                            has_existing_filter = True
                            logger.debug(f"Multi-step filter detected: distant layer '{distant_layer.name()}' has subset: {distant_subset[:50]}...")
                            break
            
            # If existing filters detected, enable additive filter
            if has_existing_filter:
                # Only update if not already enabled (preserve user choice)
                if not layer_props.get("filtering", {}).get("has_combine_operator", False):
                    layer_props["filtering"]["has_combine_operator"] = True
                    # Use existing combinator params if set, otherwise default to AND
                    if not layer_props["filtering"].get("source_layer_combine_operator"):
                        layer_props["filtering"]["source_layer_combine_operator"] = "AND"
                    if not layer_props["filtering"].get("other_layers_combine_operator"):
                        layer_props["filtering"]["other_layers_combine_operator"] = "AND"
                    
                    # Set combobox widgets to index 0 (AND) for additive mode on pre-filtered layer
                    try:
                        self.widgets["FILTERING"]["SOURCE_LAYER_COMBINE_OPERATOR"]["WIDGET"].blockSignals(True)
                        self.widgets["FILTERING"]["SOURCE_LAYER_COMBINE_OPERATOR"]["WIDGET"].setCurrentIndex(0)
                        self.widgets["FILTERING"]["SOURCE_LAYER_COMBINE_OPERATOR"]["WIDGET"].blockSignals(False)
                        
                        self.widgets["FILTERING"]["OTHER_LAYERS_COMBINE_OPERATOR"]["WIDGET"].blockSignals(True)
                        self.widgets["FILTERING"]["OTHER_LAYERS_COMBINE_OPERATOR"]["WIDGET"].setCurrentIndex(0)
                        self.widgets["FILTERING"]["OTHER_LAYERS_COMBINE_OPERATOR"]["WIDGET"].blockSignals(False)
                    except Exception as widget_error:
                        logger.debug(f"Error setting combine operator combobox indexes: {widget_error}")
                    
                    logger.info(f"Multi-step filter auto-enabled for layer '{layer.name()}' - existing filters detected")
                    return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Error detecting multi-step filter: {e}")
            return False
    
    def _synchronize_layer_widgets(self, layer, layer_props):
        """
        Synchronize all widgets with the new current layer.
        
        Updates comboboxes, field expression widgets, and backend indicator.
        """
        # Detect multi-step filter: auto-enable additive filter if existing subsets detected
        self._detect_multi_step_filter(layer, layer_props)
        
        # Always synchronize comboBox_filtering_current_layer with current_layer
        lastLayer = self.widgets["FILTERING"]["CURRENT_LAYER"]["WIDGET"].currentLayer()
        if lastLayer is None or lastLayer.id() != self.current_layer.id():
            self.manageSignal(["FILTERING","CURRENT_LAYER"], 'disconnect')
            self.widgets["FILTERING"]["CURRENT_LAYER"]["WIDGET"].setLayer(self.current_layer)
            self.manageSignal(["FILTERING","CURRENT_LAYER"], 'connect', 'layerChanged')
        
        # Update backend indicator with PostgreSQL connection availability flag
        # CRITICAL: Pass forced backend if set to show the actual backend being used
        forced_backend = None
        if hasattr(self, 'forced_backends') and layer.id() in self.forced_backends:
            forced_backend = self.forced_backends[layer.id()]
        
        if layer.id() in self.PROJECT_LAYERS:
            infos = layer_props.get('infos', {})
            if 'layer_provider_type' in infos:
                provider_type = infos['layer_provider_type']
                postgresql_conn = infos.get('postgresql_connection_available', None)
                self._update_backend_indicator(provider_type, postgresql_conn, actual_backend=forced_backend)
        else:
            provider_type = layer.providerType()
            if provider_type == 'postgres':
                self._update_backend_indicator(PROVIDER_POSTGRES, actual_backend=forced_backend)
            elif provider_type == 'spatialite':
                self._update_backend_indicator(PROVIDER_SPATIALITE, actual_backend=forced_backend)
            elif provider_type == 'ogr':
                self._update_backend_indicator(PROVIDER_OGR, actual_backend=forced_backend)
            else:
                self._update_backend_indicator(provider_type, actual_backend=forced_backend)
        
        # Initialize buffer property widget with current layer
        self.filtering_init_buffer_property()
        
        # Update all layer property widgets
        for group_name in self.layer_properties_tuples_dict:
            tuple_group = self.layer_properties_tuples_dict[group_name]
            group_state = True
            if group_name not in ('is','selection_expression'):
                group_enabled_property = tuple_group[0]
                group_state = layer_props[group_enabled_property[0]][group_enabled_property[1]]
                if group_state is False:
                    self.properties_group_state_reset_to_default(tuple_group, group_name, group_state)
                else:
                    self.properties_group_state_enabler(tuple_group)
            
            if group_state is True:
                for i, property_tuple in enumerate(tuple_group):
                    # Skip tuples that don't have a corresponding widget (data-only properties)
                    if property_tuple[0].upper() not in self.widgets:
                        continue
                    if property_tuple[1].upper() not in self.widgets[property_tuple[0].upper()]:
                        continue
                    
                    widget_type = self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["TYPE"]
                    if widget_type == 'PushButton':
                        if all(key in self.widgets[property_tuple[0].upper()][property_tuple[1].upper()] for key in ["ICON_ON_TRUE", "ICON_ON_FALSE"]):
                            self.switch_widget_icon(property_tuple, layer_props[property_tuple[0]][property_tuple[1]])
                        if self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].isCheckable():
                            # CRITICAL: Block signals during setChecked to avoid triggering actions (select/zoom/etc)
                            # during state restoration - we only want to restore the visual state
                            widget = self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"]
                            widget.blockSignals(True)
                            widget.setChecked(layer_props[property_tuple[0]][property_tuple[1]])
                            widget.blockSignals(False)
                    elif widget_type == 'CheckableComboBox':
                        self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setCheckedItems(layer_props[property_tuple[0]][property_tuple[1]])
                    elif widget_type == 'CustomCheckableComboBox':
                        self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["CUSTOM_LOAD_FUNCTION"]
                    elif widget_type == 'ComboBox':
                        widget = self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"]
                        value = layer_props[property_tuple[0]][property_tuple[1]]
                        
                        # FIX v2.5.12: For combine_operator comboboxes, use index-based lookup
                        # to handle translated values (ET, OU, NON) from older projects
                        if property_tuple[1] in ('source_layer_combine_operator', 'other_layers_combine_operator'):
                            index = self._combine_operator_to_index(value)
                        else:
                            index = widget.findText(value)
                            if index == -1:
                                index = 0  # Default to first item
                        
                        widget.setCurrentIndex(index)
                    elif widget_type == 'QgsFieldExpressionWidget':
                        # CRITICAL: Block signals during setLayer/setExpression to prevent
                        # circular signal loop (fieldChanged -> layer_property_changed ->
                        # setLayerVariable) that causes access violation crash
                        widget = self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"]
                        widget.blockSignals(True)
                        widget.setLayer(self.current_layer)
                        widget.setFilters(QgsFieldProxyModel.AllTypes)
                        widget.setExpression(layer_props[property_tuple[0]][property_tuple[1]])
                        widget.blockSignals(False)
                    elif widget_type == 'QgsDoubleSpinBox':
                        self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setValue(layer_props[property_tuple[0]][property_tuple[1]])
                    elif widget_type == 'QgsSpinBox':
                        self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setValue(layer_props[property_tuple[0]][property_tuple[1]])
                    elif widget_type == 'LineEdit':
                        self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setText(layer_props[property_tuple[0]][property_tuple[1]])
                    elif widget_type == 'QgsProjectionSelectionWidget':
                        crs = QgsCoordinateReferenceSystem(layer_props[property_tuple[0]][property_tuple[1]])
                        if crs.isValid():
                            self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setCrs(crs)
                    elif widget_type == 'PropertyOverrideButton':
                        if layer_props[property_tuple[0]][property_tuple[1]] is False:
                            self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].setActive(False)
                        elif layer_props[property_tuple[0]][property_tuple[1]] is True:
                            self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].setActive(True)
        
        # Populate layers combobox with signals disconnected
        self.manageSignal(["FILTERING","LAYERS_TO_FILTER"], 'disconnect')
        self.filtering_populate_layers_chekableCombobox()
        self.manageSignal(["FILTERING","LAYERS_TO_FILTER"], 'connect', 'checkedItemsChanged')
    
    def _reload_exploration_widgets(self, layer, layer_props):
        """
        Force reload of ALL exploration widgets with new layer data.
        
        This ensures all widgets are properly populated even if already initialized.
        Auto-initializes empty expressions with the best available field.
        
        Args:
            layer: The validated layer to use for widget updates
            layer_props: Layer properties dictionary
        """
        if not self.widgets_initialized:
            return
        
        try:
            # Disconnect ALL exploration signals before updating widgets
            self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')
            self.manageSignal(["EXPLORING","SINGLE_SELECTION_EXPRESSION"], 'disconnect')
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_EXPRESSION"], 'disconnect')
            self.manageSignal(["EXPLORING","CUSTOM_SELECTION_EXPRESSION"], 'disconnect')
            
            # Auto-initialize empty expressions with best available field
            expressions_updated = False
            single_expr = layer_props["exploring"]["single_selection_expression"]
            multiple_expr = layer_props["exploring"]["multiple_selection_expression"]
            custom_expr = layer_props["exploring"]["custom_selection_expression"]
            
            if not single_expr or not multiple_expr or not custom_expr:
                best_field = get_best_display_field(layer)
                if best_field:
                    if not single_expr:
                        layer_props["exploring"]["single_selection_expression"] = best_field
                        self.PROJECT_LAYERS[layer.id()]["exploring"]["single_selection_expression"] = best_field
                        expressions_updated = True
                    if not multiple_expr:
                        layer_props["exploring"]["multiple_selection_expression"] = best_field
                        self.PROJECT_LAYERS[layer.id()]["exploring"]["multiple_selection_expression"] = best_field
                        expressions_updated = True
                    if not custom_expr:
                        layer_props["exploring"]["custom_selection_expression"] = best_field
                        self.PROJECT_LAYERS[layer.id()]["exploring"]["custom_selection_expression"] = best_field
                        expressions_updated = True
                    
                    # Save updated expressions to SQLite if any were auto-initialized
                    if expressions_updated:
                        logger.debug(f"Auto-initialized exploring expressions with field '{best_field}' for layer {layer.name()}")
                        # CRASH FIX (v2.3.16): Re-validate layer before emitting signal
                        # Layer may have become invalid during the exploration widget reload
                        if is_valid_layer(layer):
                            # Emit signal to save the updated expressions
                            properties_to_save = []
                            if not single_expr:
                                properties_to_save.append(("exploring", "single_selection_expression"))
                            if not multiple_expr:
                                properties_to_save.append(("exploring", "multiple_selection_expression"))
                            if not custom_expr:
                                properties_to_save.append(("exploring", "custom_selection_expression"))
                            self.settingLayerVariable.emit(layer, properties_to_save)
                        else:
                            logger.debug(f"_reload_exploration_widgets: layer became invalid, skipping signal emit")
            
            # Update expressions after potential auto-initialization
            single_expr = layer_props["exploring"]["single_selection_expression"]
            multiple_expr = layer_props["exploring"]["multiple_selection_expression"]
            custom_expr = layer_props["exploring"]["custom_selection_expression"]
            
            # Single selection widget - use validated layer parameter
            if "SINGLE_SELECTION_FEATURES" in self.widgets.get("EXPLORING", {}):
                self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setLayer(layer)
                self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setDisplayExpression(single_expr)
                self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setFetchGeometry(True)
                self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setShowBrowserButtons(True)
                # SPATIALITE FIX: Allow null to prevent widget from blocking on first load
                self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setAllowNull(True)
            
            # Multiple selection widget - use validated layer parameter
            if "MULTIPLE_SELECTION_FEATURES" in self.widgets.get("EXPLORING", {}):
                self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setLayer(layer, layer_props)
            
            # Field expression widgets - setLayer BEFORE setExpression - use validated layer parameter
            if "SINGLE_SELECTION_EXPRESSION" in self.widgets.get("EXPLORING", {}):
                self.widgets["EXPLORING"]["SINGLE_SELECTION_EXPRESSION"]["WIDGET"].setLayer(layer)
                self.widgets["EXPLORING"]["SINGLE_SELECTION_EXPRESSION"]["WIDGET"].setExpression(single_expr)
            
            if "MULTIPLE_SELECTION_EXPRESSION" in self.widgets.get("EXPLORING", {}):
                self.widgets["EXPLORING"]["MULTIPLE_SELECTION_EXPRESSION"]["WIDGET"].setLayer(layer)
                self.widgets["EXPLORING"]["MULTIPLE_SELECTION_EXPRESSION"]["WIDGET"].setExpression(multiple_expr)
            
            if "CUSTOM_SELECTION_EXPRESSION" in self.widgets.get("EXPLORING", {}):
                self.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"].setLayer(layer)
                self.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"].setExpression(custom_expr)
            
            # Reconnect signals AFTER all widgets are updated
            self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'connect', 'featureChanged')
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'updatingCheckedItemList')
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'filteringCheckedItemList')
            self.manageSignal(["EXPLORING","SINGLE_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
            self.manageSignal(["EXPLORING","CUSTOM_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
            
            # DEBUG: Log widget state after reload
            picker_widget = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
            logger.debug(f"_reload_exploration_widgets complete:")
            logger.debug(f"  layer: {layer.name() if layer else 'None'}")
            logger.debug(f"  single_expr: {single_expr}")
            logger.debug(f"  picker layer: {picker_widget.layer().name() if picker_widget.layer() else 'None'}")
            logger.debug(f"  picker displayExpression: {picker_widget.displayExpression()}")
            logger.debug(f"  picker allowNull: {picker_widget.allowNull()}")
            logger.debug(f"  picker feature valid: {picker_widget.feature().isValid() if picker_widget.feature() else False}")
        except (AttributeError, KeyError, RuntimeError) as e:
            # Widget may not be ready yet or already destroyed
            logger.warning(f"Error in _reload_exploration_widgets: {type(e).__name__}: {e}")
            logger.debug(f"Layer: {layer.name() if layer else 'None'}, widgets_initialized: {self.widgets_initialized}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")


    def _restore_groupbox_ui_state(self, groupbox_name):
        """
        Restore only the visual UI state of exploring groupboxes without widget updates.
        
        This method sets the collapsed/expanded state of groupboxes based on the saved
        groupbox name. Unlike exploring_groupbox_changed(), it does NOT:
        - Disconnect/reconnect signals
        - Call setLayer() on widgets
        - Trigger exploring_link_widgets() or exploring_features_changed()
        
        Use this when widgets have already been updated (e.g., after _reload_exploration_widgets())
        and only the visual groupbox state needs restoration.
        
        Args:
            groupbox_name (str): The groupbox to expand ('single_selection', 'multiple_selection', 
                               or 'custom_selection')
        """
        if not self.widgets_initialized:
            return
        
        # Store current groupbox name
        self.current_exploring_groupbox = groupbox_name
        
        # Save to PROJECT_LAYERS for persistence
        if self.current_layer is not None and self.current_layer.id() in self.PROJECT_LAYERS:
            self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["current_exploring_groupbox"] = groupbox_name
        
        # Get groupbox widgets
        single_gb = self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"]
        multiple_gb = self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"]
        custom_gb = self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"]
        
        # Block signals to prevent recursive calls during state restoration
        single_gb.blockSignals(True)
        multiple_gb.blockSignals(True)
        custom_gb.blockSignals(True)
        
        try:
            # Set visual state based on groupbox type
            if groupbox_name == "single_selection":
                single_gb.setChecked(True)
                single_gb.setCollapsed(False)
                multiple_gb.setChecked(False)
                multiple_gb.setCollapsed(True)
                custom_gb.setChecked(False)
                custom_gb.setCollapsed(True)
                # Enable widgets for this mode
                if self.current_layer is not None:
                    self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setEnabled(True)
                    self.widgets["EXPLORING"]["SINGLE_SELECTION_EXPRESSION"]["WIDGET"].setEnabled(True)
                    
            elif groupbox_name == "multiple_selection":
                single_gb.setChecked(False)
                single_gb.setCollapsed(True)
                multiple_gb.setChecked(True)
                multiple_gb.setCollapsed(False)
                custom_gb.setChecked(False)
                custom_gb.setCollapsed(True)
                # Enable widgets for this mode
                if self.current_layer is not None:
                    self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setEnabled(True)
                    self.widgets["EXPLORING"]["MULTIPLE_SELECTION_EXPRESSION"]["WIDGET"].setEnabled(True)
                    
            elif groupbox_name == "custom_selection":
                single_gb.setChecked(False)
                single_gb.setCollapsed(True)
                multiple_gb.setChecked(False)
                multiple_gb.setCollapsed(True)
                custom_gb.setChecked(True)
                custom_gb.setCollapsed(False)
                # Enable widgets for this mode
                if self.current_layer is not None:
                    self.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"].setEnabled(True)
        finally:
            # Always restore signals
            single_gb.blockSignals(False)
            multiple_gb.blockSignals(False)
            custom_gb.blockSignals(False)
    
    def _reconnect_layer_signals(self, widgets_to_reconnect, layer_props):
        """
        Reconnect all layer-related widget signals after updates.
        
        Also restores exploring groupbox UI state and connects layer selection signal.
        
        NOTE: This method now uses _restore_groupbox_ui_state() instead of 
        exploring_groupbox_changed() to avoid double processing of widgets.
        The widget layer updates are already done in _reload_exploration_widgets().
        
        PRESERVE FILTER: When changing layers, the existing filter on the new layer
        is preserved. We only trigger exploring_features_changed if there are selected
        features or if the layer has no existing filter.
        
        SIGNAL HANDLING: Exploring widget signals are NOT reconnected here because
        they are already correctly reconnected in _reload_exploration_widgets() with
        the appropriate signal types for the active groupbox.
        """
        # Filter out exploring widget signals - they are already reconnected in _reload_exploration_widgets()
        exploring_signal_prefixes = [
            ["EXPLORING", "SINGLE_SELECTION_FEATURES"],
            ["EXPLORING", "SINGLE_SELECTION_EXPRESSION"],
            ["EXPLORING", "MULTIPLE_SELECTION_FEATURES"],
            ["EXPLORING", "MULTIPLE_SELECTION_EXPRESSION"],
            ["EXPLORING", "CUSTOM_SELECTION_EXPRESSION"]
        ]
        
        # Reconnect only non-exploring signals
        for widget_path in widgets_to_reconnect:
            # Skip exploring widget signals - already handled in _reload_exploration_widgets()
            if widget_path not in exploring_signal_prefixes:
                self.manageSignal(widget_path, 'connect')
        
        # Reconnect legend link if enabled - ALWAYS reconnect the signal first
        if self.project_props["OPTIONS"]["LAYERS"]["LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"] is True:
            # First reconnect the signal to ensure bidirectional sync continues working
            widget_path = ["QGIS","LAYER_TREE_VIEW"]
            self.manageSignal(widget_path, 'connect')
            
            # Then sync the Layer Tree View with current_layer (ComboBox → Layer Tree View sync)
            if self.current_layer is not None:
                active_layer = self.iface.activeLayer()
                if active_layer is None or active_layer.id() != self.current_layer.id():
                    # Block the signal temporarily to avoid recursive call
                    self.manageSignal(widget_path, 'disconnect')
                    self.widgets["QGIS"]["LAYER_TREE_VIEW"]["WIDGET"].setCurrentLayer(self.current_layer)
                    self.manageSignal(widget_path, 'connect')
        
        # Connect selectionChanged signal for current layer to enable tracking
        if self.current_layer is not None:
            try:
                self.current_layer.selectionChanged.connect(self.on_layer_selection_changed)
                self.current_layer_selection_connection = True
            except (TypeError, RuntimeError) as e:
                logger.warning(f"Could not connect selectionChanged signal: {type(e).__name__}: {e}")
                self.current_layer_selection_connection = None
        
        # Restore exploring groupbox UI state only (no widget updates - already done in _reload_exploration_widgets)
        # This replaces the previous call to exploring_groupbox_changed() which caused double processing
        if "current_exploring_groupbox" in layer_props.get("exploring", {}):
            saved_groupbox = layer_props["exploring"]["current_exploring_groupbox"]
            if saved_groupbox:
                self._restore_groupbox_ui_state(saved_groupbox)
        elif self.current_exploring_groupbox:
            self._restore_groupbox_ui_state(self.current_exploring_groupbox)
        else:
            self._restore_groupbox_ui_state("single_selection")
        
        # Link widgets and restore feature selection state
        if self.current_layer is not None:
            self.exploring_link_widgets()
            
            # Trigger feature update based on current groupbox mode
            # NOTE: This only updates feature selection/tracking, NOT layer filters
            # IMPORTANT: Only trigger if there are selected features to avoid clearing existing filters
            if self.current_exploring_groupbox == "single_selection":
                if "SINGLE_SELECTION_FEATURES" in self.widgets.get("EXPLORING", {}):
                    selected_feature = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].feature()
                    # Only trigger if feature is valid to avoid clearing layer filter
                    if selected_feature is not None and selected_feature.isValid():
                        self.exploring_features_changed(selected_feature)
                        
            elif self.current_exploring_groupbox == "multiple_selection":
                if "MULTIPLE_SELECTION_FEATURES" in self.widgets.get("EXPLORING", {}):
                    selected_features = self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].currentSelectedFeatures()
                    # Only trigger if there are selected features
                    if selected_features:
                        self.exploring_features_changed(selected_features, True)
                        
            elif self.current_exploring_groupbox == "custom_selection":
                custom_expression = layer_props["exploring"].get("custom_selection_expression", "")
                # Only trigger if there's an expression to avoid clearing layer filter
                if custom_expression:
                    self.exploring_custom_selection()


    def current_layer_changed(self, layer):
        """
        Handle current layer change event.
        
        Orchestrates layer change by validating, disconnecting signals, 
        synchronizing widgets, and reconnecting signals.
        
        STABILITY FIX: Added checks for plugin busy state and deferred processing
        to prevent crashes during project load operations.
        """
        # CRITICAL: Check lock BEFORE any processing
        if self._updating_current_layer:
            return
        
        # CACHE INVALIDATION: When changing layers, we don't need to invalidate 
        # the cache for the old layer (it stays valid for when we switch back).
        # The cache key includes layer_id, so each layer has its own cache entries.
        # This is intentional: cached features remain valid until selection changes.
        
        # STABILITY FIX: If plugin is busy (loading project, etc.), defer the layer change
        if self._plugin_busy:
            from qgis.PyQt.QtCore import QTimer
            from qgis.core import QgsProject
            logger.debug(f"Plugin is busy, deferring layer change for: {layer.name() if layer else 'None'}")
            # STABILITY FIX: Use weakref to prevent access violations
            weak_self = weakref.ref(self)
            # CRASH FIX (v2.3.16): Store layer ID, not layer object reference
            # The layer object may become invalid (C++ deleted) by the time timer fires.
            # Re-fetch from QgsProject to get a fresh, valid reference.
            try:
                captured_layer_id = layer.id() if layer else None
            except (RuntimeError, OSError, SystemError):
                captured_layer_id = None
            
            def safe_layer_change():
                strong_self = weak_self()
                if strong_self is not None:
                    # CRASH FIX (v2.3.16): Re-fetch layer from project using ID
                    if captured_layer_id:
                        fresh_layer = QgsProject.instance().mapLayer(captured_layer_id)
                        if fresh_layer is not None:
                            strong_self.current_layer_changed(fresh_layer)
                        else:
                            logger.debug(f"safe_layer_change: layer {captured_layer_id} no longer exists, skipping")
                    else:
                        strong_self.current_layer_changed(None)
            QTimer.singleShot(150, safe_layer_change)
            return
        
        # STABILITY FIX: Verify layer is valid before accessing properties
        if layer is not None:
            try:
                # Test if the layer C++ object is still valid
                layer_name = layer.name()
                layer_id = layer.id()
            except (RuntimeError, AttributeError):
                logger.warning("current_layer_changed received invalid layer object, ignoring")
                return
        
        # DEBUG: Log layer information
        logger.debug(f"current_layer_changed called with layer: {layer.name() if layer else 'None'} (id: {layer.id() if layer else 'None'})")
        
        # Set lock immediately
        self._updating_current_layer = True
            
        try:
            # Validate layer and prepare for change
            should_continue, validated_layer, layer_props = self._validate_and_prepare_layer(layer)
            if not should_continue:
                return
            
            # Reset expressions for new layer
            self._reset_layer_expressions(layer_props)
            
            # Disconnect all signals before updates
            widgets_to_reconnect = self._disconnect_layer_signals()
            
            # Synchronize all widgets with new layer
            self._synchronize_layer_widgets(validated_layer, layer_props)
            
            # Reload exploration widgets with validated layer
            self._reload_exploration_widgets(validated_layer, layer_props)
            
            # Reconnect all signals and restore state
            self._reconnect_layer_signals(widgets_to_reconnect, layer_props)
            
        except Exception as e:
            logger.error(f"Error in current_layer_changed: {type(e).__name__}: {e}")
        finally:
            # CRITICAL: Always release the lock
            self._updating_current_layer = False


    def project_property_changed(self, input_property, input_data=None, custom_functions={}):

        if self.widgets_initialized is True and self.has_loaded_layers is True:

            properties_group_key = None
            property_path = None
            index = None
            state = None
            group_state = True
            flag_value_changed = False

            if isinstance(input_data, dict) or isinstance(input_data, list) or isinstance(input_data, str):
                if len(input_data) >= 0:
                    state = True
                else:
                    state = False
            elif isinstance(input_data, int) or isinstance(input_data, float):
                if int(input_data) >= 0:
                    state = True
                else:
                    state = False
                if isinstance(input_data, float):
                    input_data = truncate(input_data, 2)
            elif isinstance(input_data, bool):
                state = input_data
            

            for properties_tuples_key in self.export_properties_tuples_dict:
                if input_property.find(properties_tuples_key) >= 0:
                    properties_group_key = properties_tuples_key
                    properties_tuples = self.export_properties_tuples_dict[properties_tuples_key]
                    for i, property_tuple in enumerate(properties_tuples):
                        if property_tuple[1] == input_property:
                            property_path = property_tuple
                            index = i
                            break
                    break
            
            group_enabled_property = properties_tuples[0]
            group_state = self.widgets[group_enabled_property[0].upper()][group_enabled_property[1].upper()]["WIDGET"].isChecked()

            if group_state is False:
                self.properties_group_state_reset_to_default(properties_tuples, properties_group_key, group_state)            

            else:
                self.properties_group_state_enabler(properties_tuples)
                widget_type = self.widgets[property_path[0].upper()][property_path[1].upper()]["TYPE"]
                if widget_type == 'PushButton':
                    if self.project_props[property_path[0].upper()][property_path[1].upper()] is not input_data and input_data is True:
                        self.project_props[property_path[0].upper()][property_path[1].upper()] = input_data
                        flag_value_changed = True
                        if "ON_TRUE" in custom_functions:
                            custom_functions["ON_TRUE"](0)

                    elif self.project_props[property_path[0].upper()][property_path[1].upper()] is not input_data and input_data is False:
                        self.project_props[property_path[0].upper()][property_path[1].upper()] = input_data
                        flag_value_changed = True
                        if "ON_FALSE" in custom_functions:
                            custom_functions["ON_FALSE"](0)
                else:    
                    # For non-PushButton widgets (CheckBox, ComboBox, etc.)
                    # Update the value if the parent group is enabled
                    if self.project_props[properties_tuples[0][0].upper()][properties_tuples[0][1].upper()] is True:
                        # Get the value from custom function or use input_data directly
                        new_value = custom_functions["CUSTOM_DATA"](0) if "CUSTOM_DATA" in custom_functions else input_data
                        
                        # Only mark as changed if value actually changed
                        if self.project_props[property_path[0].upper()][property_path[1].upper()] != new_value:
                            self.project_props[property_path[0].upper()][property_path[1].upper()] = new_value
                            flag_value_changed = True
                            
                            if new_value and "ON_TRUE" in custom_functions:
                                custom_functions["ON_TRUE"](0)
                            elif not new_value and "ON_FALSE" in custom_functions:
                                custom_functions["ON_FALSE"](0)

            if flag_value_changed is True:
                if "ON_CHANGE" in custom_functions:
                    custom_functions["ON_CHANGE"](0)
                self.CONFIG_DATA['CURRENT_PROJECT']['EXPORTING'] = self.project_props['EXPORTING']
                self.setProjectVariablesEvent()


    def _parse_property_data(self, input_data):
        """
        Parse and validate input data for property updates.
        
        Args:
            input_data: Property value (dict, list, str, int, float, bool, or None)
            
        Returns:
            tuple: (parsed_data, state) where state indicates if data is valid/enabled
        """
        state = None
        
        if isinstance(input_data, dict) or isinstance(input_data, list) or isinstance(input_data, str):
            state = len(input_data) >= 0
        elif isinstance(input_data, int) or isinstance(input_data, float):
            state = int(input_data) >= 0
            if isinstance(input_data, float):
                input_data = truncate(input_data, 2)
        elif isinstance(input_data, bool):
            state = input_data
        elif input_data is None:
            state = False
            
        return input_data, state

    def _find_property_path(self, input_property):
        """
        Find property path and group key from input property name.
        
        Args:
            input_property: Property identifier string
            
        Returns:
            tuple: (properties_group_key, property_path, properties_tuples, index)
        """
        for properties_tuples_key in self.layer_properties_tuples_dict:
            if input_property.find(properties_tuples_key) >= 0:
                properties_group_key = properties_tuples_key
                properties_tuples = self.layer_properties_tuples_dict[properties_tuples_key]
                for i, property_tuple in enumerate(properties_tuples):
                    if property_tuple[1] == input_property:
                        return properties_group_key, property_tuple, properties_tuples, i
        return None, None, None, None

    def _update_is_property(self, property_path, layer_props, input_data, custom_functions):
        """
        Update 'is' type properties (boolean toggles).
        
        Args:
            property_path: Property path tuple
            layer_props: Layer properties dict
            input_data: New value
            custom_functions: Callbacks dict
            
        Returns:
            bool: True if value changed
        """
        flag_value_changed = False
        
        if property_path[1] == "is_changing_all_layer_properties":
            if layer_props[property_path[0]][property_path[1]] is True:
                self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = False
                flag_value_changed = True
                if "ON_TRUE" in custom_functions:
                    custom_functions["ON_TRUE"](0)
                self.switch_widget_icon(property_path, False)
            elif layer_props[property_path[0]][property_path[1]] is False:
                self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = True
                flag_value_changed = True
                if "ON_FALSE" in custom_functions:
                    custom_functions["ON_FALSE"](0)
                self.switch_widget_icon(property_path, True)
        else:
            if layer_props[property_path[0]][property_path[1]] is not input_data and input_data is True:
                self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = input_data
                flag_value_changed = True
                if "ON_TRUE" in custom_functions:
                    custom_functions["ON_TRUE"](0)
            elif layer_props[property_path[0]][property_path[1]] is not input_data and input_data is False:
                self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = input_data
                flag_value_changed = True
                if "ON_FALSE" in custom_functions:
                    custom_functions["ON_FALSE"](0)
                    
        return flag_value_changed

    def _update_selection_expression_property(self, property_path, layer_props, input_data, custom_functions):
        """
        Update selection expression properties.
        
        Args:
            property_path: Property path tuple
            layer_props: Layer properties dict
            input_data: New expression value
            custom_functions: Callbacks dict
            
        Returns:
            bool: True if value changed (or always True for expressions to trigger display update)
        """
        value_changed = False
        if str(layer_props[property_path[0]][property_path[1]]) != input_data:
            self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = input_data
            if "ON_TRUE" in custom_functions:
                custom_functions["ON_TRUE"](0)
            value_changed = True
        
        # CRITICAL FIX: Always return True for selection expressions
        # This ensures ON_CHANGE is called to update the FeaturePicker display expression
        # even when re-selecting the same field (e.g., after layer switch)
        return True

    def _update_other_property(self, property_path, properties_tuples, properties_group_key, layer_props, input_data, custom_functions):
        """
        Update other property types (filtering, exporting, etc.).
        
        Args:
            property_path: Property path tuple
            properties_tuples: Property tuples list
            properties_group_key: Group key
            layer_props: Layer properties dict
            input_data: New value
            custom_functions: Callbacks dict
            
        Returns:
            bool: True if value changed
        """
        flag_value_changed = False
        group_enabled_property = properties_tuples[0]
        group_state = self.widgets[group_enabled_property[0].upper()][group_enabled_property[1].upper()]["WIDGET"].isChecked()
        
        # DIAGNOSTIC: Log the property update
        logger.info(f"=== _update_other_property DIAGNOSTIC ===")
        logger.info(f"  property_path: {property_path}")
        logger.info(f"  group_enabled_property: {group_enabled_property}")
        logger.info(f"  group_state (button checked): {group_state}")

        if group_state is False:
            logger.warning(f"  ⚠️ Group button NOT checked - resetting to defaults!")
            self.properties_group_state_reset_to_default(properties_tuples, properties_group_key, group_state)
            flag_value_changed = True
        else:
            self.properties_group_state_enabler(properties_tuples)
            widget_type = self.widgets[property_path[0].upper()][property_path[1].upper()]["TYPE"]
            
            # CRITICAL FIX: Use .get() to avoid KeyError on missing properties
            current_value = layer_props.get(property_path[0], {}).get(property_path[1])
            
            if widget_type == 'PushButton':
                if current_value is not input_data and input_data is True:
                    # Ensure the property path exists
                    if property_path[0] not in self.PROJECT_LAYERS[self.current_layer.id()]:
                        self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]] = {}
                    self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = input_data
                    flag_value_changed = True
                    if "ON_TRUE" in custom_functions:
                        custom_functions["ON_TRUE"](0)
                    
                    # Refresh layers list when has_layers_to_filter is activated
                    if property_path[1] == 'has_layers_to_filter':
                        self.manageSignal(["FILTERING","LAYERS_TO_FILTER"], 'disconnect')
                        self.filtering_populate_layers_chekableCombobox()
                        self.manageSignal(["FILTERING","LAYERS_TO_FILTER"], 'connect', 'checkedItemsChanged')
                        
                elif current_value is not input_data and input_data is False:
                    # Ensure the property path exists
                    if property_path[0] not in self.PROJECT_LAYERS[self.current_layer.id()]:
                        self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]] = {}
                    self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = input_data
                    flag_value_changed = True
                    if "ON_FALSE" in custom_functions:
                        custom_functions["ON_FALSE"](0)
            else:
                # For non-PushButton widgets (CheckableComboBox, etc.)
                # Get the value from custom function or use input_data directly
                new_value = custom_functions["CUSTOM_DATA"](0) if "CUSTOM_DATA" in custom_functions else input_data
                
                logger.info(f"  Widget type: non-PushButton, getting new_value from CUSTOM_DATA")
                logger.info(f"  new_value: {new_value}")
                logger.info(f"  old_value: {current_value}")
                
                # Only mark as changed if value actually changed
                if current_value != new_value:
                    # Ensure the property path exists
                    if property_path[0] not in self.PROJECT_LAYERS[self.current_layer.id()]:
                        self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]] = {}
                    self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = new_value
                    flag_value_changed = True
                    logger.info(f"  ✓ Value CHANGED and saved to PROJECT_LAYERS")
                    
                    if new_value and "ON_TRUE" in custom_functions:
                        custom_functions["ON_TRUE"](0)
                    elif not new_value and "ON_FALSE" in custom_functions:
                        custom_functions["ON_FALSE"](0)
                    
                    # Log when layers_to_filter is updated
                    if property_path[1] == 'layers_to_filter':
                        logger.info(f"  ✓ layers_to_filter updated in PROJECT_LAYERS: {new_value}")
                else:
                    logger.info(f"  ℹ️ Value unchanged, not updating PROJECT_LAYERS")
                    
        return flag_value_changed

    def layer_property_changed(self, input_property, input_data=None, custom_functions={}):
        """
        Handle property changes for the current layer.
        Orchestrates property updates by type (is/selection_expression/other).
        """
        if self.widgets_initialized is True and self.current_layer is not None:
            # STABILITY FIX: Guard against KeyError if layer not in PROJECT_LAYERS
            if self.current_layer.id() not in self.PROJECT_LAYERS:
                logger.warning(f"layer_property_changed: layer {self.current_layer.name()} not in PROJECT_LAYERS")
                return
            
            # Disconnect exploring widgets
            widgets_to_stop = [
                ["EXPLORING","SINGLE_SELECTION_FEATURES"],
                ["EXPLORING","SINGLE_SELECTION_EXPRESSION"],
                ["EXPLORING","MULTIPLE_SELECTION_FEATURES"],
                ["EXPLORING","MULTIPLE_SELECTION_EXPRESSION"],
                ["EXPLORING","CUSTOM_SELECTION_EXPRESSION"]
            ]
            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'disconnect')

            # Parse and find property
            input_data, state = self._parse_property_data(input_data)
            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
            properties_group_key, property_path, properties_tuples, index = self._find_property_path(input_property)

            # Update by property type
            flag_value_changed = False
            if properties_group_key == 'is':
                flag_value_changed = self._update_is_property(property_path, layer_props, input_data, custom_functions)
            elif properties_group_key == 'selection_expression':
                flag_value_changed = self._update_selection_expression_property(property_path, layer_props, input_data, custom_functions)
            else:
                flag_value_changed = self._update_other_property(property_path, properties_tuples, properties_group_key, layer_props, input_data, custom_functions)

            # Trigger change callbacks
            if flag_value_changed is True:
                if "ON_CHANGE" in custom_functions:
                    custom_functions["ON_CHANGE"](0)
                self.setLayerVariableEvent(self.current_layer, [property_path])

            # CRITICAL FIX: Reconnect widgets using direct connection for featureChanged signal
            # The manageSignal approach using isSignalConnected is unreliable
            picker_widget = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
            try:
                picker_widget.featureChanged.disconnect(self.exploring_features_changed)
            except TypeError:
                pass
            picker_widget.featureChanged.connect(self.exploring_features_changed)
            
            # Reconnect other widgets via manageSignal
            self.manageSignal(["EXPLORING","SINGLE_SELECTION_EXPRESSION"], 'connect')
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect')
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_EXPRESSION"], 'connect')
            self.manageSignal(["EXPLORING","CUSTOM_SELECTION_EXPRESSION"], 'connect')

    def layer_property_changed_with_buffer_style(self, input_property, input_data=None):
        """
        Handle buffer value changes with visual style feedback.
        
        Applies visual styling to indicate negative buffer (erosion) vs positive buffer (expansion):
        - Negative buffer: Orange/yellow background to indicate erosion mode
        - Zero/positive buffer: Default style
        
        Args:
            input_property: The property name being changed
            input_data: The new value
        """
        # First, call the normal property change handler
        self.layer_property_changed(input_property, input_data)
        
        # Then update the visual style based on the buffer value
        self._update_buffer_spinbox_style(input_data)
    
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
        
        Negative buffers (erosion) only work on polygon/multipolygon geometries.
        For point and line geometries, the minimum value is set to 0 to prevent
        negative buffer input.
        
        This method checks the current source layer (from exploring widgets) and
        adjusts the spinbox minimum value accordingly.
        """
        from qgis.core import QgsWkbTypes
        
        spinbox = self.mQgsDoubleSpinBox_filtering_buffer_value
        
        # Get source layer from exploring widgets
        source_layer = None
        features = []
        
        try:
            if self.current_layer is not None and self.widgets_initialized:
                features, _ = self.get_current_features()
                
                # Source layer is the current layer in exploring mode
                source_layer = self.current_layer
        except Exception as e:
            logger.debug(f"_update_buffer_validation: Could not get source layer: {e}")
        
        # Default: allow negative buffers (for polygons)
        min_value = -1000000.0
        tooltip = self.tr("Buffer value in meters (positive=expand, negative=shrink polygons)")
        
        if source_layer is not None:
            try:
                geom_type = source_layer.geometryType()
                
                # Check if geometry is polygon/multipolygon
                is_polygon = geom_type == QgsWkbTypes.PolygonGeometry
                
                if not is_polygon:
                    # Point or Line geometry: disable negative buffers
                    min_value = 0.0
                    
                    # Get geometry type name for tooltip
                    if geom_type == QgsWkbTypes.PointGeometry:
                        geom_name = self.tr("point")
                    elif geom_type == QgsWkbTypes.LineGeometry:
                        geom_name = self.tr("line")
                    else:
                        geom_name = self.tr("non-polygon")
                    
                    tooltip = self.tr(
                        f"Buffer value in meters (positive only for {geom_name} layers. "
                        f"Negative buffers only work on polygon layers)"
                    )
                    
                    # If current value is negative, reset to 0
                    current_value = spinbox.value()
                    if current_value < 0:
                        logger.info(f"Resetting negative buffer to 0 for {geom_name} layer: {source_layer.name()}")
                        spinbox.setValue(0.0)
                        
                        # Update PROJECT_LAYERS if layer exists
                        if hasattr(self, 'current_layer') and self.current_layer and self.current_layer.id() in self.PROJECT_LAYERS:
                            self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer_value"] = 0.0
                    
                    logger.debug(f"Buffer validation: {geom_name} geometry detected, minimum set to 0")
                else:
                    logger.debug(f"Buffer validation: Polygon geometry detected, negative buffers allowed")
                    
            except Exception as e:
                logger.warning(f"_update_buffer_validation: Error checking geometry type: {e}")
        
        # Apply validation
        spinbox.setMinimum(min_value)
        
        # Update tooltip (unless it's already in orange/negative mode)
        current_value = spinbox.value()
        if current_value is None or current_value >= 0:
            spinbox.setToolTip(tooltip)

    def set_exporting_properties(self):

        if self.widgets_initialized is True and self.has_loaded_layers is True:

            widgets_to_stop =   [
                                    ["EXPORTING","HAS_LAYERS_TO_EXPORT"],
                                    ["EXPORTING","HAS_PROJECTION_TO_EXPORT"],
                                    ["EXPORTING","HAS_STYLES_TO_EXPORT"],
                                    ["EXPORTING","HAS_DATATYPE_TO_EXPORT"],
                                    ["EXPORTING","LAYERS_TO_EXPORT"],
                                    ["EXPORTING","PROJECTION_TO_EXPORT"],
                                    ["EXPORTING","STYLES_TO_EXPORT"],
                                    ["EXPORTING","DATATYPE_TO_EXPORT"]
                                ]
            
            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'disconnect')

            group_state = True

            for properties_group_key in self.export_properties_tuples_dict:
                properties_tuples = self.export_properties_tuples_dict[properties_group_key]
                
                group_enabled_property = properties_tuples[0]
                group_state = self.widgets[group_enabled_property[0].upper()][group_enabled_property[1].upper()]["WIDGET"].isChecked()

                if group_state is False:
                    self.properties_group_state_reset_to_default(properties_tuples, properties_group_key, group_state)

                else:
                    self.properties_group_state_enabler(properties_tuples)
                    for i, property_path in enumerate(properties_tuples):
                        # Skip tuples that don't have a corresponding widget (data-only properties)
                        if property_path[0].upper() not in self.widgets:
                            continue
                        if property_path[1].upper() not in self.widgets[property_path[0].upper()]:
                            continue
                        
                        widget_type = self.widgets[property_path[0].upper()][property_path[1].upper()]["TYPE"]
                        if widget_type == 'PushButton':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setChecked(self.project_props[property_path[0].upper()][property_path[1].upper()])
                        elif widget_type == 'CheckBox':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setChecked(self.project_props[property_path[0].upper()][property_path[1].upper()])
                        elif widget_type == 'CheckableComboBox':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setCheckedItems(self.project_props[property_path[0].upper()][property_path[1].upper()])
                        elif widget_type == 'CustomCheckableComboBox':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["CUSTOM_LOAD_FUNCTION"]
                        elif widget_type == 'ComboBox':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setCurrentIndex(self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].findText(self.project_props[property_path[0].upper()][property_path[1].upper()]))
                        elif widget_type == 'QgsDoubleSpinBox':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setValue(self.project_props[property_path[0].upper()][property_path[1].upper()])
                        elif widget_type == 'LineEdit':
                            if self.project_props[property_path[0].upper()][property_path[1].upper()] == '':
                                if property_path[1] == 'output_folder_to_export':
                                    self.reset_export_output_path()
                                if property_path[1] == 'zip_to_export':
                                    self.reset_export_output_pathzip()
                            else:
                                self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setText(self.project_props[property_path[0].upper()][property_path[1].upper()])
                        elif widget_type == 'QgsProjectionSelectionWidget':
                            crs = QgsCoordinateReferenceSystem(self.project_props[property_path[0].upper()][property_path[1].upper()])
                            if crs.isValid():
                                self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setCrs(crs)

            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'connect')

            self.CONFIG_DATA["CURRENT_PROJECT"]['EXPORTING'] = self.project_props['EXPORTING']
            # self.reload_configuration_model()


    def properties_group_state_enabler(self, tuple_group):

        if self.widgets_initialized is True and self.has_loaded_layers is True:
            for tuple in tuple_group:
                # Skip tuples that don't have a corresponding widget (data-only properties)
                if tuple[0].upper() not in self.widgets:
                    continue
                if tuple[1].upper() not in self.widgets[tuple[0].upper()]:
                    continue
                    
                widget_type = self.widgets[tuple[0].upper()][tuple[1].upper()]["TYPE"]
                
                # Special handling for output_folder and zip buttons - only enable if layers are selected
                if tuple[1] in ['has_output_folder_to_export', 'has_zip_to_export']:
                    # Check if any layers are selected
                    has_layers_selected = False
                    if hasattr(self, 'checkableComboBoxLayer_exporting_layers'):
                        for i in range(self.checkableComboBoxLayer_exporting_layers.count()):
                            if self.checkableComboBoxLayer_exporting_layers.itemCheckState(i) == Qt.Checked:
                                has_layers_selected = True
                                break
                    self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].setEnabled(has_layers_selected)
                else:
                    self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].setEnabled(True)
                
                # Ensure QgsFieldExpressionWidget is always linked to current layer when enabled
                if widget_type == 'QgsFieldExpressionWidget' and self.current_layer is not None:
                    self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].setLayer(self.current_layer)


    def properties_group_state_reset_to_default(self, tuple_group, group_name, state):

        if self.widgets_initialized is True and self.has_loaded_layers is True:
            for i, property_path in enumerate(tuple_group):
                # Skip tuples that don't have a corresponding widget (data-only properties)
                if property_path[0].upper() not in self.widgets:
                    continue
                if property_path[1].upper() not in self.widgets[property_path[0].upper()]:
                    continue
                    
                if state is False:
                    widget_type = self.widgets[property_path[0].upper()][property_path[1].upper()]["TYPE"]
                    self.manageSignal([property_path[0].upper(),property_path[1].upper()], 'disconnect')

                    if group_name in self.layer_properties_tuples_dict:
                        if widget_type == 'PushButton':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setChecked(state)
                            self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].isChecked()
                        elif widget_type == 'CheckableComboBox':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].deselectAllOptions()
                            self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].checkedItems()
                        elif widget_type == 'ComboBox':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setCurrentIndex(0)
                            self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].currentText()
                        elif widget_type == 'QgsFieldExpressionWidget':
                            # Ensure widget is linked to current layer before setting field
                            if self.current_layer is not None:
                                self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setLayer(self.current_layer)
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setField(self.PROJECT_LAYERS[self.current_layer.id()]["infos"]["primary_key_name"])
                            self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].expression()
                        elif widget_type == 'QgsDoubleSpinBox':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].clearValue()
                            self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].value()
                        elif widget_type == 'LineEdit':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setText('')
                            self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].text()
                        elif widget_type == 'QgsProjectionSelectionWidget':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setCrs(self.PROJECT.crs())
                            self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].crs().authid()
                        elif widget_type == 'PropertyOverrideButton':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setActive(False)
                            self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = False


                    elif group_name in self.export_properties_tuples_dict:
                        if widget_type == 'PushButton':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setChecked(state)
                            self.project_props[property_path[0].upper()][property_path[1].upper()] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].isChecked()
                        elif widget_type == 'CheckBox':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setChecked(state)
                            self.project_props[property_path[0].upper()][property_path[1].upper()] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].isChecked()
                        elif widget_type == 'CheckableComboBox':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].deselectAllOptions()
                            self.project_props[property_path[0].upper()][property_path[1].upper()] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].checkedItems()
                        elif widget_type == 'ComboBox':
                            index = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].findText('GPKG')
                            if index < 0:
                                index = 0
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setCurrentIndex(index)
                            self.project_props[property_path[0].upper()][property_path[1].upper()] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].currentText()
                        elif widget_type == 'QgsFieldExpressionWidget':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setField(self.PROJECT_LAYERS[self.current_layer.id()]["infos"]["primary_key_name"])
                            self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].expression()    
                        elif widget_type == 'QgsDoubleSpinBox':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].clearValue()
                            self.project_props[property_path[0].upper()][property_path[1].upper()] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].value()
                        elif widget_type == 'LineEdit':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setText('')
                            self.project_props[property_path[0].upper()][property_path[1].upper()] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].text()
                        elif widget_type == 'QgsProjectionSelectionWidget':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setCrs(self.PROJECT.crs())
                            self.project_props[property_path[0].upper()][property_path[1].upper()] = self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].crs().authid()
                        elif widget_type == 'PropertyOverrideButton':
                            self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setActive(False)
                            self.project_props[property_path[0].upper()][property_path[1].upper()] = False

                    self.manageSignal([property_path[0].upper(), property_path[1].upper()], 'connect')
                    
                if i == 0 and property_path[1].upper().find('HAS') >= 0:
                    self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setEnabled(True)
                else:
                    self.widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setEnabled(state)
            
            # CRITICAL FIX: Persist reset properties to database
            # When resetting properties, we update PROJECT_LAYERS in memory but must also save to DB
            # Otherwise, on project reload, old values come back from database
            if state is False and self.current_layer is not None:
                if group_name in self.layer_properties_tuples_dict:
                    # Collect properties that were reset for layer properties
                    properties_to_save = []
                    for property_path in tuple_group:
                        # Only save layer properties (not project properties)
                        if property_path[0] in ("infos", "exploring", "filtering"):
                            if property_path[0] in self.PROJECT_LAYERS[self.current_layer.id()]:
                                if property_path[1] in self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]]:
                                    value = self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]]
                                    properties_to_save.append((
                                        property_path[0],  # key_group: 'infos', 'exploring', or 'filtering'
                                        property_path[1],  # key: property name
                                        value,             # value: reset value
                                        type(value)        # type: for proper serialization
                                    ))
                    
                    # Save reset properties to database via FilterMateApp
                    if properties_to_save and hasattr(self, 'app') and self.app is not None:
                        try:
                            logger.debug(f"💾 Persisting {len(properties_to_save)} reset properties for layer {self.current_layer.name()}")
                            self.app.save_variables_from_layer(self.current_layer, properties_to_save)
                        except Exception as e:
                            logger.warning(f"Failed to persist reset properties to DB: {e}")

    def filtering_init_buffer_property(self):

        if self.widgets_initialized is True and self.has_loaded_layers is True:

            # CRITICAL: Verify current_layer and its presence in PROJECT_LAYERS
            if self.current_layer is None or self.current_layer.id() not in self.PROJECT_LAYERS:
                logger.debug("filtering_init_buffer_property: No valid current_layer or not in PROJECT_LAYERS")
                return

            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]   

            name = str("{}_buffer_property_definition".format(self.current_layer.id()))
            description = str("Replace unique buffer value with values based on expression for {}".format(self.current_layer.id()))
            property_definition = QgsPropertyDefinition(name, QgsPropertyDefinition.DataTypeNumeric, description, 'Expression must returns numeric values (unit is in meters)')
            
            buffer_expression = layer_props["filtering"]["buffer_value_expression"]
            # Ensure buffer_expression is a string (handle legacy data with int/float values)
            if not isinstance(buffer_expression, str):
                buffer_expression = str(buffer_expression) if buffer_expression else ''
                # Update stored value to string format
                layer_props["filtering"]["buffer_value_expression"] = buffer_expression
            
            has_valid_expression = buffer_expression and buffer_expression.strip()
            
            if has_valid_expression:
                property = QgsProperty.fromExpression(buffer_expression)
            else:
                property = QgsProperty()
                
            # Initialize the property button with the layer context
            self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].init(0, property, property_definition, self.current_layer)
            
            # Check if property button is active AND has valid expression
            is_active = layer_props["filtering"]["buffer_value_property"]
            
            # Spinbox disabled only when property button is active AND has valid expression
            spinbox_enabled = not (is_active and has_valid_expression)
            self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"].setEnabled(spinbox_enabled)


    def filtering_buffer_property_changed(self):
        """Handle changes to the buffer property override button.
        
        When active (True): Use expression from property button
        When inactive (False): Use static value from spinbox
        """
        if self.widgets_initialized is True and self.has_loaded_layers is True:

            widgets_to_stop = [["FILTERING","BUFFER_VALUE_PROPERTY"]]
            
            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'disconnect')

            # Use widget state directly instead of stored value (which may not be updated yet)
            is_active = self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].isActive()
            has_valid_expression = False
            
            if is_active:
                # Property button is active: get expression from the widget
                qgs_property = self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].toProperty()
                if qgs_property.propertyType() == QgsProperty.ExpressionBasedProperty:
                    expression = qgs_property.asExpression()
                    if expression and expression.strip():
                        self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer_value_expression"] = expression
                        self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer_value_property"] = True
                        has_valid_expression = True
                        logger.debug(f"Property override ACTIVE with expression: '{expression}'")
                    else:
                        self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer_value_expression"] = ''
                        self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer_value_property"] = False
                        logger.debug("Property override ACTIVE but no valid expression")
                else:
                    # No valid expression, clear it
                    self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer_value_expression"] = ''
                    self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer_value_property"] = False
                    logger.debug("Property override ACTIVE but not expression-based")
            else:
                # Property button is inactive: clear expression, use spinbox value
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer_value_expression"] = ''
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer_value_property"] = False
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].setToProperty(QgsProperty())
                logger.debug("Property override INACTIVE - spinbox will be used")

            # Enable/disable spinbox based on property button state and expression validity
            # Spinbox disabled ONLY when property button is active AND has valid expression
            spinbox_enabled = not (is_active and has_valid_expression)
            self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"].setEnabled(spinbox_enabled)
            
            if spinbox_enabled:
                logger.debug("✓ Spinbox ENABLED (property inactive or no valid expression)")
            else:
                logger.debug("✓ Spinbox DISABLED (property active with valid expression)")

            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'connect')


    def get_buffer_property_state(self):
        return self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].isActive()

              
    def dialog_export_output_path(self):

        if self.widgets_initialized and self.has_loaded_layers:

            path = ''
            datatype = ''

            state = self.widgets["EXPORTING"]["HAS_OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].isChecked()

            if self.widgets["EXPORTING"]["HAS_DATATYPE_TO_EXPORT"]["WIDGET"].isChecked():  
                datatype = self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"].currentText()

            if state:

                if self.widgets["EXPORTING"]["HAS_LAYERS_TO_EXPORT"]["WIDGET"].isChecked():

                    layers = self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].checkedItems()
                    if len(layers) == 1 and datatype != '':

                        layer = layers[0]
                        regexp_layer = re.search('.* ', layer)
                        if regexp_layer is not None:
                            layer = regexp_layer.group()
                        path = str(QtWidgets.QFileDialog.getSaveFileName(self, 'Save your layer to a file', os.path.join(self.current_project_path, self.output_name + '_' + layer.strip()) ,'*.{}'.format(datatype))[0])

                    elif datatype.upper() == 'GPKG':

                        path = str(QtWidgets.QFileDialog.getSaveFileName(self, 'Save your layer to a file', os.path.join(self.current_project_path, self.output_name + '.gpkg') ,'*.gpkg')[0])
                    
                    else:
                    
                        path = str(QtWidgets.QFileDialog.getExistingDirectory(self, 'Select a folder where to export your layers', self.current_project_path))

                else:
                
                    path = str(QtWidgets.QFileDialog.getExistingDirectory(self, 'Select a folder where to export your layers', self.current_project_path))

                if path is not None and path != '':
                    path = os.path.normcase(path)
                    self.widgets["EXPORTING"]["OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].setText(path)
                else:
                    state = False
                    self.widgets["EXPORTING"]["OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].clear()
            else:
                self.widgets["EXPORTING"]["OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].clear()

            self.project_property_changed('has_output_folder_to_export', state)
            self.project_property_changed('output_folder_to_export', path)


    def reset_export_output_path(self):

        if self.widgets_initialized and self.has_loaded_layers:

            if str(self.widgets["EXPORTING"]["OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].text()) == '':
                self.widgets["EXPORTING"]["OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].clear()
                self.widgets["EXPORTING"]["HAS_OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].setChecked(False)
                self.project_property_changed('has_output_folder_to_export', False)
                self.project_property_changed('output_folder_to_export', '')

    def dialog_export_output_pathzip(self):

        if self.widgets_initialized and self.has_loaded_layers:
            
            path = ''
            state = self.widgets["EXPORTING"]["HAS_ZIP_TO_EXPORT"]["WIDGET"].isChecked()

            if state:

                path = str(QtWidgets.QFileDialog.getSaveFileName(self, 'Save your exported data to a zip file', os.path.join(self.current_project_path, self.output_name) ,'*.zip')[0])

                if path is not None and path != '':
                    path = os.path.normcase(path)
                    self.widgets["EXPORTING"]["ZIP_TO_EXPORT"]["WIDGET"].setText(path)
                else:
                    state = False
                    self.widgets["EXPORTING"]["ZIP_TO_EXPORT"]["WIDGET"].clear()
            else:
                self.widgets["EXPORTING"]["ZIP_TO_EXPORT"]["WIDGET"].clear()
                
            self.project_property_changed('has_zip_to_export', state)
            self.project_property_changed('zip_to_export', path)


    def reset_export_output_pathzip(self):

        if self.widgets_initialized is True and self.has_loaded_layers is True:
                
            if str(self.widgets["EXPORTING"]["ZIP_TO_EXPORT"]["WIDGET"].text()) == '':
                self.widgets["EXPORTING"]["ZIP_TO_EXPORT"]["WIDGET"].clear()
                self.widgets["EXPORTING"]["HAS_ZIP_TO_EXPORT"]["WIDGET"].setChecked(False)
                self.project_property_changed('has_zip_to_export', False)
                self.project_property_changed('zip_to_export', '')

    def filtering_auto_current_layer_changed(self, state=None):

        if self.widgets_initialized is True and self.has_loaded_layers is True:

            if state is None:
                state = self.project_props["OPTIONS"]["LAYERS"]["LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"]

            self.widgets["FILTERING"]["AUTO_CURRENT_LAYER"]["WIDGET"].setChecked(state)

            if state is True:
                self.project_props["OPTIONS"]["LAYERS"]["LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"] = state
                result = self.manageSignal(["QGIS","LAYER_TREE_VIEW"], 'connect')

            elif state is False:
                self.project_props["OPTIONS"]["LAYERS"]["LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"] = state
                self.manageSignal(["QGIS", "LAYER_TREE_VIEW"], 'disconnect')
                
            self.setProjectVariablesEvent()

    def _update_project_layers_data(self, project_layers, project=None):
        """
        Update internal PROJECT and PROJECT_LAYERS references.
        
        Updates project reference if provided and stores layer data.
        Sets has_loaded_layers flag based on layer count.
        
        Args:
            project_layers (dict): Updated PROJECT_LAYERS dictionary
            project (QgsProject, optional): QGIS project instance
        """
        if project is not None:    
            self.PROJECT = project

        self.PROJECT_LAYERS = project_layers
        
        # Update has_loaded_layers flag based on PROJECT_LAYERS
        if len(list(self.PROJECT_LAYERS)) > 0:
            self.has_loaded_layers = True
        else:
            self.has_loaded_layers = False

        logger.info(f"has_loaded_layers={self.has_loaded_layers}, widgets_initialized={self.widgets_initialized}")

    def _determine_active_layer(self):
        """
        Determine which layer should be active for UI update.
        
        Attempts to find active layer in this priority order:
        1. Current layer from current_layer attribute
        2. QGIS active layer from iface
        3. First available layer in PROJECT_LAYERS
        
        Returns:
            QgsVectorLayer or None: Active layer to use for UI updates
        """
        layer = None
        
        try:
            if self.current_layer is not None:
                # STABILITY FIX: Guard against KeyError before accessing PROJECT_LAYERS
                if self.current_layer.id() not in self.PROJECT_LAYERS:
                    logger.debug(f"_determine_active_layer: layer {self.current_layer.name()} not in PROJECT_LAYERS")
                    if self.iface.activeLayer():
                        layer = self.iface.activeLayer()
                else:
                    layers = [layer for layer in self.PROJECT.mapLayersByName(
                        self.PROJECT_LAYERS[self.current_layer.id()]["infos"]["layer_name"]
                    ) if layer.id() == self.current_layer.id()]
                    
                    if len(layers) == 0:
                        if self.iface.activeLayer():
                            layer = self.iface.activeLayer()
                    elif len(layers) > 0:
                        layer = layers[0]
            else:
                if self.iface.activeLayer():
                    layer = self.iface.activeLayer()
            
            # CRITICAL: If no active layer found but PROJECT_LAYERS has layers,
            # use the first available layer to enable the UI
            if layer is None and len(self.PROJECT_LAYERS) > 0:
                first_layer_id = list(self.PROJECT_LAYERS.keys())[0]
                layer = self.PROJECT.mapLayer(first_layer_id)
                logger.info(f"No active layer - using first available layer: {layer.name() if layer else 'None'}")
                
        except (AttributeError, KeyError, RuntimeError) as e:
            logger.debug(f"Layer lookup failed, falling back to active layer: {e}")
            if self.iface.activeLayer():
                layer = self.iface.activeLayer()
            # Fallback to first layer in PROJECT_LAYERS
            elif len(self.PROJECT_LAYERS) > 0:
                first_layer_id = list(self.PROJECT_LAYERS.keys())[0]
                layer = self.PROJECT.mapLayer(first_layer_id)
                logger.info(f"Exception occurred - using first available layer: {layer.name() if layer else 'None'}")
        
        return layer

    def _activate_layer_ui(self):
        """
        Enable UI widgets and configure basic export functionality.
        
        Enables all widgets, populates export combobox, sets export properties,
        and connects widget signals (only once to avoid duplicates).
        
        Also updates backend indicator based on first available layer type.
        """
        # Track if this is the first time we're activating (transition from empty to loaded)
        was_empty = not self.has_loaded_layers
        
        # Ensure flag is set
        if self.has_loaded_layers is False:
            self.has_loaded_layers = True
        
        # CRITICAL: Always enable widgets if PROJECT_LAYERS has layers
        logger.info(f"About to enable UI: PROJECT_LAYERS count={len(self.PROJECT_LAYERS)}")
        logger.info(f"Calling set_widgets_enabled_state(True)")
        self.set_widgets_enabled_state(True)
        logger.info(f"set_widgets_enabled_state(True) completed - UI should now be enabled")
        
        # Always populate export combobox when layers exist
        self.manageSignal(["EXPORTING","LAYERS_TO_EXPORT"], 'disconnect')
        self.exporting_populate_combobox()
        self.manageSignal(["EXPORTING","LAYERS_TO_EXPORT"], 'connect', 'checkedItemsChanged')
        self.set_exporting_properties()
        
        # Connect signals only once to avoid duplicate connections
        if not self._signals_connected:
            self.connect_widgets_signals()
            self._signals_connected = True
        
        # Update backend indicator even if no specific layer is selected
        if len(self.PROJECT_LAYERS) > 0:
            first_layer_id = list(self.PROJECT_LAYERS.keys())[0]
            if first_layer_id in self.PROJECT_LAYERS:
                layer_props = self.PROJECT_LAYERS[first_layer_id]
                infos = layer_props.get('infos', {})
                if 'layer_provider_type' in infos:
                    provider_type = infos['layer_provider_type']
                    postgresql_conn = infos.get('postgresql_connection_available', None)
                    # Check for forced backend
                    forced_backend = None
                    if hasattr(self, 'forced_backends') and first_layer_id in self.forced_backends:
                        forced_backend = self.forced_backends[first_layer_id]
                    self._update_backend_indicator(provider_type, postgresql_conn, actual_backend=forced_backend)
        
        # Notify user when transitioning from empty to loaded state
        if was_empty and len(self.PROJECT_LAYERS) > 0:
            show_success(
                "FilterMate",
                f"Plugin activé avec {len(self.PROJECT_LAYERS)} couche(s) vectorielle(s)"
            )
            logger.info(f"FilterMate: Plugin activated with {len(self.PROJECT_LAYERS)} layer(s) after being empty")

    def _refresh_layer_specific_widgets(self, layer):
        """
        Refresh UI widgets specific to the active layer.
        
        Updates output name, backend indicator, triggers layer change event,
        initializes exploring groupbox, and refreshes filtering combobox.
        
        Args:
            layer (QgsVectorLayer): Active layer for widget refresh
        """
        if layer is None or not isinstance(layer, QgsVectorLayer):
            return
        
        # Layer-specific initialization
        if layer.id() in self.PROJECT_LAYERS:
            layer_props = self.PROJECT_LAYERS[layer.id()]
            if 'layer_provider_type' in layer_props.get('infos', {}):
                # Check for forced backend
                forced_backend = None
                if hasattr(self, 'forced_backends') and layer.id() in self.forced_backends:
                    forced_backend = self.forced_backends[layer.id()]
                self._update_backend_indicator(layer_props['infos']['layer_provider_type'], actual_backend=forced_backend)
        
        self.manage_output_name()
        self.select_tabTools_index()
        self.current_layer_changed(layer)
        
        # CRITICAL: Only initialize exploring groupbox if layer exists in PROJECT_LAYERS
        if self.current_layer and self.current_layer.id() in self.PROJECT_LAYERS:
            self.exploring_groupbox_init()
        else:
            logger.warning(f"Skipping exploring_groupbox_init for layer {layer.name()} - not yet in PROJECT_LAYERS")
        
        self.filtering_auto_current_layer_changed()
        
        # CRITICAL: Always refresh filtering combobox after layer changes
        if self.current_layer is not None and isinstance(self.current_layer, QgsVectorLayer):
            self.manageSignal(["FILTERING","LAYERS_TO_FILTER"], 'disconnect')
            self.filtering_populate_layers_chekableCombobox(self.current_layer)
            self.manageSignal(["FILTERING","LAYERS_TO_FILTER"], 'connect', 'checkedItemsChanged')

    def get_project_layers_from_app(self, project_layers, project=None):
        """
        Update dockwidget with latest layer information from FilterMateApp.
        
        Called when layer management tasks complete. Orchestrates UI refresh
        by delegating to specialized methods for each concern.
        
        Args:
            project_layers (dict): Updated PROJECT_LAYERS dictionary from app
            project (QgsProject, optional): QGIS project instance
            
        Workflow:
        1. Update PROJECT_LAYERS data
        2. Determine active layer
        3. Activate UI widgets
        4. Refresh layer-specific widgets
        
        Notes:
            - Always updates PROJECT_LAYERS even if widgets not initialized yet
            - Only updates UI if widgets_initialized is True
            - Handles cases with no layers gracefully
            - Called from FilterMateApp.layer_management_engine_task_completed()
        """
        # CRITICAL: Prevent recursive/multiple simultaneous calls
        if self._updating_layers:
            logger.warning("Blocking recursive call to get_project_layers_from_app")
            return
        
        # STABILITY FIX: Validate input parameters
        if project_layers is None:
            logger.warning("get_project_layers_from_app received None for project_layers, using empty dict")
            project_layers = {}
            
        self._updating_layers = True
        self._plugin_busy = True  # STABILITY FIX: Block other operations during layer update
        
        logger.info(f"get_project_layers_from_app called: widgets_initialized={self.widgets_initialized}, PROJECT_LAYERS count={len(project_layers)}")
        
        try:
            # Always update data, even if widgets not initialized yet
            self._update_project_layers_data(project_layers, project)

            # Only update UI if widgets are initialized
            if self.widgets_initialized is True:
                logger.info(f"Updating UI: PROJECT is not None={self.PROJECT is not None}, PROJECT_LAYERS count={len(list(self.PROJECT_LAYERS))}")

                if self.PROJECT is not None and len(list(self.PROJECT_LAYERS)) > 0:
                    # CRITICAL: Force reconnect signals if _signals_connected flag is False
                    # This can happen after a project change when signals were disconnected
                    if not self._signals_connected:
                        logger.info("Reconnecting widget signals after project change")
                        self.connect_widgets_signals()
                        self._signals_connected = True
                    
                    # Determine which layer to use for UI
                    layer = self._determine_active_layer()
                    
                    # Enable UI and configure basic functionality
                    self._activate_layer_ui()
                    
                    # Refresh layer-specific widgets if layer is available
                    if layer is not None:
                        self._refresh_layer_specific_widgets(layer)
                    else:
                        # No active layer - widgets enabled but awaiting user selection
                        logger.info(f"UI enabled with {len(self.PROJECT_LAYERS)} layers but no active layer selected")
                        logger.info("User can click on a layer in the QGIS layer panel to activate it")
                    
                    return
                else:
                    # No project or no layers - disable UI
                    logger.warning(f"Cannot update UI: PROJECT is None={self.PROJECT is None}, PROJECT_LAYERS empty={len(list(self.PROJECT_LAYERS)) == 0}")
                    self.has_loaded_layers = False
                    self.current_layer = None  # STABILITY FIX: Reset current_layer when no layers
                    self.disconnect_widgets_signals()
                    self._signals_connected = False
                    self.set_widgets_enabled_state(False)
                    # Update backend indicator to show waiting state (badge style)
                    if self.backend_indicator_label:
                        self.backend_indicator_label.setText("...")
                        self.backend_indicator_label.setStyleSheet("""
                            QLabel#label_backend_indicator {
                                color: #7f8c8d;
                                font-size: 9pt;
                                font-weight: 600;
                                padding: 3px 10px;
                                border-radius: 12px;
                                border: none;
                                background-color: #ecf0f1;
                            }
                        """)
                    return
            else:
                # Widgets not initialized yet - set flag to refresh later
                logger.debug(f"Widgets not initialized yet, setting pending flag. PROJECT_LAYERS count: {len(self.PROJECT_LAYERS)}")
                self._pending_layers_update = True
        finally:
            # CRITICAL: Always release the lock, even if an error occurred
            self._updating_layers = False
            self._plugin_busy = False  # STABILITY FIX: Release busy flag


    def open_project_page(self):
        if "APP" in self.CONFIG_DATA and "OPTIONS" in self.CONFIG_DATA["APP"]:
            if "GITHUB_PAGE" in self.CONFIG_DATA["APP"]["OPTIONS"]:
                url = self.CONFIG_DATA["APP"]["OPTIONS"]["GITHUB_PAGE"]
                if url and url.startswith("http"):
                    webbrowser.open(url)

    def reload_plugin(self):
        """
        Reload the FilterMate plugin to apply layout changes.
        
        This closes and reopens the dockwidget, applying any pending configuration changes
        including action bar position changes.
        """
        try:
            from qgis.utils import iface, plugins
            
            logger.info("Reloading FilterMate plugin...")
            
            # Save configuration before reload
            self.save_configuration_model()
            
            # Get the FilterMate plugin instance
            if 'filter_mate' in plugins:
                filter_mate_plugin = plugins['filter_mate']
                
                # Close the current dockwidget
                self.close()
                
                # Reset the plugin state
                filter_mate_plugin.pluginIsActive = False
                filter_mate_plugin.app = None
                
                # Use QTimer to delay the reopen slightly
                from qgis.PyQt.QtCore import QTimer
                QTimer.singleShot(100, filter_mate_plugin.run)
                
                logger.info("FilterMate plugin reload initiated")
            else:
                logger.warning("FilterMate plugin not found in plugins dictionary")
                show_warning(
                    "FilterMate",
                    "Could not reload plugin automatically. Please close and reopen the plugin."
                )
        except Exception as e:
            logger.error(f"Error reloading plugin: {e}")
            import traceback
            logger.error(traceback.format_exc())
            show_error(
                "FilterMate",
                f"Error reloading plugin: {str(e)}"
            )


    def setLayerVariableEvent(self, layer=None, properties=None):
        """
        Emit signal to set layer variables.
        
        CRASH FIX (v2.3.15): Added is_valid_layer() check before emitting signal
        to prevent Windows access violations when layer's C++ object is deleted
        during signal processing (e.g., backend change, layer switch, project unload).
        
        Args:
            layer: QgsVectorLayer to set, or None to use current_layer
            properties: List of properties (default: empty list)
        """
        if properties is None:
            properties = []

        if self.widgets_initialized is True:
            if layer is None:
                layer = self.current_layer
            
            # CRASH FIX (v2.3.15): Validate layer before emitting signal
            # This prevents access violations when layer becomes invalid during signal cascade
            if not is_valid_layer(layer):
                logger.debug(f"setLayerVariableEvent: layer is invalid or deleted, skipping emit")
                return
            
            # Ensure properties is a list type for PyQt signal
            if not isinstance(properties, list):
                logger.debug(f"Properties is {type(properties)}, converting to list")
                properties = []

            self.settingLayerVariable.emit(layer, properties)


    def resetLayerVariableOnErrorEvent(self, layer, properties=None):
        """
        Emit signal to reset layer variables after an error.
        
        Args:
            layer: QgsVectorLayer to reset, or None to use current_layer
            properties: List of properties (default: empty list)
        """
        if properties is None:
            properties = []

        if self.widgets_initialized is True:
            if layer is None:
                layer = self.current_layer
            
            # Double-check layer is valid before emitting signal
            try:
                if layer is not None and not sip.isdeleted(layer):
                    # Ensure properties is a list type for PyQt signal
                    if not isinstance(properties, list):
                        logger.debug(f"Properties is {type(properties)}, converting to list")
                        properties = []
                    self.resettingLayerVariableOnError.emit(layer, properties)
                else:
                    logger.debug("Cannot emit resettingLayerVariableOnError - layer is None or deleted")
            except RuntimeError as e:
                # Layer C++ object is deleted
                logger.debug(f"Cannot emit resettingLayerVariableOnError - layer object deleted: {e}")
            except TypeError as e:
                # Signal emission failed due to type mismatch
                logger.warning(f"Signal emission failed - type error: {e}")


    def resetLayerVariableEvent(self, layer=None, properties=None):
        """
        Reset layer properties to default values for exploring and filtering.
        
        This method resets all layer-specific properties (exploring, filtering) to their
        default values, updates PROJECT_LAYERS, saves to SQLite, and refreshes widgets.
        
        Args:
            layer: QgsVectorLayer to reset, or None to use current_layer
            properties: List of properties (unused, kept for backwards compatibility)
        """
        if not self.widgets_initialized:
            return
            
        if layer is None:
            layer = self.current_layer
            
        if layer is None or not is_valid_layer(layer):
            logger.warning("resetLayerVariableEvent: No valid layer to reset")
            return
            
        layer_id = layer.id()
        if layer_id not in self.PROJECT_LAYERS:
            logger.warning(f"resetLayerVariableEvent: Layer {layer.name()} not in PROJECT_LAYERS")
            return
        
        try:
            layer_props = self.PROJECT_LAYERS[layer_id]
            
            # Get best display field for exploring expressions
            best_field = get_best_display_field(layer)
            if not best_field:
                # Fallback to primary key or first field
                primary_key = layer_props.get("infos", {}).get("primary_key_name", "")
                best_field = primary_key if primary_key else ""
            
            # Default exploring properties
            default_exploring = {
                "is_changing_all_layer_properties": True,
                "is_tracking": False,
                "is_selecting": False,
                "is_linking": False,
                "current_exploring_groupbox": "single_selection",
                "single_selection_expression": best_field,
                "multiple_selection_expression": best_field,
                "custom_selection_expression": best_field
            }
            
            # Default filtering properties
            default_filtering = {
                "has_layers_to_filter": False,
                "layers_to_filter": [],
                "has_combine_operator": False,
                "source_layer_combine_operator": "AND",
                "other_layers_combine_operator": "AND",
                "has_geometric_predicates": False,
                "geometric_predicates": [],
                "has_buffer_value": False,
                "buffer_value": 0.0,
                "buffer_value_property": False,
                "buffer_value_expression": "",
                "has_buffer_type": False,
                "buffer_type": "Round"
            }
            
            # Update PROJECT_LAYERS with default values
            layer_props["exploring"].update(default_exploring)
            layer_props["filtering"].update(default_filtering)
            
            # Collect all properties to save
            properties_to_save = []
            for key, value in default_exploring.items():
                properties_to_save.append(("exploring", key))
            for key, value in default_filtering.items():
                properties_to_save.append(("filtering", key))
            
            # Emit signal to save to SQLite and QGIS variables
            self.settingLayerVariable.emit(layer, properties_to_save)
            
            # Refresh widgets with new default values
            self._synchronize_layer_widgets(layer, layer_props)
            
            # Reset buffer spinbox style
            self._update_buffer_spinbox_style(0.0)
            
            # Reset checkable buttons visual state
            self._reset_exploring_button_states(layer_props)
            self._reset_filtering_button_states(layer_props)
            
            logger.info(f"✓ Reset layer '{layer.name()}' properties to defaults")
            
            # Show user feedback
            from qgis.utils import iface
            iface.messageBar().pushSuccess(
                "FilterMate",
                self.tr("Layer properties reset to defaults")
            )
            
        except Exception as e:
            logger.error(f"Error resetting layer properties: {e}")
            from qgis.utils import iface
            iface.messageBar().pushCritical(
                "FilterMate",
                self.tr("Error resetting layer properties: {}").format(str(e))
            )

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
        """Reset filtering button visual states based on layer properties."""
        try:
            filtering = layer_props["filtering"]
            
            # Get button widgets
            buttons = {
                "HAS_LAYERS_TO_FILTER": filtering["has_layers_to_filter"],
                "HAS_COMBINE_OPERATOR": filtering["has_combine_operator"],
                "HAS_GEOMETRIC_PREDICATES": filtering["has_geometric_predicates"],
                "HAS_BUFFER_VALUE": filtering["has_buffer_value"],
                "HAS_BUFFER_TYPE": filtering["has_buffer_type"]
            }
            
            for widget_key, state in buttons.items():
                widget = self.widgets["FILTERING"][widget_key]["WIDGET"]
                widget.blockSignals(True)
                widget.setChecked(state)
                widget.blockSignals(False)
                
            # Reset comboboxes to index 0 (AND)
            source_combo = self.widgets["FILTERING"]["SOURCE_LAYER_COMBINE_OPERATOR"]["WIDGET"]
            other_combo = self.widgets["FILTERING"]["OTHER_LAYERS_COMBINE_OPERATOR"]["WIDGET"]
            
            source_combo.blockSignals(True)
            source_combo.setCurrentIndex(0)  # AND
            source_combo.blockSignals(False)
            
            other_combo.blockSignals(True)
            other_combo.setCurrentIndex(0)  # AND
            other_combo.blockSignals(False)
            
            # Reset buffer value spinbox
            buffer_spinbox = self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"]
            buffer_spinbox.blockSignals(True)
            buffer_spinbox.setValue(0.0)
            buffer_spinbox.blockSignals(False)
            
            # Reset geometric predicates
            geo_combo = self.widgets["FILTERING"]["GEOMETRIC_PREDICATES"]["WIDGET"]
            geo_combo.blockSignals(True)
            geo_combo.setCheckedItems([])
            geo_combo.blockSignals(False)
            
            # Reset layers to filter
            layers_combo = self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"]
            layers_combo.blockSignals(True)
            layers_combo.setCheckedItems([])
            layers_combo.blockSignals(False)
            
        except Exception as e:
            logger.debug(f"Error resetting filtering button states: {e}")

    def setProjectVariablesEvent(self):
        if self.widgets_initialized is True:

            self.settingProjectVariables.emit()

    def _update_backend_indicator(self, provider_type, postgresql_connection_available=None, actual_backend=None):
        """
        Update the backend indicator badge based on the layer provider type and actual backend used.
        
        Uses modern badge styling with colored backgrounds for visual distinction.
        Shows the REAL backend being used (not just provider type).
        
        Args:
            provider_type: The provider type string ('postgresql', 'spatialite', 'ogr', etc.)
            postgresql_connection_available: For PostgreSQL layers, whether connection is available
            actual_backend: The actual backend name being used (from BackendFactory)
        """
        if not hasattr(self, 'backend_indicator_label') or not self.backend_indicator_label:
            return
        
        from .modules.appUtils import POSTGRESQL_AVAILABLE
        
        # Store current provider for backend selection menu
        self._current_provider_type = provider_type
        self._current_postgresql_available = postgresql_connection_available
        
        # Determine backend text and badge style (modern colored badges)
        base_style = """
            QLabel#label_backend_indicator {{
                font-size: 9pt;
                font-weight: 600;
                padding: 3px 10px;
                border-radius: 12px;
                border: none;
                {custom_style}
            }}
            QLabel#label_backend_indicator:hover {{
                opacity: 0.85;
            }}
        """
        
        # CRITICAL FIX: Check both POSTGRESQL_AVAILABLE and postgresql_connection_available
        postgresql_usable = POSTGRESQL_AVAILABLE and (postgresql_connection_available is not False)
        
        # PRIORITY 1: Check if backend is forced by user (always takes precedence)
        current_layer = self.current_layer
        forced_backend_from_dict = None
        if current_layer and hasattr(self, 'forced_backends'):
            if current_layer.id() in self.forced_backends:
                forced_backend_from_dict = self.forced_backends[current_layer.id()]
        
        # Determine actual backend being used
        if actual_backend:
            # Use actual backend name if provided as parameter (forced backend)
            backend_type = actual_backend.lower()
        elif forced_backend_from_dict:
            # Use forced backend from dictionary (user selection via menu)
            backend_type = forced_backend_from_dict.lower()
        else:
            # Auto mode: Apply same logic as BackendFactory to show real backend
            # Get current layer to check feature count for optimization
            feature_count = current_layer.featureCount() if current_layer else -1
            
            # Import optimization logic
            from .modules.backends.factory import should_use_memory_optimization
            from .modules.backends.spatialite_backend import SpatialiteGeometricFilter
            
            # PostgreSQL layers
            if provider_type == 'postgresql' and postgresql_usable:
                # Check if small dataset optimization would be used
                if current_layer and should_use_memory_optimization(current_layer, 'postgresql'):
                    backend_type = 'ogr'  # Small PostgreSQL → OGR memory optimization
                else:
                    backend_type = 'postgresql'
            elif provider_type == 'postgresql' and not postgresql_usable:
                backend_type = 'ogr_fallback'
            # Spatialite layers (native spatialite provider)
            elif provider_type == 'spatialite':
                backend_type = 'spatialite'
            # OGR layers - check if GeoPackage/SQLite with Spatialite support
            elif provider_type == 'ogr':
                # Check if this is a GeoPackage/SQLite that supports Spatialite
                if current_layer:
                    source = current_layer.source()
                    source_path = source.split('|')[0] if '|' in source else source
                    is_gpkg_or_sqlite = (
                        source_path.lower().endswith('.gpkg') or 
                        source_path.lower().endswith('.sqlite')
                    )
                    if is_gpkg_or_sqlite:
                        # Test if Spatialite backend supports this layer
                        spatialite_backend = SpatialiteGeometricFilter({})
                        if spatialite_backend.supports_layer(current_layer):
                            backend_type = 'spatialite'
                        else:
                            backend_type = 'ogr'
                    else:
                        backend_type = 'ogr'
                else:
                    backend_type = 'ogr'
            else:
                backend_type = 'unknown'
        
        # Set text and styling based on backend type
        # Check if backend is forced (either by parameter or from dictionary)
        is_forced = (actual_backend is not None) or (forced_backend_from_dict is not None)
        is_auto_mode = not is_forced
        feature_count = current_layer.featureCount() if current_layer else -1
        
        if backend_type == 'postgresql':
            backend_text = "PostgreSQL"
            custom = "color: white; background-color: #27ae60;"
            tooltip = "Backend: PostgreSQL (High Performance)"
        elif backend_type == 'spatialite':
            backend_text = "Spatialite"
            custom = "color: white; background-color: #9b59b6;"
            tooltip = "Backend: Spatialite (Good Performance)"
        elif backend_type == 'ogr':
            backend_text = "OGR"
            custom = "color: white; background-color: #3498db;"
            # Provide context for OGR usage in auto mode
            if is_auto_mode and provider_type == 'postgresql':
                tooltip = f"Backend: OGR (Memory Optimization - {feature_count:,} features)"
            elif is_auto_mode and provider_type == 'spatialite':
                tooltip = f"Backend: OGR (Small Dataset - {feature_count:,} features)"
            else:
                tooltip = "Backend: OGR (Universal)"
        elif backend_type == 'ogr_fallback':
            backend_text = "OGR*"
            custom = "color: white; background-color: #e67e22;"  # Orange for fallback
            tooltip = "Backend: OGR (Fallback - PostgreSQL connection unavailable)"
        else:
            backend_text = provider_type[:6].upper() if provider_type else "..."
            custom = "color: #7f8c8d; background-color: #ecf0f1;"
            tooltip = f"Backend: {provider_type or 'Unknown'}"
        
        # Add forced indicator if backend was forced by user
        if is_forced:
            backend_text = f"{backend_text}⚡"
            forced_backend_name = actual_backend or forced_backend_from_dict
            tooltip += f"\n(Forced by user: {forced_backend_name.upper()})"
        
        tooltip += "\n\nClick to change backend"
        
        self.backend_indicator_label.setText(backend_text)
        self.backend_indicator_label.setStyleSheet(base_style.format(custom_style=custom))
        self.backend_indicator_label.setToolTip(tooltip)
        self.backend_indicator_label.adjustSize()

    def getProjectLayersEvent(self, event):

        if self.widgets_initialized is True:

            self.gettingProjectLayers.emit()

    def closeEvent(self, event):
        """Clean up resources before closing."""
        if self.widgets_initialized is True:
            # CRITICAL: Clear QgsMapLayerComboBox to prevent access violations
            # when layers are removed or project is closed
            try:
                if hasattr(self, 'comboBox_filtering_current_layer'):
                    self.comboBox_filtering_current_layer.setLayer(None)
                    self.comboBox_filtering_current_layer.clear()
            except Exception as e:
                logger.debug(f"FilterMate: Error clearing layer combo on close: {e}")
            
            # Clean up exploring cache
            try:
                if hasattr(self, '_exploring_cache'):
                    stats = self._exploring_cache.get_stats()
                    logger.info(f"Exploring cache stats on close: {stats}")
                    self._exploring_cache.invalidate_all()
            except Exception as e:
                logger.debug(f"FilterMate: Error cleaning up exploring cache: {e}")
            
            # Clean up theme watcher
            try:
                if self._theme_watcher is not None:
                    self._theme_watcher.remove_callback(self._on_qgis_theme_changed)
                    logger.debug("Theme watcher callback removed")
            except Exception as e:
                logger.debug(f"FilterMate: Error cleaning up theme watcher: {e}")
            
            self.closingPlugin.emit()
            event.accept()

    def get_exploring_cache_stats(self):
        """
        Get statistics about the exploring features cache.
        
        Returns:
            dict: Cache statistics including hits, misses, hit ratio, and entry counts.
                  Returns empty dict if cache is not initialized.
        
        Example:
            >>> stats = self.get_exploring_cache_stats()
            >>> print(f"Cache hit ratio: {stats['hit_ratio']}")
        """
        if hasattr(self, '_exploring_cache'):
            return self._exploring_cache.get_stats()
        return {}
    
    def invalidate_exploring_cache(self, layer_id=None, groupbox_type=None):
        """
        Invalidate the exploring features cache.
        
        Args:
            layer_id: Optional layer ID to invalidate. If None, invalidates all layers.
            groupbox_type: Optional groupbox type ('single_selection', 'multiple_selection', 
                          'custom_selection'). If None with layer_id, invalidates all 
                          groupboxes for that layer.
        
        Example:
            >>> self.invalidate_exploring_cache()  # Clear all
            >>> self.invalidate_exploring_cache(layer.id())  # Clear specific layer
            >>> self.invalidate_exploring_cache(layer.id(), 'single_selection')  # Clear specific
        """
        if hasattr(self, '_exploring_cache'):
            if layer_id is None:
                self._exploring_cache.invalidate_all()
                logger.debug("Exploring cache: invalidated all entries")
            elif groupbox_type is None:
                self._exploring_cache.invalidate_layer(layer_id)
                logger.debug(f"Exploring cache: invalidated layer {layer_id[:8]}...")
            else:
                self._exploring_cache.invalidate(layer_id, groupbox_type)
                logger.debug(f"Exploring cache: invalidated {layer_id[:8]}.../{groupbox_type}")

    def launchTaskEvent(self, state, task_name):

        if self.widgets_initialized is True:

            # CRITICAL: Verify current_layer and its presence in PROJECT_LAYERS
            if self.current_layer is None or self.current_layer.id() not in self.PROJECT_LAYERS:
                logger.warning(f"launchTaskEvent: Cannot launch task {task_name} - no valid current_layer")
                return

            self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["layers_to_filter"] = self.get_layers_to_filter()
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
        """
        Handle F5 shortcut to reload layers.
        
        Emits the launchingTask signal with 'reload_layers' to trigger
        a complete reload of all layers from the current project.
        """
        logger.info("F5 pressed - Force reloading layers")
        self._trigger_reload_layers()
    
    def _trigger_reload_layers(self):
        """
        Trigger layer reload from shortcut (F5) or backend indicator click.
        
        Shows visual feedback on the indicator and emits the reload signal.
        """
        # Visual feedback - show loading state on backend indicator
        if hasattr(self, 'backend_indicator_label') and self.backend_indicator_label:
            self.backend_indicator_label.setText("⟳")
            self.backend_indicator_label.setStyleSheet("""
                QLabel#label_backend_indicator {
                    color: #3498db;
                    font-size: 9pt;
                    font-weight: 600;
                    padding: 3px 10px;
                    border-radius: 12px;
                    border: none;
                    background-color: #e8f4fc;
                }
            """)
        
        # Emit reload signal
        self.launchingTask.emit('reload_layers')

    def _on_undo_shortcut(self):
        """
        Handle Ctrl+Z shortcut to undo last filter operation.
        
        Triggers the undo action if the undo button is enabled.
        """
        logger.info("Ctrl+Z pressed - Undo filter operation")
        undo_widget = self.widgets.get("ACTION", {}).get("UNDO_FILTER", {}).get("WIDGET")
        if undo_widget and undo_widget.isEnabled():
            self.launchTaskEvent(False, 'undo')
        else:
            logger.debug("Undo shortcut ignored - no undo available")

    def _on_redo_shortcut(self):
        """
        Handle Ctrl+Y shortcut to redo last undone filter operation.
        
        Triggers the redo action if the redo button is enabled.
        """
        logger.info("Ctrl+Y pressed - Redo filter operation")
        redo_widget = self.widgets.get("ACTION", {}).get("REDO_FILTER", {}).get("WIDGET")
        if redo_widget and redo_widget.isEnabled():
            self.launchTaskEvent(False, 'redo')
        else:
            logger.debug("Redo shortcut ignored - no redo available")




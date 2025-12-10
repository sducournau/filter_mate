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
    QApplication,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QVBoxLayout
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
from .modules.appUtils import (
    get_datasource_connexion_from_layer,
    get_primary_key_name,
    POSTGRESQL_AVAILABLE
)
from .modules.customExceptions import SignalStateChangeError
from .modules.constants import PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR
from .modules.ui_styles import StyleLoader
from .filter_mate_dockwidget_base import Ui_FilterMateDockWidgetBase

# Import UI configuration system for dynamic dimensions
try:
    from .modules.ui_config import UIConfig
    from .modules import ui_widget_utils as ui_utils
    UI_CONFIG_AVAILABLE = True
except ImportError:
    UI_CONFIG_AVAILABLE = False
    print("FilterMate: UI configuration system not available, using default dimensions")

class FilterMateDockWidget(QtWidgets.QDockWidget, Ui_FilterMateDockWidgetBase):

    closingPlugin = pyqtSignal()
    launchingTask = pyqtSignal(str)

    gettingProjectLayers = pyqtSignal()

    settingLayerVariable = pyqtSignal(QgsVectorLayer, list)
    resettingLayerVariable = pyqtSignal(QgsVectorLayer, list)
    resettingLayerVariableOnError = pyqtSignal(QgsVectorLayer, list)

    settingProjectVariables = pyqtSignal()
    
    # Static cache for geometry icons to avoid repeated calculations
    _icon_cache = {}

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
        self._signals_connected = False
        self._pending_layers_update = False  # Flag to track if layers were updated before widgets_initialized
        
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

        self.predicates = None
        self.buffer_property_has_been_init = False
        self.project_props = None
        self.layer_properties_tuples_dict = None
        self.export_properties_tuples_dict = None
        self.json_template_project_exporting = '{"has_layers_to_export":false,"layers_to_export":[],"has_projection_to_export":false,"projection_to_export":"","has_styles_to_export":false,"styles_to_export":"","has_datatype_to_export":false,"datatype_to_export":"","datatype_to_export":"","has_output_folder_to_export":false,"output_folder_to_export":"","has_zip_to_export":false,"zip_to_export":"","batch_output_folder":false,"batch_zip":false }'

        # Initialize config changes tracking
        self.pending_config_changes = []
        self.config_changes_pending = False

        self.setupUi(self)
        self.setupUiCustom()
        self.manage_ui_style()
        self.manage_interactions()
        

    def getSignal(self, oObject : QObject, strSignalName : str):
        oMetaObj = oObject.metaObject()
        for i in range (oMetaObj.methodCount()):
            oMetaMethod = oMetaObj.method(i)
            if not oMetaMethod.isValid():
                continue
            if oMetaMethod.methodType () == QMetaMethod.Signal and \
                oMetaMethod.name() == strSignalName:
                return oMetaMethod

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
                    state = self.changeSignalState(widget_path, current_signal_name, current_triggered_function, custom_action)

        else:
            for signal in widget_object["SIGNALS"]:
                if signal[-1] is not None:
                    current_signal_name = str(signal[0])
                    current_triggered_function = signal[-1]
                    state = self.changeSignalState(widget_path, current_signal_name, current_triggered_function, custom_action)
        
        if state == None:
            raise SignalStateChangeError(state, widget_path)

        return state
        

        

    def changeSignalState(self, widget_path, current_signal_name, current_triggered_function, custom_action=None):
        state = None

        if isinstance(widget_path, list) and len(widget_path) == 2:
            if hasattr(self.widgets[widget_path[0]][widget_path[1]]["WIDGET"], current_signal_name):
                state = self.widgets[widget_path[0]][widget_path[1]]["WIDGET"].isSignalConnected(self.getSignal(self.widgets[widget_path[0]][widget_path[1]]["WIDGET"], current_signal_name))
                if custom_action is not None:
                    if custom_action == 'disconnect' and state == True:
                        getattr(self.widgets[widget_path[0]][widget_path[1]]["WIDGET"], current_signal_name).disconnect()
                    elif custom_action == 'connect' and state == False:
                        getattr(self.widgets[widget_path[0]][widget_path[1]]["WIDGET"], current_signal_name).connect(current_triggered_function)
                else:
                    if state == True:
                        getattr(self.widgets[widget_path[0]][widget_path[1]]["WIDGET"], current_signal_name).disconnect()
                    else:
                        getattr(self.widgets[widget_path[0]][widget_path[1]]["WIDGET"], current_signal_name).connect(current_triggered_function)

                state = self.widgets[widget_path[0]][widget_path[1]]["WIDGET"].isSignalConnected(self.getSignal(self.widgets[widget_path[0]][widget_path[1]]["WIDGET"], current_signal_name))   
                return state
        
        if state == None:
            raise SignalStateChangeError(state, widget_path)

    def reset_multiple_checkable_combobox(self):
        """
        Safely reset and recreate the multiple checkable combobox widget.
        
        This method handles proper cleanup of the old widget and creation of a new one
        to avoid Qt memory issues and crashes.
        """
        try:
            layout = self.verticalLayout_exploring_multiple_selection
            
            # Safely remove old widget from layout
            if layout.count() > 0:
                item = layout.itemAt(0)
                if item and item.widget():
                    old_widget = item.widget()
                    layout.removeWidget(old_widget)
                    # Properly delete the old widget to free resources
                    old_widget.deleteLater()
                elif item:
                    layout.removeItem(item)
            
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

            # Insert new widget into layout
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


    def setupUiCustom(self):
        self.set_multiple_checkable_combobox()
        
        # Apply dynamic dimensions based on active profile
        self.apply_dynamic_dimensions()

        # Setup backend indicator (right-aligned label showing current backend)
        self._setup_backend_indicator()
        
        # Setup tab-specific widgets
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


    def apply_dynamic_dimensions(self):
        """
        Apply dynamic dimensions to widgets based on active UI profile (compact/normal).
        
        Orchestrates the application of dimensions by calling specialized methods.
        Called from setupUiCustom() during initialization.
        """
        try:
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
        Apply dimensions to frames and widget key containers.
        
        Sets min/max widths for widget key containers and heights for main frames.
        """
        from .modules.ui_config import UIConfig
        
        # Get widget_keys dimensions
        widget_keys_min_width = UIConfig.get_config('widget_keys', 'min_width')
        widget_keys_max_width = UIConfig.get_config('widget_keys', 'max_width')
        
        # Get frame dimensions
        frame_exploring_min = UIConfig.get_config('frame_exploring', 'min_height')
        frame_exploring_max = UIConfig.get_config('frame_exploring', 'max_height')
        frame_filtering_min = UIConfig.get_config('frame_filtering', 'min_height')
        
        # Apply to widget keys containers
        if hasattr(self, 'widget_exploring_keys'):
            self.widget_exploring_keys.setMinimumWidth(widget_keys_min_width)
            self.widget_exploring_keys.setMaximumWidth(widget_keys_max_width)
        
        if hasattr(self, 'widget_filtering_keys'):
            self.widget_filtering_keys.setMinimumWidth(widget_keys_min_width)
            self.widget_filtering_keys.setMaximumWidth(widget_keys_max_width)
        
        if hasattr(self, 'widget_exporting_keys'):
            self.widget_exporting_keys.setMinimumWidth(widget_keys_min_width)
            self.widget_exporting_keys.setMaximumWidth(widget_keys_max_width)
        
        # Apply to main frames
        if hasattr(self, 'frame_exploring'):
            self.frame_exploring.setMinimumHeight(frame_exploring_min)
            self.frame_exploring.setMaximumHeight(frame_exploring_max)
        
        if hasattr(self, 'frame_filtering'):
            self.frame_filtering.setMinimumHeight(frame_filtering_min)
        
        logger.debug(f"Applied frame dimensions: widget_keys={widget_keys_min_width}-{widget_keys_max_width}px")
    
    def _harmonize_checkable_pushbuttons(self):
        """
        Harmonize dimensions of all checkable pushbuttons across tabs.
        
        Applies consistent sizing to exploring, filtering, and exporting pushbuttons
        based on the active UI profile (compact/normal).
        """
        try:
            from qgis.PyQt.QtWidgets import QPushButton, QSizePolicy
            from qgis.PyQt.QtCore import QSize
            from .modules.ui_config import UIConfig, DisplayProfile
            
            # Get dynamic dimensions based on active profile (compact/normal)
            is_compact = UIConfig._active_profile == DisplayProfile.COMPACT
            
            if is_compact:
                # Compact mode - smaller pushbuttons
                pushbutton_min_width = 18
                pushbutton_max_width = 20
                pushbutton_min_height = 18
                pushbutton_max_height = 25
                pushbutton_icon_size = 16
            else:
                # Normal mode - larger pushbuttons (ratio ~1.5x)
                pushbutton_min_width = 27
                pushbutton_max_width = 30
                pushbutton_min_height = 27
                pushbutton_max_height = 38
                pushbutton_icon_size = 24
            
            # Get all checkable pushbuttons with consistent naming pattern
            checkable_buttons = []
            
            # Exploring buttons
            exploring_button_names = [
                'pushButton_checkable_exploring_selecting',
                'pushButton_checkable_exploring_tracking',
                'pushButton_checkable_exploring_linking_widgets'
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
            
            # Apply consistent dimensions to all checkable pushbuttons
            for button_name in all_button_names:
                if hasattr(self, button_name):
                    button = getattr(self, button_name)
                    if isinstance(button, QPushButton):
                        # Set consistent size constraints
                        button.setMinimumSize(pushbutton_min_width, pushbutton_min_height)
                        button.setMaximumSize(pushbutton_max_width, pushbutton_max_height)
                        
                        # Set consistent icon size
                        button.setIconSize(QSize(pushbutton_icon_size, pushbutton_icon_size))
                        
                        # Ensure consistent style properties
                        button.setFlat(True)
                        button.setCheckable(True)
                        
                        # Set consistent size policy
                        button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
                        
                        checkable_buttons.append(button_name)
            
            mode_name = 'COMPACT' if is_compact else 'NORMAL'
            logger.debug(f"Harmonized {len(checkable_buttons)} checkable pushbuttons in {mode_name} mode: {pushbutton_min_width}-{pushbutton_max_width}x{pushbutton_min_height}-{pushbutton_max_height}px")
            
        except Exception as e:
            logger.warning(f"Could not harmonize checkable pushbuttons: {e}")
            import traceback
            traceback.print_exc()
    
    def _apply_layout_spacing(self):
        """
        Apply consistent spacing to layouts across all tabs.
        
        Sets spacing for exploring groupbox layouts and margins for groupbox content areas.
        """
        try:
            from .modules.ui_config import UIConfig
            
            # Get layout spacing from config
            layout_spacing = UIConfig.get_config('layout', 'spacing_frame') or 6
            
            # Apply spacing to exploring layouts to prevent widget overlap
            if hasattr(self, 'verticalLayout_exploring_single_selection'):
                self.verticalLayout_exploring_single_selection.setSpacing(layout_spacing)
            
            if hasattr(self, 'verticalLayout_exploring_multiple_selection'):
                self.verticalLayout_exploring_multiple_selection.setSpacing(layout_spacing)
            
            if hasattr(self, 'verticalLayout_exploring_custom_selection'):
                self.verticalLayout_exploring_custom_selection.setSpacing(layout_spacing)
            
            # Apply dynamic margins to groupbox layouts
            margins_frame = UIConfig.get_config('layout', 'margins_frame')
            if margins_frame and isinstance(margins_frame, dict):
                left = margins_frame.get('left', 4)
                top = margins_frame.get('top', 6)
                right = margins_frame.get('right', 4)
                bottom = margins_frame.get('bottom', 6)
                
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
                
                logger.debug(f"Applied groupbox margins: {left}-{top}-{right}-{bottom}")
            
            logger.debug(f"Applied layout spacing: {layout_spacing}px")
            
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
        and their parent containers.
        """
        try:
            from .modules.ui_config import UIConfig
            
            # Get layout spacing from config
            layout_spacing = UIConfig.get_config('layout', 'spacing_frame') or 4
            
            # Apply consistent spacing and alignment to ALL key layouts
            key_layouts = [
                ('verticalLayout_exploring_keys', 'exploring keys'),
                ('verticalLayout_filtering_keys', 'filtering keys'),
                ('verticalLayout_exporting_keys', 'exporting keys')
            ]
            
            for layout_name, description in key_layouts:
                if hasattr(self, layout_name):
                    layout = getattr(self, layout_name)
                    # Set consistent spacing between items
                    layout.setSpacing(layout_spacing)
                    # Remove content margins for alignment
                    layout.setContentsMargins(0, 0, 0, 0)
                    # Center buttons vertically within their space
                    layout.setAlignment(Qt.AlignVCenter)
            
            # Apply consistent styling to parent container layouts
            parent_widgets = [
                ('widget_exploring_keys', 'exploring'),
                ('widget_filtering_keys', 'filtering'),
                ('widget_exporting_keys', 'exporting')
            ]
            
            for widget_name, section in parent_widgets:
                if hasattr(self, widget_name):
                    parent_layout = getattr(self, widget_name).layout()
                    if parent_layout:
                        # Minimal horizontal margins, no vertical margins
                        parent_layout.setContentsMargins(2, 0, 2, 0)
                        # Center content
                        parent_layout.setAlignment(Qt.AlignCenter)
            
            logger.debug(f"Aligned key layouts with {layout_spacing}px spacing")
            
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
        Create and configure backend indicator label.
        
        Sets up the label displaying the current backend type (PostgreSQL/Spatialite/OGR)
        with right alignment in the main layout.
        """
        # Create backend indicator label with horizontal layout for right alignment
        self.backend_indicator_label = QtWidgets.QLabel(self)
        self.backend_indicator_label.setObjectName("label_backend_indicator")
        self.backend_indicator_label.setText("Backend: Detecting...")
        self.backend_indicator_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        # Create horizontal layout for backend indicator (right-aligned)
        backend_indicator_layout = QtWidgets.QHBoxLayout()
        backend_indicator_layout.setContentsMargins(2, 0, 2, 0)
        backend_indicator_layout.setSpacing(0)
        backend_indicator_layout.addStretch()  # Push label to the right
        backend_indicator_layout.addWidget(self.backend_indicator_label)
        
        # Add to the main layout (top of the widget)
        if hasattr(self, 'verticalLayout_main_root'):
            self.verticalLayout_main_root.insertLayout(0, backend_indicator_layout)

    def _setup_exploring_tab_widgets(self):
        """
        Configure widgets for the Exploring tab.
        
        Sets up checkableComboBox for feature selection and configures mFieldExpressionWidget
        for single/multiple/custom selection modes. Synchronizes with init_layer if available.
        """
        layout = self.verticalLayout_exploring_multiple_selection
        layout.insertWidget(0, self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection)

        # Configure QgsFieldExpressionWidget to allow all field types (except geometry)
        # QgsFieldProxyModel.AllTypes includes all field types
        # We exclude only geometry fields using ~SkipGeometry filter
        field_filters = QgsFieldProxyModel.AllTypes
        self.mFieldExpressionWidget_exploring_single_selection.setFilters(field_filters)
        self.mFieldExpressionWidget_exploring_multiple_selection.setFilters(field_filters)
        self.mFieldExpressionWidget_exploring_custom_selection.setFilters(field_filters)
        
        # Initialize QgsFieldExpressionWidget with init layer if available
        if self.init_layer and isinstance(self.init_layer, QgsVectorLayer):
            # Initialize all mFieldExpressionWidget with init_layer
            self.mFieldExpressionWidget_exploring_single_selection.setLayer(self.init_layer)
            self.mFieldExpressionWidget_exploring_multiple_selection.setLayer(self.init_layer)
            self.mFieldExpressionWidget_exploring_custom_selection.setLayer(self.init_layer)

    def _setup_filtering_tab_widgets(self):
        """
        Configure widgets for the Filtering tab.
        
        Sets up comboBox_filtering_current_layer (VectorLayer filter), creates and configures
        checkableComboBoxLayer_filtering_layers_to_filter, and synchronizes with init_layer.
        Updates backend indicator based on current layer's provider type.
        """
        # Filter comboBox_filtering_current_layer to show only vector layers
        self.comboBox_filtering_current_layer.setFilters(QgsMapLayerProxyModel.VectorLayer)
        
        # Synchronize comboBox_filtering_current_layer with init_layer if available
        if self.init_layer and isinstance(self.init_layer, QgsVectorLayer):
            self.comboBox_filtering_current_layer.setLayer(self.init_layer)
            
            # Update backend indicator with initial layer
            if self.init_layer.id() in self.PROJECT_LAYERS:
                layer_props = self.PROJECT_LAYERS[self.init_layer.id()]
                if 'layer_provider_type' in layer_props.get('infos', {}):
                    self._update_backend_indicator(layer_props['infos']['layer_provider_type'])
            else:
                # PROJECT_LAYERS not populated yet, detect directly from layer
                provider_type = self.init_layer.providerType()
                if provider_type == 'postgres':
                    self._update_backend_indicator(PROVIDER_POSTGRES)
                elif provider_type == 'spatialite':
                    self._update_backend_indicator(PROVIDER_SPATIALITE)
                elif provider_type == 'ogr':
                    self._update_backend_indicator(PROVIDER_OGR)
                else:
                    self._update_backend_indicator(provider_type)

        # Create custom checkable combobox for layers to filter
        self.checkableComboBoxLayer_filtering_layers_to_filter = QgsCheckableComboBoxLayer(self)
        
        # Insert into layout
        layout = self.verticalLayout_filtering_values
        layout.insertWidget(3, self.checkableComboBoxLayer_filtering_layers_to_filter)
        
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
        self.checkableComboBoxLayer_exporting_layers = QgsCheckableComboBoxLayer(self)
        
        # Find the layout that contains verticalSpacer_exporting_values_top
        # This layout is the second child of horizontalLayout_3 in the exporting tab
        exporting_tab_layout = self.findChild(QHBoxLayout, 'horizontalLayout_3')
        if exporting_tab_layout:
            # The verticalLayout is the layout at index 1 (second item) of horizontalLayout_3
            exporting_values_layout = exporting_tab_layout.itemAt(1)
            if exporting_values_layout:
                # Insert the combobox right after the top spacer (index 1)
                exporting_values_layout.insertWidget(1, self.checkableComboBoxLayer_exporting_layers)
        
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
        
        # Configure map canvas selection color
        self.iface.mapCanvas().setSelectionColor(QColor(237, 97, 62, 75))

    def dockwidget_widgets_configuration(self):

        self.layer_properties_tuples_dict =   {
                                                "is":(("exploring","is_selecting"),("exploring","is_tracking"),("exploring","is_linking")),
                                                "selection_expression":(("exploring","single_selection_expression"),("exploring","multiple_selection_expression"),("exploring","custom_selection_expression")),
                                                "layers_to_filter":(("filtering","has_layers_to_filter"),("filtering","layers_to_filter")),
                                                "combine_operator":(("filtering", "has_combine_operator"), ("filtering", "source_layer_combine_operator"),("filtering", "other_layers_combine_operator")),
                                                "buffer_type":(("filtering","has_buffer_type"),("filtering","buffer_type")),
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
            
        self.widgets["DOCK"] = {
                                "SINGLE_SELECTION":{"TYPE":"GroupBox", "WIDGET":self.mGroupBox_exploring_single_selection, "SIGNALS":[("clicked", lambda state, x='single_selection': self.exploring_groupbox_changed(x))]},
                                "MULTIPLE_SELECTION":{"TYPE":"GroupBox","WIDGET":self.mGroupBox_exploring_multiple_selection, "SIGNALS":[("clicked", lambda state, x='multiple_selection': self.exploring_groupbox_changed(x))]},
                                "CUSTOM_SELECTION":{"TYPE":"GroupBox","WIDGET":self.mGroupBox_exploring_custom_selection, "SIGNALS":[("clicked", lambda state, x='custom_selection': self.exploring_groupbox_changed(x))]},
                                "CONFIGURATION_TREE_VIEW":{"TYPE":"JsonTreeView","WIDGET":self.config_view, "SIGNALS":[("collapsed", None),("expanded", None)]},
                                "CONFIGURATION_MODEL":{"TYPE":"JsonModel","WIDGET":self.config_model, "SIGNALS":[("itemChanged", None)]},
                                "CONFIGURATION_BUTTONBOX":{"TYPE":"DialogButtonBox","WIDGET":self.buttonBox, "SIGNALS":[("accepted", None),("rejected", None)]},
                                "TOOLS":{"TYPE":"ToolBox","WIDGET":self.toolBox_tabTools, "SIGNALS":[("currentChanged", self.select_tabTools_index)]}
                                }   

        self.widgets["ACTION"] = {
                                "FILTER":{"TYPE":"PushButton", "WIDGET":self.pushButton_action_filter, "SIGNALS":[("clicked", lambda state, x='filter': self.launchTaskEvent(state, x))], "ICON":None},
                                "UNFILTER":{"TYPE":"PushButton", "WIDGET":self.pushButton_action_undo_filter, "SIGNALS":[("clicked", lambda state, x='unfilter': self.launchTaskEvent(state, x))], "ICON":None},
                                "RESET":{"TYPE":"PushButton", "WIDGET":self.pushButton_action_reset, "SIGNALS":[("clicked", lambda state, x='reset': self.launchTaskEvent(state, x))], "ICON":None},
                                "EXPORT":{"TYPE":"PushButton", "WIDGET":self.pushButton_action_export, "SIGNALS":[("clicked", lambda state, x='export': self.launchTaskEvent(state, x))], "ICON":None},
                                "ABOUT":{"TYPE":"PushButton", "WIDGET":self.pushButton_action_about, "SIGNALS":[("clicked", self.open_project_page)], "ICON":None}
                                }        


        self.widgets["EXPLORING"] = {
                                    "IDENTIFY":{"TYPE":"PushButton", "WIDGET":self.pushButton_exploring_identify, "SIGNALS":[("clicked", self.exploring_identify_clicked)], "ICON":None},
                                    "ZOOM":{"TYPE":"PushButton", "WIDGET":self.pushButton_exploring_zoom, "SIGNALS":[("clicked", self.exploring_zoom_clicked)], "ICON":None},
                                    "IS_SELECTING":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exploring_selecting, "SIGNALS":[("clicked", lambda state, x='is_selecting', custom_functions={"ON_TRUE": lambda x: self.exploring_select_features(), "ON_FALSE": lambda x: self.exploring_deselect_features()}: self.layer_property_changed(x, state, custom_functions))], "ICON":None},
                                    "IS_TRACKING":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exploring_tracking, "SIGNALS":[("clicked", lambda state, x='is_tracking', custom_functions={"ON_TRUE": lambda x: self.get_current_features()}: self.layer_property_changed(x, state, custom_functions))], "ICON":None},
                                    "IS_LINKING":{"TYPE":"PushButton", "WIDGET":self.pushButton_checkable_exploring_linking_widgets, "SIGNALS":[("clicked", lambda state, x='is_linking', custom_functions={"ON_CHANGE": lambda x: self.exploring_link_widgets()}: self.layer_property_changed(x, state, custom_functions))], "ICON":None},
                                    "RESET_ALL_LAYER_PROPERTIES":{"TYPE":"PushButton", "WIDGET":self.pushButton_exploring_reset_layer_properties, "SIGNALS":[("clicked", lambda: self.resetLayerVariableEvent())], "ICON":None},
                                    
                                    "SINGLE_SELECTION_FEATURES":{"TYPE":"FeatureComboBox", "WIDGET":self.mFeaturePickerWidget_exploring_single_selection, "SIGNALS":[("featureChanged", self.exploring_features_changed)]},
                                    "SINGLE_SELECTION_EXPRESSION":{"TYPE":"QgsFieldExpressionWidget", "WIDGET":self.mFieldExpressionWidget_exploring_single_selection, "SIGNALS":[("fieldChanged", lambda state, x='single_selection_expression', custom_functions={"ON_CHANGE": lambda x: self.exploring_source_params_changed()}: self.layer_property_changed(x, state, custom_functions))]},
                                    
                                    "MULTIPLE_SELECTION_FEATURES":{"TYPE":"CustomCheckableFeatureComboBox", "WIDGET":self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection, "SIGNALS":[("updatingCheckedItemList", self.exploring_features_changed),("filteringCheckedItemList", self.exploring_source_params_changed)]},
                                    "MULTIPLE_SELECTION_EXPRESSION":{"TYPE":"QgsFieldExpressionWidget", "WIDGET":self.mFieldExpressionWidget_exploring_multiple_selection, "SIGNALS":[("fieldChanged", lambda state, x='multiple_selection_expression', custom_functions={"ON_CHANGE": lambda x: self.exploring_source_params_changed()}: self.layer_property_changed(x, state, custom_functions))]},
                                    
                                    "CUSTOM_SELECTION_EXPRESSION":{"TYPE":"QgsFieldExpressionWidget", "WIDGET":self.mFieldExpressionWidget_exploring_custom_selection, "SIGNALS":[("fieldChanged", lambda state, x='custom_selection_expression', custom_functions={"ON_CHANGE": lambda x: self.exploring_source_params_changed()}: self.layer_property_changed(x, state, custom_functions))]}
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
                                    "SOURCE_LAYER_COMBINE_OPERATOR":{"TYPE":"ComboBox", "WIDGET":self.comboBox_filtering_source_layer_combine_operator, "SIGNALS":[("currentTextChanged", lambda state, x='source_layer_combine_operator': self.layer_property_changed(x, state))]},
                                    "OTHER_LAYERS_COMBINE_OPERATOR":{"TYPE":"ComboBox", "WIDGET":self.comboBox_filtering_other_layers_combine_operator, "SIGNALS":[("currentTextChanged", lambda state, x='other_layers_combine_operator': self.layer_property_changed(x, state))]},
                                    "GEOMETRIC_PREDICATES":{"TYPE":"CheckableComboBox", "WIDGET":self.comboBox_filtering_geometric_predicates, "SIGNALS":[("checkedItemsChanged", lambda state, x='geometric_predicates': self.layer_property_changed(x, state))]},
                                    "BUFFER_VALUE":{"TYPE":"QgsDoubleSpinBox", "WIDGET":self.mQgsDoubleSpinBox_filtering_buffer_value, "SIGNALS":[("valueChanged", lambda state, x='buffer_value': self.layer_property_changed(x, state))]},
                                    "BUFFER_VALUE_PROPERTY":{"TYPE":"PropertyOverrideButton", "WIDGET":self.mPropertyOverrideButton_filtering_buffer_value_property, "SIGNALS":[("activated", lambda state, x='buffer_value_property', custom_functions={"ON_CHANGE": lambda x: self.filtering_buffer_property_changed(), "CUSTOM_DATA": lambda x: self.get_buffer_property_state()}: self.layer_property_changed(x, state, custom_functions))]},
                                    "BUFFER_VALUE_EXPRESSION":{"TYPE":"LineEdit", "WIDGET":self.lineEdit_filtering_buffer_value_expression, "SIGNALS":[("textEdited", lambda state, x='buffer_value_expression', custom_functions={"ON_CHANGE": lambda x: self.filtering_buffer_expression_edited()}: self.layer_property_changed(x, state, custom_functions)), ("textChanged", lambda state, x='buffer_value_expression', custom_functions={"ON_CHANGE": lambda x: self.filtering_buffer_expression_edited()}: self.layer_property_changed(x, state, custom_functions))]},
                                    "BUFFER_TYPE":{"TYPE":"ComboBox", "WIDGET":self.comboBox_filtering_buffer_type, "SIGNALS":[("currentTextChanged", lambda state, x='buffer_type': self.layer_property_changed(x, state))]},
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
        print(f"FilterMate: === WIDGETS INITIALIZED === PROJECT_LAYERS count at init: {len(self.PROJECT_LAYERS)}")
        logger.info(f"=== WIDGETS INITIALIZED === PROJECT_LAYERS count at init: {len(self.PROJECT_LAYERS)}")
        
        # CRITICAL: If layers were updated before widgets_initialized, refresh UI now
        if self._pending_layers_update:
            print(f"FilterMate: Pending layers update detected - refreshing UI with {len(self.PROJECT_LAYERS)} layers")
            logger.info(f"Pending layers update detected - refreshing UI with {len(self.PROJECT_LAYERS)} layers")
            self._pending_layers_update = False
            # Use QTimer to ensure the event loop has processed widgets_initialized
            from qgis.PyQt.QtCore import QTimer
            QTimer.singleShot(50, lambda: self.get_project_layers_from_app(self.PROJECT_LAYERS, self.PROJECT))

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


    def apply_pending_config_changes(self):
        """Apply all pending configuration changes when OK button is clicked"""
        
        if not self.config_changes_pending or not self.pending_config_changes:
            logger.info("No pending configuration changes to apply")
            return
        
        logger.info(f"Applying {len(self.pending_config_changes)} pending configuration change(s)")
        
        changes_summary = []
        
        for change in self.pending_config_changes:
            items_keys_values_path = change['path']
            index = change['index']
            item = change['item']
            
            # Handle ICONS changes
            if 'ICONS' in items_keys_values_path:
                self.set_widget_icon(items_keys_values_path)
                changes_summary.append(f"Icon: {' → '.join(items_keys_values_path[-2:])}")
            
            # Handle ACTIVE_THEME changes - apply new theme
            if 'ACTIVE_THEME' in items_keys_values_path:
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
            
            # Handle UI_PROFILE changes - apply new dimensions immediately
            if 'UI_PROFILE' in items_keys_values_path:
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
                            
                            # Show confirmation message to user
                            profile_display = UIConfig.get_profile_name().upper()
                            iface.messageBar().pushSuccess(
                                "FilterMate",
                                f"UI profile changed to {profile_display} mode. Dimensions updated.",
                                3
                            )
                        else:
                            logger.warning("UI_CONFIG not available - cannot apply profile changes")
                            
                except Exception as e:
                    logger.error(f"Error applying UI_PROFILE change: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            # Handle STYLES_TO_EXPORT changes - update export style combobox
            if 'STYLES_TO_EXPORT' in items_keys_values_path:
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
                    
                    if new_style_value and 'STYLE_TO_EXPORT' in self.widgets.get('EXPORTING', {}):
                        logger.info(f"STYLES_TO_EXPORT changed to: {new_style_value}")
                        
                        # Update the combobox selection
                        style_combo = self.widgets["EXPORTING"]["STYLE_TO_EXPORT"]["WIDGET"]
                        index_to_set = style_combo.findText(new_style_value)
                        if index_to_set >= 0:
                            style_combo.setCurrentIndex(index_to_set)
                            logger.info(f"Export style updated to: {new_style_value}")
                            
                            iface.messageBar().pushInfo(
                                "FilterMate",
                                f"Export style changed to {new_style_value}",
                                3
                            )
                        
                except Exception as e:
                    logger.error(f"Error applying STYLES_TO_EXPORT change: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            # Handle DATATYPE_TO_EXPORT changes - update export format combobox
            if 'DATATYPE_TO_EXPORT' in items_keys_values_path:
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
                            
                            iface.messageBar().pushInfo(
                                "FilterMate",
                                f"Export format changed to {new_format_value}",
                                3
                            )
                        
                except Exception as e:
                    logger.error(f"Error applying DATATYPE_TO_EXPORT change: {e}")
                    import traceback
                    logger.error(traceback.format_exc())

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
            with open(self.plugin_dir + '/config/config.json', 'r') as infile:
                self.CONFIG_DATA = json.load(infile)
            
            # Recreate model with original data
            self.config_model = JsonModel(
                data=self.CONFIG_DATA, 
                editable_keys=True, 
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
            
            iface.messageBar().pushInfo(
                "FilterMate",
                "Configuration changes cancelled and reverted",
                3
            )
            logger.info("Configuration changes cancelled successfully")
            
        except Exception as e:
            logger.error(f"Error cancelling configuration changes: {e}")
            import traceback
            logger.error(traceback.format_exc())
            iface.messageBar().pushCritical(
                "FilterMate",
                f"Error cancelling changes: {str(e)}",
                5
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
                self.config_model = JsonModel(data=self.CONFIG_DATA, editable_keys=True, editable_values=True, plugin_dir=self.plugin_dir)
                
                # Update view model - safe to call here since view already exists
                if hasattr(self, 'config_view') and self.config_view is not None:
                    self.config_view.setModel(self.config_model)
                    self.config_view.model = self.config_model
                
                # Save to file
                json_object = json.dumps(self.CONFIG_DATA, indent=4)
                with open(self.plugin_dir + '/config/config.json', 'w') as outfile:
                    outfile.write(json_object)
            except Exception as e:
                logger.error(f"Error reloading configuration model: {e}")
                import traceback
                logger.error(traceback.format_exc())


    def save_configuration_model(self):

        if self.widgets_initialized is True:

            self.CONFIG_DATA = self.config_model.serialize()
            json_object = json.dumps(self.CONFIG_DATA, indent=4)

            with open(self.plugin_dir + '/config/config.json', 'w') as outfile:
                outfile.write(json_object)


    def manage_configuration_model(self):
        """Manage the qtreeview model configuration"""

        try:
            # Create model with data
            self.config_model = JsonModel(data=self.CONFIG_DATA, editable_keys=True, editable_values=True, plugin_dir=self.plugin_dir)

            # Create view with model - setModel() is called in JsonView.__init__()
            self.config_view = JsonView(self.config_model, self.plugin_dir)
            
            # Insert into layout
            self.CONFIGURATION.layout().insertWidget(0, self.config_view)

            # Note: setModel() is already called in JsonView constructor - do NOT call again
            # Calling setModel() after insertion can cause Qt crashes

            self.config_view.setAnimated(True)
            self.config_view.setEnabled(True)
            self.config_view.show()
            
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

                icon = QtGui.QIcon(file_path)
                self.widgets[config_widget_path[4]][config_widget_path[5]]["WIDGET"].setIcon(icon)


    def switch_widget_icon(self, widget_path, state):
        if state is True:
            icon = QtGui.QIcon(self.widgets[widget_path[0].upper()][widget_path[1].upper()]["ICON_ON_TRUE"])
        else:
            icon = QtGui.QIcon(self.widgets[widget_path[0].upper()][widget_path[1].upper()]["ICON_ON_FALSE"])
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

            if layer == None:
                layer = self.current_layer
            else:
                assert isinstance(layer, QgsVectorLayer)
            try:    
                self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].clear()
                
                # CRITICAL: Check if layer exists in PROJECT_LAYERS before accessing
                if layer.id() not in self.PROJECT_LAYERS:
                    print(f"FilterMate: Layer {layer.name()} not in PROJECT_LAYERS yet, skipping")
                    return
                
                layer_props = self.PROJECT_LAYERS[layer.id()]

                if layer_props["filtering"]["has_layers_to_filter"] == True:
                    i = 0
                    
                    for key in self.PROJECT_LAYERS:
                        # Verify required keys exist in layer info
                        if "infos" not in self.PROJECT_LAYERS[key]:
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

                        # Only add vector layers (skip raster layers)
                        layer_obj = self.PROJECT.mapLayer(layer_id)
                        if key != layer.id() and layer_obj and isinstance(layer_obj, QgsVectorLayer):
                            self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].addItem(layer_icon, layer_name + ' [%s]' % (layer_crs_authid), key)
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
                    for key in self.PROJECT_LAYERS:
                        # Verify required keys exist in layer info
                        if "infos" not in self.PROJECT_LAYERS[key]:
                            continue
                        
                        layer_info = self.PROJECT_LAYERS[key]["infos"]
                        required_keys = ["layer_id", "layer_name", "layer_crs_authid", "layer_geometry_type"]
                        if any(k not in layer_info or layer_info[k] is None for k in required_keys):
                            continue
                        
                        layer_id = layer_info["layer_id"]
                        layer_name = layer_info["layer_name"]
                        layer_crs_authid = layer_info["layer_crs_authid"]
                        layer_icon = self.icon_per_geometry_type(layer_info["layer_geometry_type"])
                        
                        # Only add vector layers (skip raster layers)
                        layer_obj = self.PROJECT.mapLayer(layer_id)
                        if key != layer.id() and layer_obj and isinstance(layer_obj, QgsVectorLayer):
                            self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].addItem(layer_icon, layer_name + ' [%s]' % (layer_crs_authid), key)
                            item = self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].model().item(i)
                            item.setCheckState(Qt.Unchecked)
                            i += 1    
            
            except Exception as e:
                # Log the error without storing in self.exception
                print(f"FilterMate: Error in filtering_populate_layers_chekableCombobox: {type(e).__name__}: {e}")
                
                # Check if layer is still valid (not deleted)
                try:
                    if layer is not None and not sip.isdeleted(layer):
                        # Pass explicitly typed empty list for properties parameter
                        empty_properties = []
                        self.resetLayerVariableOnErrorEvent(layer, empty_properties)
                    else:
                        # Layer has been deleted
                        print(f"FilterMate: Cannot reset layer variable - layer has been deleted")
                except RuntimeError as runtime_err:
                    # Layer C++ object is deleted
                    print(f"FilterMate: Cannot reset layer variable - layer C++ object deleted: {runtime_err}")

    def exporting_populate_combobox(self):

        if self.widgets_initialized is True and self.has_loaded_layers is True:

            layers_to_export = []
            datatype_to_export = ''

            if self.project_props['EXPORTING']['HAS_LAYERS_TO_EXPORT'] is True:
                layers_to_export = self.project_props['EXPORTING']['LAYERS_TO_EXPORT']
            
            if self.project_props['EXPORTING']['HAS_DATATYPE_TO_EXPORT'] is True:
                datatype_to_export = self.project_props['EXPORTING']['DATATYPE_TO_EXPORT']


            self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].clear()
            item_index = 0  # Track actual item position in widget
            for key in self.PROJECT_LAYERS:
                # Verify required keys exist in layer info
                if "infos" not in self.PROJECT_LAYERS[key]:
                    continue
                
                layer_info = self.PROJECT_LAYERS[key]["infos"]
                required_keys = ["layer_id", "layer_name", "layer_crs_authid", "layer_geometry_type"]
                if any(k not in layer_info or layer_info[k] is None for k in required_keys):
                    continue
                
                layer_id = layer_info["layer_id"]
                layer_name = layer_info["layer_name"]
                layer_crs_authid = layer_info["layer_crs_authid"]
                layer_icon = self.icon_per_geometry_type(layer_info["layer_geometry_type"])
                
                # Only add vector layers (skip raster layers)
                layer_obj = self.PROJECT.mapLayer(layer_id)
                if layer_obj and isinstance(layer_obj, QgsVectorLayer):
                    layer_name = layer_name + ' [%s]' % (layer_crs_authid)
                    self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].addItem(layer_icon, layer_name, key)
                    item = self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].model().item(item_index)
                    if key in layers_to_export:
                        item.setCheckState(Qt.Checked)
                    else:
                        item.setCheckState(Qt.Unchecked)
                    item_index += 1  # Increment only when item is actually added
            
            ogr_driver_list = [ogr.GetDriver(i).GetDescription() for i in range(ogr.GetDriverCount())]
            ogr_driver_list.sort()
            self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"].clear()
            self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"].addItems(ogr_driver_list)
        
            if datatype_to_export != '':
                self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"].setCurrentIndex(self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"].findText(datatype_to_export))
            else:
                self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"].setCurrentIndex(self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"].findText('GPKG'))


    def manage_ui_style(self):
        """
        Load and apply plugin stylesheet using StyleLoader with auto-detection.
        
        This method:
        1. Auto-detects UI profile from screen resolution (if UI_PROFILE="auto")
        2. Auto-detects color theme from QGIS (if ACTIVE_THEME="auto")
        3. Uses StyleLoader to load stylesheet from resources/styles/default.qss
        4. Applies config.json colors dynamically via StyleLoader
        5. Sets widget-specific properties (sizes, fonts, icons, cursors)
        
        The StyleLoader handles:
        - Loading QSS file with error handling
        - Replacing color placeholders with config values
        - Replacing dimension placeholders with UI profile values
        - Caching for performance
        - Theme management (auto-detects from config)
        
        Benefits:
        - Centralized style management
        - Automatic adaptation to screen size and QGIS theme
        - Proper error handling and fallbacks
        - Easy theme customization via config.json
        - Testable and maintainable
        """
        # Auto-configure UI profile and theme based on environment
        if UI_CONFIG_AVAILABLE:
            auto_config_result = ui_utils.auto_configure_from_environment(self.CONFIG_DATA)
            
            # Log auto-configuration results
            logger.info(f"FilterMate auto-configuration completed:")
            logger.info(f"  - Profile: {auto_config_result.get('profile_detected')} "
                       f"({auto_config_result.get('profile_source')})")
            logger.info(f"  - Theme: {auto_config_result.get('theme_detected')} "
                       f"({auto_config_result.get('theme_source')})")
            logger.info(f"  - Resolution: {auto_config_result.get('screen_resolution')}")
        
        # Apply stylesheet using StyleLoader with config colors
        # Theme is automatically detected from config.json ACTIVE_THEME or QGIS
        StyleLoader.set_theme_from_config(
            self.dockWidgetContents, 
            self.CONFIG_DATA
        )
        
        # Configure push buttons, comboboxes, and other widgets
        pushButton_config_path = ['APP', 'DOCKWIDGET', 'PushButton']
        pushButton_config = self.CONFIG_DATA[pushButton_config_path[0]][pushButton_config_path[1]][pushButton_config_path[2]]
        
        # Get icon sizes from config
        icons_sizes = {
            "ACTION": pushButton_config.get("ICONS_SIZES", {}).get("ACTION", 20),
            "OTHERS": pushButton_config.get("ICONS_SIZES", {}).get("OTHERS", 20),
        }
        
        # Set font for widgets
        font = QFont("Segoe UI Semibold", 8)
        font.setBold(True)
        
        # Apply widget-specific configurations
        for widget_group in self.widgets:
            for widget_name in self.widgets[widget_group]:
                widget_type = self.widgets[widget_group][widget_name]["TYPE"]
                widget_obj = self.widgets[widget_group][widget_name]["WIDGET"]
                
                # Skip certain widget types
                if widget_type in ("JsonTreeView", "LayerTreeView", "JsonModel", "ToolBox"):
                    continue
                
                # Configure push buttons
                if widget_type == "PushButton":
                    self.set_widget_icon(pushButton_config_path + ["ICONS", widget_group, widget_name])
                    widget_obj.setCursor(Qt.PointingHandCursor)
                    
                    # Determine icon size from config (will be overridden by UIConfig if available)
                    icon_size = icons_sizes.get(widget_group, icons_sizes["OTHERS"])
                    
                    # Apply dynamic dimensions based on button type
                    if UI_CONFIG_AVAILABLE:
                        # Determine button type for dynamic sizing
                        if widget_group == "ACTION":
                            # Main action buttons (filter, export, etc.)
                            button_height = UIConfig.get_button_height("action_button")
                            button_icon_size = UIConfig.get_icon_size("action_button")
                        elif widget_group in ["EXPLORING", "FILTERING", "EXPORTING"]:
                            # Tool/sidebar buttons
                            button_height = UIConfig.get_button_height("tool_button")
                            button_icon_size = UIConfig.get_icon_size("tool_button")
                        else:
                            # Default buttons
                            button_height = UIConfig.get_button_height("button")
                            button_icon_size = UIConfig.get_icon_size("button")
                        
                        widget_obj.setMinimumHeight(button_height)
                        widget_obj.setMaximumHeight(button_height)
                        widget_obj.setMinimumWidth(button_height)
                        widget_obj.setMaximumWidth(button_height)
                        widget_obj.setIconSize(QtCore.QSize(button_icon_size, button_icon_size))
                        
                        # CRITICAL: Force Fixed size policy for sidebar buttons to prevent stretching
                        if widget_group in ["EXPLORING", "FILTERING", "EXPORTING"]:
                            widget_obj.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
                    else:
                        # Fallback: use default normal profile values if UIConfig not available
                        widget_obj.setIconSize(QtCore.QSize(icon_size, icon_size))
                        
                        # Set button size based on group using normal profile defaults
                        if widget_group in ["EXPLORING", "FILTERING", "EXPORTING"]:
                            # Sidebar tool buttons - use normal profile default (36px)
                            fallback_size = 36
                            widget_obj.setMinimumHeight(fallback_size)
                            widget_obj.setMaximumHeight(fallback_size)
                            widget_obj.setMinimumWidth(fallback_size)
                            widget_obj.setMaximumWidth(fallback_size)
                        else:
                            # Action buttons - double icon size
                            widget_obj.setMinimumHeight(icon_size * 2)
                            widget_obj.setMaximumHeight(icon_size * 2)
                            widget_obj.setMinimumWidth(icon_size * 2)
                            widget_obj.setMaximumWidth(icon_size * 2)
                    
                    widget_obj.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
                    widget_obj.setFont(font)
                
                # Configure comboboxes and field widgets
                elif any(keyword in widget_type for keyword in ["ComboBox", "QgsFieldExpressionWidget", "QgsProjectionSelectionWidget"]):
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
        
        # Set sizes for key widgets - accommodate buttons with padding
        # Use dynamic dimensions if available
        if UI_CONFIG_AVAILABLE:
            # Get widget_keys width directly from config
            widget_keys_width = UIConfig.get_config('widget_keys', 'max_width') or 56
            
            for widget in [self.widget_exploring_keys, self.widget_filtering_keys, self.widget_exporting_keys]:
                widget.setMinimumWidth(widget_keys_width)
                widget.setMaximumWidth(widget_keys_width)
                widget.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)
            
            # Set frame actions size (convert to int to avoid float)
            action_button_height = UIConfig.get_button_height("action_button")
            frame_height = int(action_button_height * 1.5)
            self.frame_actions.setMinimumHeight(frame_height)
            self.frame_actions.setMaximumHeight(frame_height)
        else:
            # Fallback to hardcoded values
            icon_size = icons_sizes["OTHERS"]
            for widget in [self.widget_exploring_keys, self.widget_filtering_keys, self.widget_exporting_keys]:
                widget.setMinimumWidth(80)
                widget.setMaximumWidth(80)
                widget.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)
            
            # Set frame actions size
            icon_size = icons_sizes["ACTION"]
            self.frame_actions.setMinimumHeight(icon_size * 3)
            self.frame_actions.setMaximumHeight(icon_size * 3)
        
        logger.debug("UI stylesheet loaded and applied successfully")


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
        """
        logger.debug(f"set_widgets_enabled_state({state}) called")
        widget_count = 0
        for widget_group in self.widgets:
            for widget_name in self.widgets[widget_group]:
                if self.widgets[widget_group][widget_name]["TYPE"] not in ("JsonTreeView","LayerTreeView","JsonModel","ToolBox"):
                    if self.widgets[widget_group][widget_name]["TYPE"] in ("PushButton", "GroupBox"):
                        if self.widgets[widget_group][widget_name]["WIDGET"].isCheckable():
                            if state is False:
                                self.widgets[widget_group][widget_name]["WIDGET"].setChecked(state)
                                if self.widgets[widget_group][widget_name]["TYPE"] == "GroupBox":
                                    self.widgets[widget_group][widget_name]["WIDGET"].setCollapsed(True)
                    self.widgets[widget_group][widget_name]["WIDGET"].setEnabled(state)
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
        Processes Qt event queue between disconnections to avoid overflow.
        
        Notes:
            - CRITICAL FIX: Prevents crashes during task execution
            - Processes events between disconnects to avoid Qt queue overflow
            - Handles already-deleted widgets gracefully
            - Called before long-running tasks or layer removal
            - Essential for plugin stability
            - Pairs with connect_widgets_signals()
            
        Raises:
            No exceptions propagated - all errors caught and logged
        """
        # CRITICAL FIX: Protect against Qt access violations during task execution
        from qgis.PyQt.QtCore import QCoreApplication
        
        for widget_group in self.widgets:
            if widget_group != 'QGIS':
                for widget in self.widgets[widget_group]:
                    try:
                        # Process events to avoid Qt queue overflow during signal disconnect
                        QCoreApplication.processEvents()
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
        
        Configuration steps:
        1. Initialize coordinate reference system
        2. Enable expression support for buffer widget
        3. Set default buffer value to 0.0
        4. Configure projection widget with project CRS
        5. Enable/disable widgets based on layer availability
        6. Populate predicate and buffer type comboboxes
        7. Connect widget signals if layers present
        
        Notes:
            - Called from __init__ after setupUi() and setupUiCustom()
            - Widget state depends on has_loaded_layers flag
            - Signals only connected if layers are available
            - Central initialization point for widget behavior
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
            except (AttributeError, RuntimeError, TypeError, SignalStateChangeError):
                pass
        
        self.filtering_populate_predicates_chekableCombobox()
        self.filtering_populate_buffer_type_combobox()

        # Note: DOCK widget signals (SINGLE_SELECTION, MULTIPLE_SELECTION, CUSTOM_SELECTION, TOOLS)
        # are already connected via connect_widgets_signals() above.
        # No need for manual connection to avoid double signal firing.
        
        # Connect configuration model signal to detect changes in JSON tree view
        self.widgets["DOCK"]["CONFIGURATION_MODEL"]["WIDGET"].itemChanged.connect(self.data_changed_configuration_model)
        # self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].filterExpressionChanged()
        
        # self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].contextMenuEvent
        # self.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].contextMenuEvent

        if self.init_layer is not None and isinstance(self.init_layer, QgsVectorLayer):
            self.manage_output_name()
            self.manageSignal(["EXPORTING","LAYERS_TO_EXPORT"], 'disconnect')
            self.exporting_populate_combobox()
            self.manageSignal(["EXPORTING","LAYERS_TO_EXPORT"], 'connect', 'checkedItemsChanged')
            self.set_exporting_properties()
            self.exploring_groupbox_init()
            self.current_layer_changed(self.init_layer)
            self.filtering_auto_current_layer_changed()

            
    def select_tabTools_index(self):
        
        if self.widgets_initialized is True:

            self.tabTools_current_index = self.widgets["DOCK"]["TOOLS"]["WIDGET"].currentIndex()
            if self.tabTools_current_index == 1:
                self.widgets["ACTION"]["EXPORT"]["WIDGET"].setEnabled(True)
            else:
                self.widgets["ACTION"]["EXPORT"]["WIDGET"].setEnabled(False)

            self.set_exporting_properties()


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

    def exploring_groupbox_changed(self, groupbox):
        
        if self.widgets_initialized is True:

            if groupbox == "single_selection":
    
  

                self.current_exploring_groupbox = "single_selection"
                
                # Save to PROJECT_LAYERS for persistence
                if self.current_layer is not None and self.current_layer.id() in self.PROJECT_LAYERS:
                    self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["current_exploring_groupbox"] = "single_selection"

                self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].setChecked(True)
                self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].setCollapsed(False)

                self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].setChecked(False)
                self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].setCollapsed(True)

                self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].setChecked(False)
                self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].setCollapsed(True)
                

                if self.current_layer is not None:
                    # CRITICAL: Use safe getter to validate layer exists in PROJECT_LAYERS
                    layer_props = self._safe_get_layer_props(self.current_layer)
                    if layer_props is None:
                        logger.warning(f"Cannot initialize single_selection exploring - layer not in PROJECT_LAYERS. Skipping.")
                        return
                    
                    # CRITICAL: Disconnect signals BEFORE updating widgets to prevent unwanted triggers
                    self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
                    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')
                    self.manageSignal(["EXPLORING","SINGLE_SELECTION_EXPRESSION"], 'disconnect')
                    
                    self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setEnabled(True)
                    self.widgets["EXPLORING"]["SINGLE_SELECTION_EXPRESSION"]["WIDGET"].setEnabled(True)
                    
                    # CRITICAL FIX: Update SINGLE_SELECTION_FEATURES widget to use current layer
                    # This ensures the QgsFeaturePickerWidget displays features from the correct layer
                    self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setLayer(self.current_layer)
                    self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setDisplayExpression(layer_props["exploring"]["single_selection_expression"])
                    
                    # Ensure mFieldExpressionWidget is linked to current layer
                    self.widgets["EXPLORING"]["SINGLE_SELECTION_EXPRESSION"]["WIDGET"].setLayer(self.current_layer)
                    
                    # CRITICAL: Reconnect signals AFTER updating widgets
                    self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'connect', 'featureChanged')
                    self.manageSignal(["EXPLORING","SINGLE_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
                    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'filteringCheckedItemList')
                    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'updatingCheckedItemList')

                    # Trigger features update and link widgets
                    self.exploring_link_widgets()
                    self.exploring_features_changed(self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].feature())
                else:
                    self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
                    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')



            elif groupbox == "multiple_selection":

     
                    
                self.current_exploring_groupbox = "multiple_selection"
                
                # Save to PROJECT_LAYERS for persistence
                if self.current_layer is not None and self.current_layer.id() in self.PROJECT_LAYERS:
                    self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["current_exploring_groupbox"] = "multiple_selection"



                self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].setChecked(True)
                self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].setCollapsed(False)

                self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].setChecked(False)
                self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].setCollapsed(True)

                self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].setChecked(False)
                self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].setCollapsed(True)



                if self.current_layer is not None:
                    # CRITICAL: Disconnect ALL signals BEFORE updating widgets
                    self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
                    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')
                    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_EXPRESSION"], 'disconnect')

                    self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setEnabled(True)
                    self.widgets["EXPLORING"]["MULTIPLE_SELECTION_EXPRESSION"]["WIDGET"].setEnabled(True)
                    # Ensure mFieldExpressionWidget is linked to current layer
                    self.widgets["EXPLORING"]["MULTIPLE_SELECTION_EXPRESSION"]["WIDGET"].setLayer(self.current_layer)

                    layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
                    self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setLayer(self.current_layer, layer_props)
                    
                    # CRITICAL: Reconnect signals AFTER updating widgets
                    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect')
                    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')

                    # Trigger features update and link widgets
                    self.exploring_link_widgets()
                    self.exploring_features_changed(self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].currentSelectedFeatures(), True)
                else:
                    self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
                    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')

            elif groupbox == "custom_selection":


                    
                self.current_exploring_groupbox = "custom_selection"
                
                # Save to PROJECT_LAYERS for persistence
                if self.current_layer is not None and self.current_layer.id() in self.PROJECT_LAYERS:
                    self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["current_exploring_groupbox"] = "custom_selection"
                
                self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].setChecked(True)
                self.widgets["DOCK"]["CUSTOM_SELECTION"]["WIDGET"].setCollapsed(False)

                self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].setChecked(False)
                self.widgets["DOCK"]["MULTIPLE_SELECTION"]["WIDGET"].setCollapsed(True)

                self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].setChecked(False)
                self.widgets["DOCK"]["SINGLE_SELECTION"]["WIDGET"].setCollapsed(True)



                if self.current_layer is not None:
                    # CRITICAL: Disconnect ALL signals BEFORE updating widgets
                    self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
                    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')
                    self.manageSignal(["EXPLORING","CUSTOM_SELECTION_EXPRESSION"], 'disconnect')

                    self.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"].setEnabled(True)
                    # Ensure mFieldExpressionWidget is linked to current layer
                    self.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"].setLayer(self.current_layer)
                    
                    # CRITICAL: Reconnect signals AFTER updating widgets
                    self.manageSignal(["EXPLORING","CUSTOM_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
                    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'filteringCheckedItemList')
                    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'updatingCheckedItemList')
                    
                    # Trigger link and custom selection
                    self.exploring_link_widgets()
                    self.exploring_custom_selection()
                else:
                    self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
                    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')


    def exploring_identify_clicked(self):

        features = []
        expression = None

        if self.widgets_initialized is True and self.current_layer is not None:

            features, expression = self.get_current_features()
            
            if len(features) == 0:
                return
            else:
                self.iface.mapCanvas().flashFeatureIds(self.current_layer, [feature.id() for feature in features], startColor=QColor(235, 49, 42, 255), endColor=QColor(237, 97, 62, 25), flashes=6, duration=400)


    def get_current_features(self):

        if self.widgets_initialized is True and self.current_layer is not None:

            features = []    
            expression = ''

            if self.current_exploring_groupbox == "single_selection":
                input = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].feature()
                features, expression = self.get_exploring_features(input, True)

            elif self.current_exploring_groupbox == "multiple_selection":
                input = self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].checkedItems()
                features, expression = self.get_exploring_features(input, True)

            elif self.current_exploring_groupbox == "custom_selection":
                expression = self.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"].expression()
                
                # Save expression to layer_props before calling exploring_custom_selection
                if self.current_layer.id() in self.PROJECT_LAYERS:
                    self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["custom_selection_expression"] = expression
                
                # Process expression (whether field or complex expression)
                features, expression = self.exploring_custom_selection()


                
            return features, expression
        
        return [], ''
        

    def exploring_zoom_clicked(self, features=[]):

        if self.widgets_initialized is True and self.current_layer is not None:

            if not features or len(features) == 0:   
                features, expression = self.get_current_features()
            

            self.zooming_to_features(features)


    def zooming_to_features(self, features):
        
        if self.widgets_initialized is True and self.current_layer is not None:

            # Safety check: ensure features is a list
            if not features or not isinstance(features, list) or len(features) == 0:        
                extent = self.current_layer.extent()
                self.iface.mapCanvas().zoomToFeatureExtent(extent) 

            else: 
                features_with_geometry = [feature for feature in features if feature.hasGeometry()]

                if len(features_with_geometry) == 1:
                    feature = features_with_geometry[0]
                    # CRITICAL: Create a copy to avoid modifying the original geometry
                    geom = QgsGeometry(feature.geometry())
                    
                    # Get CRS information
                    layer_crs = self.current_layer.crs()
                    canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
                    is_geographic = layer_crs.isGeographic()
                    
                    # CRITICAL: For geographic coordinates, switch to EPSG:3857 for metric calculations
                    # This ensures accurate buffer distances in meters instead of imprecise degrees
                    if is_geographic:
                        # Transform to Web Mercator (EPSG:3857) for metric-based buffer
                        work_crs = QgsCoordinateReferenceSystem("EPSG:3857")
                        to_metric = QgsCoordinateTransform(layer_crs, work_crs, QgsProject.instance())
                        geom.transform(to_metric)
                        logger.debug(f"FilterMate: Switched from {layer_crs.authid()} to EPSG:3857 for metric buffer")
                    else:
                        # Already in projected coordinates, use layer CRS
                        work_crs = layer_crs
                    
                    if str(feature.geometry().type()) == 'GeometryType.Point':
                        # Apply buffer in meters (work_crs is now always metric)
                        buffer_distance = 50  # 50 meters for all points
                        box = geom.buffer(buffer_distance, 5).boundingBox()
                    else:
                        # For polygons/lines, add small buffer for better visibility
                        box = geom.boundingBox()
                        box.grow(10)  # 10 meters expansion in all cases
                    
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
        Si is_tracking est activé, zoom sur les features sélectionnées.
        
        Args:
            selected: List of added feature IDs
            deselected: List of removed feature IDs  
            clearAndSelect: Boolean indicating if selection was cleared
        """
        if self.widgets_initialized is True and self.current_layer is not None:
            layer_props = self.PROJECT_LAYERS.get(self.current_layer.id())
            
            if layer_props and layer_props["exploring"]["is_tracking"] is True:
                # Get currently selected features
                selected_features = self.current_layer.selectedFeatures()
                
                if len(selected_features) > 0:
                    self.zooming_to_features(selected_features)


    def exploring_source_params_changed(self, expression=None):

        if self.widgets_initialized is True and self.current_layer is not None:


            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]


            if self.current_exploring_groupbox == "single_selection":

                expression = self.widgets["EXPLORING"]["SINGLE_SELECTION_EXPRESSION"]["WIDGET"].expression()
                if expression is not None and layer_props["exploring"]["single_selection_expression"] != expression:
                    self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["single_selection_expression"] = expression
                    self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setDisplayExpression(expression)
                    # CRITICAL: Update linked widgets when single selection expression changes
                    self.exploring_link_widgets()

            elif self.current_exploring_groupbox == "multiple_selection":

                expression = self.widgets["EXPLORING"]["MULTIPLE_SELECTION_EXPRESSION"]["WIDGET"].expression()
                if expression is not None and layer_props["exploring"]["multiple_selection_expression"] != expression:
                    self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["multiple_selection_expression"] = expression

                layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
                self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setLayer(self.current_layer, layer_props)
                self.exploring_link_widgets()

            elif self.current_exploring_groupbox == "custom_selection":

                expression = self.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"].expression()
                if expression is not None and layer_props["exploring"]["custom_selection_expression"] != expression:
                    self.PROJECT_LAYERS[self.current_layer.id()]["exploring"]["custom_selection_expression"] = expression
                    self.exploring_link_widgets(expression)

            self.get_current_features()

 


    def exploring_custom_selection(self):

        if self.widgets_initialized is True and self.current_layer is not None:

            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
            expression = layer_props["exploring"]["custom_selection_expression"]
            features = []
            
            # Always get features for custom expression (whether field or complex)
            features = self.exploring_features_changed([], False, expression)

            return features, expression
        
        return [], ''
    

    def exploring_deselect_features(self):

        if self.widgets_initialized is True and self.current_layer is not None:

            if self.current_layer == None:
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
            
            if self.current_layer == None:
                return
            
            # Get features from the active groupbox
            features, expression = self.get_current_features()
            
            # Select features on the layer
            if len(features) > 0:
                self.current_layer.removeSelection()
                self.current_layer.select([feature.id() for feature in features])


    
    def exploring_features_changed(self, input=[], identify_by_primary_key_name=False, custom_expression=None):

        if self.widgets_initialized is True and self.current_layer is not None and isinstance(self.current_layer, QgsVectorLayer):
            
            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
            features, expression = self.get_exploring_features(input, identify_by_primary_key_name, custom_expression)

     
            self.exploring_link_widgets()

            self.current_layer.removeSelection()

            if len(features) == 0:
                return []
        
            if layer_props["exploring"]["is_selecting"] == True:
                self.current_layer.removeSelection()
                self.current_layer.select([feature.id() for feature in features])

            if layer_props["exploring"]["is_tracking"] == True:
                self.zooming_to_features(features)  

            return features
        
        return []


    def get_exploring_features(self, input, identify_by_primary_key_name=False, custom_expression=None):

        if self.widgets_initialized is True and self.current_layer is not None:

            if self.current_layer == None:
                return [], None
            
            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
            features = []
            expression = None

            if isinstance(input, QgsFeature):
                if identify_by_primary_key_name is True:
                    pk_name = layer_props["infos"]["primary_key_name"]
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
                        except (AttributeError, IndexError, KeyError):
                            pass
                    
                    if pk_value is not None:
                        if layer_props["infos"]["primary_key_is_numeric"] is True: 
                            expression = pk_name + " = {}".format(pk_value)
                        else:
                            expression = pk_name + " = '{}'".format(pk_value)
                    else:
                        # If we can't get the primary key, use the feature as-is
                        features = [input]
                        print(f"FilterMate Warning: Could not access primary key '{pk_name}' in feature. Using feature directly.")
                else:
                    features = [input]

            elif isinstance(input, list):
                if len(input) == 0 and custom_expression == None:
                    return features, expression
                
                if identify_by_primary_key_name is True:
                    if layer_props["infos"]["primary_key_is_numeric"] is True:
                        input_ids = [str(feat[1]) for feat in input]  
                        expression = layer_props["infos"]["primary_key_name"] + " IN (" + ", ".join(input_ids) + ")"
                    else:
                        input_ids = [str(feat[1]) for feat in input]
                        expression = layer_props["infos"]["primary_key_name"] + " IN (\'" + "\', \'".join(input_ids) + "\')"
                
            if custom_expression is not None:
                    expression = custom_expression

            if QgsExpression(expression).isValid():

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
        
    
    def exploring_link_widgets(self, expression=None):

        if self.widgets_initialized is True and self.current_layer is not None:

            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
            custom_filter = None
            layer_features_source = self.current_layer.dataProvider().featureSource() 
            
            if layer_props["exploring"]["is_linking"] == True:
                   

                if QgsExpression(layer_props["exploring"]["custom_selection_expression"]).isValid() is True:
                    if QgsExpression(layer_props["exploring"]["custom_selection_expression"]).isField() is False:
                        custom_filter = layer_props["exploring"]["custom_selection_expression"]
                        self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setFilterExpression(custom_filter, layer_props)
                if expression is not None:
                    self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setFilterExpression(expression)
                elif self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].currentSelectedFeatures() != False:
                    features, expression = self.get_exploring_features(self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].currentSelectedFeatures(), True)
                    if len(features) > 0 and expression is not None:
                        self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setFilterExpression(expression)
                elif self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].currentVisibleFeatures() != False:
                    features, expression = self.get_exploring_features(self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].currentVisibleFeatures(), True)
                    if len(features) > 0 and expression is not None:
                        self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setFilterExpression(expression)
                elif custom_filter is not None:
                    self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setFilterExpression(custom_filter)
                
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
                self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setFilterExpression('')
                self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setFilterExpression('', layer_props)


    def get_layers_to_filter(self):

        if self.widgets_initialized is True and self.current_layer is not None:

            checked_list_data = []
            for i in range(self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].count()):
                if self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].itemCheckState(i) == Qt.Checked:
                    data = self.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"].itemData(i, Qt.UserRole)
                    if isinstance(data, str):
                        checked_list_data.append(data)
            return checked_list_data


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
        # Skip raster layers - FilterMate only handles vector layers
        if layer is not None and not isinstance(layer, QgsVectorLayer):
            return (False, None, None)
        
        # CRITICAL: Prevent recursive calls during layer update
        if self._updating_current_layer:
            logger.debug("Blocking recursive call to current_layer_changed")
            return (False, None, None)
        
        if not self.widgets_initialized:
            return (False, None, None)
        
        # Disconnect selectionChanged signal from previous layer
        if self.current_layer is not None and self.current_layer_selection_connection is not None:
            try:
                self.current_layer.selectionChanged.disconnect(self.on_layer_selection_changed)
                self.current_layer_selection_connection = None
            except (TypeError, RuntimeError):
                pass
        
        if layer is None:
            return (False, None, None)
        
        self.current_layer = layer
        
        # Verify layer exists in PROJECT_LAYERS before proceeding
        if self.current_layer.id() not in self.PROJECT_LAYERS:
            return (False, None, None)
        
        layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
        return (True, layer, layer_props)
    
    def _reset_layer_expressions(self, layer_props):
        """
        Reset exploring expressions to primary_key_name of new layer when switching.
        
        This prevents KeyError when field names from previous layer don't exist in new layer.
        """
        primary_key = layer_props["infos"]["primary_key_name"]
        layer_fields = [field.name() for field in self.current_layer.fields()]
        
        # Reset single_selection_expression if invalid for current layer
        single_expr = layer_props["exploring"].get("single_selection_expression", "")
        if not single_expr or single_expr not in layer_fields:
            layer_props["exploring"]["single_selection_expression"] = primary_key
        
        # Reset multiple_selection_expression if invalid for current layer
        multiple_expr = layer_props["exploring"].get("multiple_selection_expression", "")
        if not multiple_expr or multiple_expr not in layer_fields:
            layer_props["exploring"]["multiple_selection_expression"] = primary_key
        
        # Reset custom_selection_expression if invalid for current layer
        custom_expr = layer_props["exploring"].get("custom_selection_expression", "")
        if not custom_expr or (QgsExpression(custom_expr).isField() and custom_expr.replace('"', '') not in layer_fields):
            layer_props["exploring"]["custom_selection_expression"] = primary_key
    
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
            ["FILTERING", "BUFFER_VALUE_EXPRESSION"],
            ["FILTERING","HAS_BUFFER_TYPE"],
            ["FILTERING","BUFFER_TYPE"]
        ]
        
        for widget_path in widgets_to_stop:
            self.manageSignal(widget_path, 'disconnect')
        
        if self.project_props["OPTIONS"]["LAYERS"]["LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"] is True:
            widget_path = ["QGIS","LAYER_TREE_VIEW"]
            self.manageSignal(widget_path, 'disconnect')
        
        return widgets_to_stop
    
    def _synchronize_layer_widgets(self, layer, layer_props):
        """
        Synchronize all widgets with the new current layer.
        
        Updates comboboxes, field expression widgets, and backend indicator.
        """
        # Always synchronize comboBox_filtering_current_layer with current_layer
        lastLayer = self.widgets["FILTERING"]["CURRENT_LAYER"]["WIDGET"].currentLayer()
        if lastLayer == None or lastLayer.id() != self.current_layer.id():
            self.manageSignal(["FILTERING","CURRENT_LAYER"], 'disconnect')
            self.widgets["FILTERING"]["CURRENT_LAYER"]["WIDGET"].setLayer(self.current_layer)
            self.manageSignal(["FILTERING","CURRENT_LAYER"], 'connect', 'layerChanged')
        
        # Update backend indicator
        if layer.id() in self.PROJECT_LAYERS:
            if 'layer_provider_type' in layer_props.get('infos', {}):
                self._update_backend_indicator(layer_props['infos']['layer_provider_type'])
        else:
            provider_type = layer.providerType()
            if provider_type == 'postgres':
                self._update_backend_indicator(PROVIDER_POSTGRES)
            elif provider_type == 'spatialite':
                self._update_backend_indicator(PROVIDER_SPATIALITE)
            elif provider_type == 'ogr':
                self._update_backend_indicator(PROVIDER_OGR)
            else:
                self._update_backend_indicator(provider_type)
        
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
                    widget_type = self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["TYPE"]
                    if widget_type == 'PushButton':
                        if all(key in self.widgets[property_tuple[0].upper()][property_tuple[1].upper()] for key in ["ICON_ON_TRUE", "ICON_ON_FALSE"]):
                            self.switch_widget_icon(property_tuple, layer_props[property_tuple[0]][property_tuple[1]])
                        if self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].isCheckable():
                            self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setChecked(layer_props[property_tuple[0]][property_tuple[1]])
                    elif widget_type == 'CheckableComboBox':
                        self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setCheckedItems(layer_props[property_tuple[0]][property_tuple[1]])
                    elif widget_type == 'CustomCheckableComboBox':
                        self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["CUSTOM_LOAD_FUNCTION"]
                    elif widget_type == 'ComboBox':
                        self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setCurrentIndex(self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].findText(layer_props[property_tuple[0]][property_tuple[1]]))
                    elif widget_type == 'QgsFieldExpressionWidget':
                        self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setLayer(self.current_layer)
                        self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setFilters(QgsFieldProxyModel.AllTypes)
                        self.widgets[property_tuple[0].upper()][property_tuple[1].upper()]["WIDGET"].setExpression(layer_props[property_tuple[0]][property_tuple[1]])
                    elif widget_type == 'QgsDoubleSpinBox':
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
    
    def _reload_exploration_widgets(self, layer_props):
        """
        Force reload of ALL exploration widgets with new layer data.
        
        This ensures all widgets are properly populated even if already initialized.
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
            
            # Single selection widget
            if "SINGLE_SELECTION_FEATURES" in self.widgets.get("EXPLORING", {}):
                self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setLayer(self.current_layer)
                self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setDisplayExpression(layer_props["exploring"]["single_selection_expression"])
                self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setFetchGeometry(True)
                self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setShowBrowserButtons(True)
            
            # Multiple selection widget
            if "MULTIPLE_SELECTION_FEATURES" in self.widgets.get("EXPLORING", {}):
                self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setLayer(self.current_layer, layer_props)
            
            # Field expression widgets - setLayer BEFORE setExpression
            if "SINGLE_SELECTION_EXPRESSION" in self.widgets.get("EXPLORING", {}):
                self.widgets["EXPLORING"]["SINGLE_SELECTION_EXPRESSION"]["WIDGET"].setLayer(self.current_layer)
                self.widgets["EXPLORING"]["SINGLE_SELECTION_EXPRESSION"]["WIDGET"].setExpression(layer_props["exploring"]["single_selection_expression"])
            
            if "MULTIPLE_SELECTION_EXPRESSION" in self.widgets.get("EXPLORING", {}):
                self.widgets["EXPLORING"]["MULTIPLE_SELECTION_EXPRESSION"]["WIDGET"].setLayer(self.current_layer)
                self.widgets["EXPLORING"]["MULTIPLE_SELECTION_EXPRESSION"]["WIDGET"].setExpression(layer_props["exploring"]["multiple_selection_expression"])
            
            if "CUSTOM_SELECTION_EXPRESSION" in self.widgets.get("EXPLORING", {}):
                self.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"].setLayer(self.current_layer)
                self.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"].setExpression(layer_props["exploring"]["custom_selection_expression"])
            
            # Reconnect signals AFTER all widgets are updated
            self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'connect', 'featureChanged')
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'updatingCheckedItemList')
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'filteringCheckedItemList')
            self.manageSignal(["EXPLORING","SINGLE_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
            self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
            self.manageSignal(["EXPLORING","CUSTOM_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
        except (AttributeError, KeyError, RuntimeError) as e:
            # Widget may not be ready yet or already destroyed
            pass
    
    def _reconnect_layer_signals(self, widgets_to_reconnect, layer_props):
        """
        Reconnect all layer-related widget signals after updates.
        
        Also restores exploring groupbox state and connects layer selection signal.
        """
        # Reconnect all disconnected signals
        for widget_path in widgets_to_reconnect:
            self.manageSignal(widget_path, 'connect')
        
        # Reconnect legend link if enabled
        if self.project_props["OPTIONS"]["LAYERS"]["LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"] is True:
            if self.iface.activeLayer() is not None and self.iface.activeLayer().id() != self.current_layer.id():
                self.widgets["QGIS"]["LAYER_TREE_VIEW"]["WIDGET"].setCurrentLayer(self.current_layer)
            widget_path = ["QGIS","LAYER_TREE_VIEW"]
            self.manageSignal(widget_path, 'connect')
        
        # Connect selectionChanged signal for current layer to enable tracking
        if self.current_layer is not None:
            try:
                self.current_layer.selectionChanged.connect(self.on_layer_selection_changed)
                self.current_layer_selection_connection = True
            except (TypeError, RuntimeError):
                self.current_layer_selection_connection = None
        
        # Restore exploring groupbox state from PROJECT_LAYERS
        if "current_exploring_groupbox" in layer_props.get("exploring", {}):
            saved_groupbox = layer_props["exploring"]["current_exploring_groupbox"]
            if saved_groupbox:
                self.current_exploring_groupbox = saved_groupbox
                self.exploring_groupbox_changed(saved_groupbox)
        elif self.current_exploring_groupbox:
            self.exploring_groupbox_changed(self.current_exploring_groupbox)
        else:
            self.current_exploring_groupbox = "single_selection"
            self.exploring_groupbox_changed("single_selection")


    def current_layer_changed(self, layer):
        """
        Handle current layer change event.
        
        Orchestrates layer change by validating, disconnecting signals, 
        synchronizing widgets, and reconnecting signals.
        """
        try:
            # Validate layer and prepare for change
            should_continue, validated_layer, layer_props = self._validate_and_prepare_layer(layer)
            if not should_continue:
                return
            
            # Set update lock to prevent recursive calls
            self._updating_current_layer = True
            
            # Reset expressions for new layer
            self._reset_layer_expressions(layer_props)
            
            # Disconnect all signals before updates
            widgets_to_reconnect = self._disconnect_layer_signals()
            
            # Synchronize all widgets with new layer
            self._synchronize_layer_widgets(validated_layer, layer_props)
            
            # Reload exploration widgets
            self._reload_exploration_widgets(layer_props)
            
            # Reconnect all signals and restore state
            self._reconnect_layer_signals(widgets_to_reconnect, layer_props)
            
        except (AttributeError, KeyError, RuntimeError) as e:
            # Widget initialization may not be complete
            logger.debug(f"Error in current_layer_changed: {e}")
        finally:
            # CRITICAL: Always release the lock, even if an error occurred
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


    def layer_property_changed(self, input_property, input_data=None, custom_functions={}):
        
        if self.widgets_initialized is True and self.current_layer is not None:


            if self.current_layer == None:
                return
            
            widgets_to_stop =   [
                        ["EXPLORING","SINGLE_SELECTION_FEATURES"],
                        ["EXPLORING","SINGLE_SELECTION_EXPRESSION"],
                        ["EXPLORING","MULTIPLE_SELECTION_FEATURES"],
                        ["EXPLORING","MULTIPLE_SELECTION_EXPRESSION"],
                        ["EXPLORING","CUSTOM_SELECTION_EXPRESSION"]
                    ]
        
            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'disconnect')

            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
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
            elif input_data is None:
                state = False
            

            for properties_tuples_key in self.layer_properties_tuples_dict:
                if input_property.find(properties_tuples_key) >= 0:
                    properties_group_key = properties_tuples_key
                    properties_tuples = self.layer_properties_tuples_dict[properties_tuples_key]
                    for i, property_tuple in enumerate(properties_tuples):
                        if property_tuple[1] == input_property:
                            property_path = property_tuple
                            index = i
                            break
                    break


            if properties_group_key == 'is':

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


            elif properties_group_key == 'selection_expression':
                
                if str(layer_props[property_path[0]][property_path[1]]) != input_data:
                    self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = input_data
                    flag_value_changed = True
                    if "ON_TRUE" in custom_functions:
                        custom_functions["ON_TRUE"](0)

            else:
                group_enabled_property = properties_tuples[0]
                group_state = self.widgets[group_enabled_property[0].upper()][group_enabled_property[1].upper()]["WIDGET"].isChecked()

                if group_state is False:
                    self.properties_group_state_reset_to_default(properties_tuples, properties_group_key, group_state)
                    flag_value_changed = True

                else:
                    self.properties_group_state_enabler(properties_tuples)
                    widget_type = self.widgets[property_path[0].upper()][property_path[1].upper()]["TYPE"]
                    if widget_type == 'PushButton':
                        if layer_props[property_path[0]][property_path[1]] is not input_data and input_data is True:
                            self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = input_data
                            flag_value_changed = True
                            if "ON_TRUE" in custom_functions:
                                custom_functions["ON_TRUE"](0)
                            
                            # When has_layers_to_filter is activated, refresh the layers list
                            if property_path[1] == 'has_layers_to_filter':
                                self.manageSignal(["FILTERING","LAYERS_TO_FILTER"], 'disconnect')
                                self.filtering_populate_layers_chekableCombobox()
                                self.manageSignal(["FILTERING","LAYERS_TO_FILTER"], 'connect', 'checkedItemsChanged')

                        elif layer_props[property_path[0]][property_path[1]] is not input_data and input_data is False:
                            self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = input_data
                            flag_value_changed = True
                            if "ON_FALSE" in custom_functions:
                                custom_functions["ON_FALSE"](0)

                    else:
                        self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]] = input_data
                        flag_value_changed = True
                        if "ON_TRUE" in custom_functions:
                            custom_functions["ON_TRUE"](0)


            if flag_value_changed is True:
                if "ON_CHANGE" in custom_functions:
                    custom_functions["ON_CHANGE"](0)

                self.setLayerVariableEvent(self.current_layer, [property_path])

            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'connect')

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
                widget_type = self.widgets[tuple[0].upper()][tuple[1].upper()]["TYPE"]
                self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].setEnabled(True)
                
                # Ensure QgsFieldExpressionWidget is always linked to current layer when enabled
                if widget_type == 'QgsFieldExpressionWidget' and self.current_layer is not None:
                    self.widgets[tuple[0].upper()][tuple[1].upper()]["WIDGET"].setLayer(self.current_layer)


    def properties_group_state_reset_to_default(self, tuple_group, group_name, state):

        if self.widgets_initialized is True and self.has_loaded_layers is True:
            for i, property_path in enumerate(tuple_group):
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

    def filtering_init_buffer_property(self):

        if self.widgets_initialized is True and self.has_loaded_layers is True:
                        




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
            
            if buffer_expression != '':
                property = QgsProperty.fromExpression(buffer_expression)
            else:
                property = QgsProperty()

            # if self.buffer_property_has_been_init is False:
                
            self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].init(0, property, property_definition, self.current_layer)

            if property.propertyType() == 0:
                # Register widgets with property button
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].registerEnabledWidget(self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"], True)
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].registerVisibleWidget(self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"], True)
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].registerEnabledWidget(self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"], False)
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].registerVisibleWidget(self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"], False)
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].registerExpressionWidget(self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"])
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].setText('')
                
                # CRITICAL: Force visibility explicitly AFTER registration
                self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"].setVisible(True)
                self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"].setEnabled(True)
                self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"].setVisible(False)
                self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"].setEnabled(False)

            else:
                # Register widgets with property button
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].registerEnabledWidget(self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"], False)
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].registerVisibleWidget(self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"], False)
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].registerEnabledWidget(self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"], True)
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].registerVisibleWidget(self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"], True)
                self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"].setClearButtonEnabled(True)
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].registerExpressionWidget(self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"])
                
                # CRITICAL: Force visibility explicitly AFTER registration
                self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"].setVisible(False)
                self.widgets["FILTERING"]["BUFFER_VALUE"]["WIDGET"].setEnabled(False)
                self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"].setVisible(True)
                self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"].setEnabled(True)
                
                #self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["SIGNALS"][0][1](True)

                

                
                # self.buffer_property_has_been_init = True


                


    def filtering_buffer_expression_edited(self):

        if self.widgets_initialized is True and self.has_loaded_layers is True:


            widgets_to_stop =   [
                                    ["FILTERING","BUFFER_VALUE_EXPRESSION"]
                                ]
            
            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'disconnect')



            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]

            if self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"].text().strip() in ('', 'NULL') or len(self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"].text().strip()) == 0:

                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer_value_expression"] = ''
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].setActive(False)
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["SIGNALS"][0][1](False)

            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'connect')
 

    def filtering_buffer_property_changed(self):

        if self.widgets_initialized is True and self.has_loaded_layers is True:


            widgets_to_stop =   [
                                    ["FILTERING","BUFFER_VALUE_PROPERTY"]
                                ]
            
            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'disconnect')


            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
            
            if layer_props["filtering"]["buffer_value_property"] is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer_value_expression"] = self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].toProperty().asExpression()
                self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"].setClearButtonEnabled(True)


            if layer_props["filtering"]["buffer_value_property"] is False:
                self.PROJECT_LAYERS[self.current_layer.id()]["filtering"]["buffer_value_expression"] = ''
                if self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"].text().strip() != '':
                    self.widgets["FILTERING"]["BUFFER_VALUE_EXPRESSION"]["WIDGET"].setText('')
                self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].setToProperty(QgsProperty())


            for widget_path in widgets_to_stop:
                self.manageSignal(widget_path, 'connect')


    def get_buffer_property_state(self):
        return self.widgets["FILTERING"]["BUFFER_VALUE_PROPERTY"]["WIDGET"].isActive()

              
    def dialog_export_output_path(self):

        if self.widgets_initialized is True and self.has_loaded_layers is True:

            path = ''
            datatype = ''

            state = self.widgets["EXPORTING"]["HAS_OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].isChecked()

            if self.widgets["EXPORTING"]["HAS_DATATYPE_TO_EXPORT"]["WIDGET"].isChecked() == True:  
                datatype = self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"].currentText()

            if state == True:

                if self.widgets["EXPORTING"]["HAS_LAYERS_TO_EXPORT"]["WIDGET"].isChecked() == True:

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

        if self.widgets_initialized is True and self.has_loaded_layers is True:

            if str(self.widgets["EXPORTING"]["OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].text()) == '':
                self.widgets["EXPORTING"]["OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].clear()
                self.widgets["EXPORTING"]["HAS_OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].setChecked(False)
                self.project_property_changed('has_output_folder_to_export', False)
                self.project_property_changed('output_folder_to_export', '')

    def dialog_export_output_pathzip(self):

        if self.widgets_initialized is True and self.has_loaded_layers is True:
            
            path = ''
            state = self.widgets["EXPORTING"]["HAS_ZIP_TO_EXPORT"]["WIDGET"].isChecked()

            if state == True:

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

            if state == None:
                state = self.project_props["OPTIONS"]["LAYERS"]["LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"]


            self.widgets["FILTERING"]["AUTO_CURRENT_LAYER"]["WIDGET"].setChecked(state)

            if state is True:
                self.project_props["OPTIONS"]["LAYERS"]["LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"] = state
                self.manageSignal(["QGIS","LAYER_TREE_VIEW"], 'connect')

            elif state is False:
                self.project_props["OPTIONS"]["LAYERS"]["LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG"] = state
                self.manageSignal(["QGIS", "LAYER_TREE_VIEW"], 'disconnect')
                
            self.setProjectVariablesEvent()

    def get_project_layers_from_app(self, project_layers, project=None):
        """
        Update dockwidget with latest layer information from FilterMateApp.
        
        Called when layer management tasks complete. Refreshes internal state,
        updates UI widgets, and re-establishes signal connections.
        
        Args:
            project_layers (dict): Updated PROJECT_LAYERS dictionary from app
            project (QgsProject, optional): QGIS project instance
            
        Workflow:
        1. Update PROJECT reference if provided
        2. Store new PROJECT_LAYERS
        3. Determine active layer (current or fallback to active)
        4. Set has_loaded_layers flag
        5. Enable widgets
        6. Refresh UI (output name, export combobox, etc.)
        7. Reconnect signals
        8. Initialize exploring groupbox
        
        Notes:
            - Always updates PROJECT_LAYERS even if widgets not initialized yet
            - Only updates UI if widgets_initialized is True
            - Handles cases with no layers gracefully
            - Always reconnects signals even without active layer
            - Called from FilterMateApp.layer_management_engine_task_completed()
        """

        # CRITICAL: Prevent recursive/multiple simultaneous calls
        if self._updating_layers:
            logger.warning("Blocking recursive call to get_project_layers_from_app")
            return
            
        self._updating_layers = True
        
        logger.info(f"get_project_layers_from_app called: widgets_initialized={self.widgets_initialized}, PROJECT_LAYERS count={len(project_layers)}")
        
        try:
            layer = None

            # Always update PROJECT and PROJECT_LAYERS, even if widgets not initialized yet
            # This fixes the issue where layers loaded at startup aren't tracked
            if project is not None:    
                self.PROJECT = project

            self.PROJECT_LAYERS = project_layers
            
            # Update has_loaded_layers flag based on PROJECT_LAYERS, even if widgets not initialized
            if len(list(self.PROJECT_LAYERS)) > 0:
                self.has_loaded_layers = True
            else:
                self.has_loaded_layers = False

            logger.info(f"has_loaded_layers={self.has_loaded_layers}, widgets_initialized={self.widgets_initialized}")

            # Only update UI if widgets are initialized
            if self.widgets_initialized is True:
                logger.info(f"Updating UI: PROJECT is not None={self.PROJECT is not None}, PROJECT_LAYERS count={len(list(self.PROJECT_LAYERS))}")

                if self.PROJECT is not None and len(list(self.PROJECT_LAYERS)) > 0:

                    try:
                        if self.current_layer is not None:
                            layers = [layer for layer in self.PROJECT.mapLayersByName(self.PROJECT_LAYERS[self.current_layer.id()]["infos"]["layer_name"]) if layer.id() == self.current_layer.id()]
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


                    if self.has_loaded_layers is False:
                        self.has_loaded_layers = True
                        
                    # CRITICAL: Always enable widgets if PROJECT_LAYERS has layers, even without active layer
                    logger.info(f"About to enable UI: PROJECT_LAYERS count={len(self.PROJECT_LAYERS)}, layer={layer.name() if layer else 'None'}")
                    logger.info(f"Calling set_widgets_enabled_state(True) with layer={layer.name() if layer else 'None'}")
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
                    # This ensures the indicator is updated when layers are added
                    if len(self.PROJECT_LAYERS) > 0:
                        # Get first available layer to determine backend
                        first_layer_id = list(self.PROJECT_LAYERS.keys())[0]
                        if first_layer_id in self.PROJECT_LAYERS:
                            layer_props = self.PROJECT_LAYERS[first_layer_id]
                            if 'layer_provider_type' in layer_props.get('infos', {}):
                                self._update_backend_indicator(layer_props['infos']['layer_provider_type'])
                    
                    if layer is not None and isinstance(layer, QgsVectorLayer):
                        # Layer-specific initialization
                        if layer.id() in self.PROJECT_LAYERS:
                            layer_props = self.PROJECT_LAYERS[layer.id()]
                            if 'layer_provider_type' in layer_props.get('infos', {}):
                                self._update_backend_indicator(layer_props['infos']['layer_provider_type'])
                        
                        self.manage_output_name()
                        self.select_tabTools_index()
                        self.current_layer_changed(layer)
                        
                        # CRITICAL: Only initialize exploring groupbox if layer exists in PROJECT_LAYERS
                        # This prevents KeyError when layers are being added/removed
                        if self.current_layer and self.current_layer.id() in self.PROJECT_LAYERS:
                            self.exploring_groupbox_init()
                        else:
                            logger.warning(f"Skipping exploring_groupbox_init for layer {layer.name()} - not yet in PROJECT_LAYERS")
                        
                        self.filtering_auto_current_layer_changed()
                        
                        # CRITICAL: Always refresh filtering combobox after layer changes
                        # This ensures newly added layers appear in the filtering list
                        # even when current_layer_changed() has already been called
                        if self.current_layer is not None and isinstance(self.current_layer, QgsVectorLayer):
                            self.manageSignal(["FILTERING","LAYERS_TO_FILTER"], 'disconnect')
                            self.filtering_populate_layers_chekableCombobox(self.current_layer)
                            self.manageSignal(["FILTERING","LAYERS_TO_FILTER"], 'connect', 'checkedItemsChanged')
                    else:
                        # No active layer found - widgets are enabled but show message to user
                        logger.info(f"UI enabled with {len(self.PROJECT_LAYERS)} layers but no active layer selected")
                        logger.info("User can click on a layer in the QGIS layer panel to activate it")
                    
                    return

                        
                else:
                    logger.warning(f"Cannot update UI: PROJECT is None={self.PROJECT is None}, PROJECT_LAYERS empty={len(list(self.PROJECT_LAYERS)) == 0}")
                    self.has_loaded_layers = False
                    self.disconnect_widgets_signals()
                    self._signals_connected = False
                    self.set_widgets_enabled_state(False)
                    return
            else:
                # Widgets not initialized yet - set flag to refresh later
                print(f"FilterMate: Widgets not initialized yet, setting pending flag. PROJECT_LAYERS count: {len(self.PROJECT_LAYERS)}")
                logger.warning(f"Widgets not initialized yet, setting pending flag. PROJECT_LAYERS count: {len(self.PROJECT_LAYERS)}")
                self._pending_layers_update = True
        finally:
            # CRITICAL: Always release the lock, even if an error occurred
            self._updating_layers = False


    def open_project_page(self):
        if "APP" in self.CONFIG_DATA and "OPTIONS" in self.CONFIG_DATA["APP"]:
            if "GITHUB_PAGE" in self.CONFIG_DATA["APP"]["OPTIONS"]:
                url = self.CONFIG_DATA["APP"]["OPTIONS"]["GITHUB_PAGE"]
                if url and url.startswith("http"):
                    webbrowser.open(url)


    def setLayerVariableEvent(self, layer=None, properties=None):
        """
        Emit signal to set layer variables.
        
        Args:
            layer: QgsVectorLayer to set, or None to use current_layer
            properties: List of properties (default: empty list)
        """
        if properties is None:
            properties = []

        if self.widgets_initialized is True:
            if layer == None:
                layer = self.current_layer
            
            # Ensure properties is a list type for PyQt signal
            if not isinstance(properties, list):
                print(f"FilterMate Warning: properties is {type(properties)}, converting to list")
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
            if layer == None:
                layer = self.current_layer
            
            # Double-check layer is valid before emitting signal
            try:
                if layer is not None and not sip.isdeleted(layer):
                    # Ensure properties is a list type for PyQt signal
                    if not isinstance(properties, list):
                        print(f"FilterMate Warning: properties is {type(properties)}, converting to list")
                        properties = []
                    self.resettingLayerVariableOnError.emit(layer, properties)
                else:
                    print(f"FilterMate: Cannot emit resettingLayerVariableOnError - layer is None or deleted")
            except RuntimeError as e:
                # Layer C++ object is deleted
                print(f"FilterMate: Cannot emit resettingLayerVariableOnError - layer object deleted: {e}")
            except TypeError as e:
                # Signal emission failed due to type mismatch
                print(f"FilterMate: Signal emission failed - type error: {e}")
                print(f"  layer type: {type(layer)}, properties type: {type(properties)}")


    def resetLayerVariableEvent(self, layer=None, properties=None):
        """
        Emit signal to reset layer variables.
        
        Args:
            layer: QgsVectorLayer to reset, or None to use current_layer
            properties: List of properties (default: empty list)
        """
        if properties is None:
            properties = []

        if self.widgets_initialized is True:
            if layer == None:
                layer = self.current_layer
            
            # Ensure properties is a list type for PyQt signal
            if not isinstance(properties, list):
                print(f"FilterMate Warning: properties is {type(properties)}, converting to list")
                properties = []
           
            self.resettingLayerVariable.emit(layer, properties)

    def setProjectVariablesEvent(self):
        if self.widgets_initialized is True:

            self.settingProjectVariables.emit()

    def _update_backend_indicator(self, provider_type):
        """
        Update the backend indicator label based on the layer provider type.
        
        Args:
            provider_type: The provider type string ('postgresql', 'spatialite', 'ogr', etc.)
        """
        if not self.backend_indicator_label:
            return
        
        from .modules.appUtils import POSTGRESQL_AVAILABLE
        
        # Determine backend and styling
        if provider_type == 'postgresql' and POSTGRESQL_AVAILABLE:
            backend_text = "Backend: PostgreSQL"
            style = "color: #2ecc71; font-size: 8pt; padding: 1px 4px;"
        elif provider_type == 'spatialite':
            backend_text = "Backend: Spatialite"
            style = "color: #3498db; font-size: 8pt; padding: 1px 4px;"
        elif provider_type == 'ogr':
            backend_text = "Backend: OGR"
            style = "color: #f39c12; font-size: 8pt; padding: 1px 4px;"
        elif provider_type == 'postgresql' and not POSTGRESQL_AVAILABLE:
            backend_text = "Backend: OGR (PostgreSQL unavailable)"
            style = "color: #e74c3c; font-size: 8pt; padding: 1px 4px;"
        else:
            backend_text = f"Backend: {provider_type}"
        
        self.backend_indicator_label.setText(backend_text)

    def getProjectLayersEvent(self, event):

        if self.widgets_initialized is True:

            self.gettingProjectLayers.emit()

    def closeEvent(self, event):

        if self.widgets_initialized is True:

            self.closingPlugin.emit()
            event.accept()

    def launchTaskEvent(self, state, task_name):

        if self.widgets_initialized is True:

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
            (self.checkableComboBoxLayer_exporting_layers, 'checkedItemsChanged', lambda: self._update_checkable_combo_tooltip(self.checkableComboBoxLayer_exporting_layers)),
            
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
                    combo_widget.setToolTip(f"Current layer: {text}")
                else:
                    combo_widget.setToolTip("No layer selected")
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
                        combo_widget.setToolTip(f"Selected layers:\n{text}")
                    else:
                        combo_widget.setToolTip("Multiple layers selected")
                else:
                    combo_widget.setToolTip("No layers selected")
        except Exception as e:
            logger.debug(f"FilterMate: Error updating checkable combo tooltip: {e}")
    
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
                    expression_widget.setToolTip(f"Expression:\n{formatted_expr}")
                elif expr:
                    expression_widget.setToolTip(f"Expression: {expr}")
                else:
                    expression_widget.setToolTip("No expression defined")
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
                    picker_widget.setToolTip(f"Display expression: {display_expr}")
                elif hasattr(picker_widget, 'feature'):
                    feature = picker_widget.feature()
                    if feature and feature.isValid():
                        # Show feature ID and first attribute
                        attrs = feature.attributes()
                        if attrs:
                            picker_widget.setToolTip(f"Feature ID: {feature.id()}\nFirst attribute: {attrs[0]}")
        except Exception as e:
            logger.debug(f"FilterMate: Error updating feature picker tooltip: {e}")




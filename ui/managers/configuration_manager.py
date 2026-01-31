# -*- coding: utf-8 -*-
"""
ConfigurationManager - Widget Configuration Management

Externalizes widget configuration logic from FilterMateDockWidget.
Created in v4.0 Sprint 6 as part of dockwidget reduction strategy.

Responsibilities:
- Define widget structure and properties
- Map layer/export properties to widget tuples
- Configure signal connections
- Initialize widget dictionaries

This replaces the 164-line dockwidget_widgets_configuration() method.
"""

from qgis.PyQt.QtCore import QObject
from ...infrastructure.logging import get_app_logger

logger = get_app_logger()


class ConfigurationManager(QObject):
    """
    Manages widget configuration dictionaries and property mappings.
    
    v4.0 Sprint 6: Extracted from FilterMateDockWidget to reduce God Class size.
    """
    
    def __init__(self, dockwidget):
        """
        Initialize configuration manager.
        
        Args:
            dockwidget: Reference to FilterMateDockWidget instance
        """
        super().__init__()
        self.dockwidget = dockwidget
        logger.debug("ConfigurationManager initialized")
    
    def get_layer_properties_tuples_dict(self):
        """
        Returns the mapping of layer properties to their widget tuples.
        
        Each property maps to a tuple of (category, widget_key) pairs that
        control or display that property.
        
        Returns:
            dict: Property name → tuple of (category, widget_key) pairs
        """
        return {
            "is": (
                ("exploring", "is_selecting"),
                ("exploring", "is_tracking"),
                ("exploring", "is_linking")
            ),
            "selection_expression": (
                ("exploring", "single_selection_expression"),
                ("exploring", "multiple_selection_expression"),
                ("exploring", "custom_selection_expression")
            ),
            "source_layer": (
                ("filtering", "use_centroids_source_layer"),
            ),
            "layers_to_filter": (
                ("filtering", "has_layers_to_filter"),
                ("filtering", "layers_to_filter"),
                ("filtering", "use_centroids_distant_layers")
            ),
            "combine_operator": (
                ("filtering", "has_combine_operator"),
                ("filtering", "source_layer_combine_operator"),
                ("filtering", "other_layers_combine_operator")
            ),
            "buffer_type": (
                ("filtering", "has_buffer_type"),
                ("filtering", "buffer_type"),
                ("filtering", "buffer_segments")
            ),
            "buffer_value": (
                ("filtering", "has_buffer_value"),
                ("filtering", "has_buffer_type"),
                ("filtering", "buffer_value"),
                ("filtering", "buffer_value_expression"),
                ("filtering", "buffer_value_property")
            ),
            "geometric_predicates": (
                ("filtering", "has_geometric_predicates"),
                ("filtering", "has_buffer_value"),
                ("filtering", "has_buffer_type"),
                ("filtering", "geometric_predicates")
            ),
            "use_centroids_distant_layers": (
                ("filtering", "use_centroids_distant_layers"),
            ),
            "use_centroids_source_layer": (
                ("filtering", "use_centroids_source_layer"),
            )
        }
    
    def get_export_properties_tuples_dict(self):
        """
        Returns the mapping of export properties to their widget tuples.
        
        Returns:
            dict: Property name → tuple of (category, widget_key) pairs
        """
        return {
            "layers_to_export": (
                ("exporting", "has_layers_to_export"),
                ("exporting", "layers_to_export")
            ),
            "projection_to_export": (
                ("exporting", "has_projection_to_export"),
                ("exporting", "projection_to_export")
            ),
            "styles_to_export": (
                ("exporting", "has_styles_to_export"),
                ("exporting", "styles_to_export")
            ),
            "datatype_to_export": (
                ("exporting", "has_datatype_to_export"),
                ("exporting", "datatype_to_export")
            ),
            "output_folder_to_export": (
                ("exporting", "has_output_folder_to_export"),
                ("exporting", "batch_output_folder"),
                ("exporting", "output_folder_to_export")
            ),
            "zip_to_export": (
                ("exporting", "has_zip_to_export"),
                ("exporting", "batch_zip"),
                ("exporting", "zip_to_export")
            ),
            "batch_output_folder": (
                ("exporting", "has_output_folder_to_export"),
                ("exporting", "batch_output_folder"),
                ("exporting", "output_folder_to_export")
            ),
            "batch_zip": (
                ("exporting", "has_zip_to_export"),
                ("exporting", "batch_zip"),
                ("exporting", "zip_to_export")
            )
        }
    
    def configure_widgets(self):
        """
        Configure all widget dictionaries and signal connections.
        
        This is the main entry point that replaces dockwidget_widgets_configuration().
        Sets up:
        - DOCK widgets (groupboxes, config tree, toolbox)
        - ACTION widgets (filter, undo, redo, export buttons)
        - EXPLORING widgets (feature selection, navigation)
        - FILTERING widgets (layer selection, geometric operations)
        - EXPORTING widgets (export configuration)
        - QGIS widgets (layer tree view)
        
        Returns:
            dict: Complete widgets configuration dictionary
        """
        d = self.dockwidget  # Shorthand
        
        widgets = {
            "DOCK": {},
            "ACTION": {},
            "EXPLORING": {},
            "FILTERING": {},
            "EXPORTING": {},
            "QGIS": {}
        }
        
        # DOCK widgets - Main UI containers
        # CRITICAL: GroupBoxes use "toggled" signal for checkbox state changes
        # and "collapsedStateChanged" signal for arrow collapse/expand
        widgets["DOCK"] = {
            "SINGLE_SELECTION": {
                "TYPE": "GroupBox",
                "WIDGET": d.mGroupBox_exploring_single_selection,
                "SIGNALS": [
                    ("toggled", lambda checked, x='single_selection': d._on_groupbox_clicked(x, checked)),
                    ("collapsedStateChanged", lambda collapsed, x='single_selection': d._on_groupbox_collapse_changed(x, collapsed))
                ]
            },
            "MULTIPLE_SELECTION": {
                "TYPE": "GroupBox",
                "WIDGET": d.mGroupBox_exploring_multiple_selection,
                "SIGNALS": [
                    ("toggled", lambda checked, x='multiple_selection': d._on_groupbox_clicked(x, checked)),
                    ("collapsedStateChanged", lambda collapsed, x='multiple_selection': d._on_groupbox_collapse_changed(x, collapsed))
                ]
            },
            "CUSTOM_SELECTION": {
                "TYPE": "GroupBox",
                "WIDGET": d.mGroupBox_exploring_custom_selection,
                "SIGNALS": [
                    ("toggled", lambda checked, x='custom_selection': d._on_groupbox_clicked(x, checked)),
                    ("collapsedStateChanged", lambda collapsed, x='custom_selection': d._on_groupbox_collapse_changed(x, collapsed))
                ]
            },
            "CONFIGURATION_TREE_VIEW": {
                "TYPE": "JsonTreeView",
                "WIDGET": d.config_view,
                "SIGNALS": [("collapsed", None), ("expanded", None)]
            },
            "CONFIGURATION_MODEL": {
                "TYPE": "JsonModel",
                "WIDGET": d.config_model,
                "SIGNALS": [("itemChanged", None)]
            },
            "CONFIGURATION_BUTTONBOX": {
                "TYPE": "DialogButtonBox",
                "WIDGET": d.buttonBox,
                "SIGNALS": [("accepted", None), ("rejected", None)]
            },
            "TOOLS": {
                "TYPE": "ToolBox",
                "WIDGET": d.toolBox_tabTools,
                "SIGNALS": [("currentChanged", d.select_tabTools_index)]
            }
        }
        
        # ACTION widgets - Main action buttons
        widgets["ACTION"] = {
            "FILTER": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_action_filter,
                "SIGNALS": [("clicked", lambda state, x='filter': d.launchTaskEvent(state, x))],
                "ICON": None
            },
            "UNDO_FILTER": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_action_undo_filter,
                "SIGNALS": [("clicked", lambda state, x='undo': d.launchTaskEvent(state, x))],
                "ICON": None
            },
            "REDO_FILTER": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_action_redo_filter,
                "SIGNALS": [("clicked", lambda state, x='redo': d.launchTaskEvent(state, x))],
                "ICON": None
            },
            "UNFILTER": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_action_unfilter,
                "SIGNALS": [("clicked", lambda state, x='unfilter': d.launchTaskEvent(state, x))],
                "ICON": None
            },
            "EXPORT": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_action_export,
                "SIGNALS": [("clicked", lambda state, x='export': d.launchTaskEvent(state, x))],
                "ICON": None
            },
            "ABOUT": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_action_about,
                "SIGNALS": [("clicked", d.open_project_page)],
                "ICON": None
            }
        }
        
        # EXPLORING widgets - Feature exploration and selection
        widgets["EXPLORING"] = {
            "IDENTIFY": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_exploring_identify,
                "SIGNALS": [("clicked", d.exploring_identify_clicked)],
                "ICON": None
            },
            "ZOOM": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_exploring_zoom,
                "SIGNALS": [("clicked", d.exploring_zoom_clicked)],
                "ICON": None
            },
            "IS_SELECTING": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_checkable_exploring_selecting,
                "SIGNALS": [(
                    "toggled",
                    lambda state, x='is_selecting', custom_functions={
                        "ON_TRUE": lambda x: d.exploring_select_features(),
                        "ON_FALSE": lambda x: d.exploring_deselect_features()
                    }: d.layer_property_changed(x, state, custom_functions)
                )],
                "ICON": None
            },
            "IS_TRACKING": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_checkable_exploring_tracking,
                "SIGNALS": [(
                    "toggled",
                    lambda state, x='is_tracking', custom_functions={
                        "ON_TRUE": lambda x: d.exploring_zoom_clicked()
                    }: d.layer_property_changed(x, state, custom_functions)
                )],
                "ICON": None
            },
            "IS_LINKING": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_checkable_exploring_linking_widgets,
                "SIGNALS": [(
                    "toggled",
                    lambda state, x='is_linking', custom_functions={
                        "ON_CHANGE": lambda x: d.exploring_link_widgets()
                    }: d.layer_property_changed(x, state, custom_functions)
                )],
                "ICON": None
            },
            "RESET_ALL_LAYER_PROPERTIES": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_exploring_reset_layer_properties,
                "SIGNALS": [("clicked", lambda: d.resetLayerVariableEvent())],
                "ICON": None
            },
            "SINGLE_SELECTION_FEATURES": {
                "TYPE": "FeatureComboBox",
                "WIDGET": d.mFeaturePickerWidget_exploring_single_selection,
                "SIGNALS": [("featureChanged", d.exploring_features_changed)]
            },
            # NOTE: fieldChanged signal handled by _setup_expression_widget_direct_connections() with debounce
            "SINGLE_SELECTION_EXPRESSION": {
                "TYPE": "QgsFieldExpressionWidget",
                "WIDGET": d.mFieldExpressionWidget_exploring_single_selection,
                "SIGNALS": [("fieldChanged", None)]
            },
            "MULTIPLE_SELECTION_FEATURES": {
                "TYPE": "CustomCheckableFeatureComboBox",
                "WIDGET": d.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection,
                "SIGNALS": [
                    ("updatingCheckedItemList", d.exploring_features_changed),
                    ("filteringCheckedItemList", lambda: d.exploring_source_params_changed(groupbox_override="multiple_selection"))
                ]
            },
            # NOTE: fieldChanged signal handled by _setup_expression_widget_direct_connections() with debounce
            "MULTIPLE_SELECTION_EXPRESSION": {
                "TYPE": "QgsFieldExpressionWidget",
                "WIDGET": d.mFieldExpressionWidget_exploring_multiple_selection,
                "SIGNALS": [("fieldChanged", None)]
            },
            # NOTE: fieldChanged signal handled by _setup_expression_widget_direct_connections() with debounce
            "CUSTOM_SELECTION_EXPRESSION": {
                "TYPE": "QgsFieldExpressionWidget",
                "WIDGET": d.mFieldExpressionWidget_exploring_custom_selection,
                "SIGNALS": [("fieldChanged", None)]
            }
        }
        
        # FILTERING widgets - Geometric filtering configuration
        widgets["FILTERING"] = {
            "AUTO_CURRENT_LAYER": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_checkable_filtering_auto_current_layer,
                "SIGNALS": [("clicked", lambda state: d.filtering_auto_current_layer_changed(state))],
                "ICON": None
            },
            "HAS_LAYERS_TO_FILTER": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_checkable_filtering_layers_to_filter,
                "SIGNALS": [(
                    "toggled",
                    lambda state, x='has_layers_to_filter', custom_functions={
                        "ON_CHANGE": lambda x: d.filtering_layers_to_filter_state_changed()
                    }: d.layer_property_changed(x, state, custom_functions)
                )],
                "ICON": None
            },
            "HAS_COMBINE_OPERATOR": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_checkable_filtering_current_layer_combine_operator,
                "SIGNALS": [(
                    "toggled",
                    lambda state, x='has_combine_operator', custom_functions={
                        "ON_CHANGE": lambda x: d.filtering_combine_operator_state_changed()
                    }: d.layer_property_changed(x, state, custom_functions)
                )],
                "ICON": None
            },
            "HAS_GEOMETRIC_PREDICATES": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_checkable_filtering_geometric_predicates,
                "SIGNALS": [(
                    "toggled",
                    lambda state, x='has_geometric_predicates', custom_functions={
                        "ON_CHANGE": lambda x: d.filtering_geometric_predicates_state_changed()
                    }: d.layer_property_changed(x, state, custom_functions)
                )],
                "ICON": None
            },
            "HAS_BUFFER_VALUE": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_checkable_filtering_buffer_value,
                "SIGNALS": [(
                    "toggled",
                    lambda state, x='has_buffer_value', custom_functions={
                        "ON_CHANGE": lambda x: d.filtering_buffer_value_state_changed()
                    }: d.layer_property_changed(x, state, custom_functions)
                )],
                "ICON": None
            },
            "HAS_BUFFER_TYPE": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_checkable_filtering_buffer_type,
                "SIGNALS": [(
                    "toggled",
                    lambda state, x='has_buffer_type', custom_functions={
                        # v4.0.3: Fixed - Call correct state change function
                        "ON_CHANGE": lambda x: d.filtering_buffer_type_state_changed()
                    }: d.layer_property_changed(x, state, custom_functions)
                )],
                "ICON": None
            },
            "CURRENT_LAYER": {
                "TYPE": "ComboBox",
                "WIDGET": d.comboBox_filtering_current_layer,
                # FIX 2026-01-14: Pass manual_change=True for manual combobox changes
                "SIGNALS": [("layerChanged", lambda layer: d.current_layer_changed(layer, manual_change=True))]
            },
            "LAYERS_TO_FILTER": {
                "TYPE": "CustomCheckableLayerComboBox",
                "WIDGET": d.checkableComboBoxLayer_filtering_layers_to_filter,
                "CUSTOM_LOAD_FUNCTION": lambda x: d.get_layers_to_filter(),
                "SIGNALS": [(
                    "checkedItemsChanged",
                    lambda state, custom_functions={
                        "CUSTOM_DATA": lambda x: d.get_layers_to_filter()
                    }, x='layers_to_filter': d.layer_property_changed(x, state, custom_functions)
                )]
            },
            "SOURCE_LAYER_COMBINE_OPERATOR": {
                "TYPE": "ComboBox",
                "WIDGET": d.comboBox_filtering_source_layer_combine_operator,
                "SIGNALS": [(
                    "currentIndexChanged",
                    lambda index, x='source_layer_combine_operator': d.layer_property_changed(x, d._index_to_combine_operator(index))
                )]
            },
            "OTHER_LAYERS_COMBINE_OPERATOR": {
                "TYPE": "ComboBox",
                "WIDGET": d.comboBox_filtering_other_layers_combine_operator,
                "SIGNALS": [(
                    "currentIndexChanged",
                    lambda index, x='other_layers_combine_operator': d.layer_property_changed(x, d._index_to_combine_operator(index))
                )]
            },
            "GEOMETRIC_PREDICATES": {
                "TYPE": "CheckableComboBox",
                "WIDGET": d.comboBox_filtering_geometric_predicates,
                "SIGNALS": [(
                    "checkedItemsChanged",
                    lambda state, x='geometric_predicates': d.layer_property_changed(x, state)
                )]
            },
            "USE_CENTROIDS_SOURCE_LAYER": {
                "TYPE": "CheckBox",
                "WIDGET": d.checkBox_filtering_use_centroids_source_layer,
                "SIGNALS": [(
                    "stateChanged",
                    lambda state, x='use_centroids_source_layer', custom_functions={
                        "ON_CHANGE": lambda x: d._update_buffer_validation()
                    }: d.layer_property_changed(x, bool(state), custom_functions)
                )]
            },
            "USE_CENTROIDS_DISTANT_LAYERS": {
                "TYPE": "CheckBox",
                "WIDGET": d.checkBox_filtering_use_centroids_distant_layers,
                "SIGNALS": [(
                    "stateChanged",
                    lambda state, x='use_centroids_distant_layers': d.layer_property_changed(x, bool(state))
                )]
            },
            "BUFFER_VALUE": {
                "TYPE": "QgsDoubleSpinBox",
                "WIDGET": d.mQgsDoubleSpinBox_filtering_buffer_value,
                "SIGNALS": [(
                    "valueChanged",
                    lambda state, x='buffer_value': d.layer_property_changed_with_buffer_style(x, state)
                )]
            },
            "BUFFER_VALUE_PROPERTY": {
                "TYPE": "PropertyOverrideButton",
                "WIDGET": d.mPropertyOverrideButton_filtering_buffer_value_property,
                "SIGNALS": [(
                    "changed",
                    lambda state=None, x='buffer_value_property', custom_functions={
                        "ON_CHANGE": lambda x: d.filtering_buffer_property_changed(),
                        "CUSTOM_DATA": lambda x: d.get_buffer_property_state()
                    }: d.layer_property_changed(x, state, custom_functions)
                )]
            },
            "BUFFER_TYPE": {
                "TYPE": "ComboBox",
                "WIDGET": d.comboBox_filtering_buffer_type,
                "SIGNALS": [(
                    "currentTextChanged",
                    lambda state, x='buffer_type': d.layer_property_changed(x, state)
                )]
            },
            "BUFFER_SEGMENTS": {
                "TYPE": "QgsSpinBox",
                "WIDGET": d.mQgsSpinBox_filtering_buffer_segments,
                "SIGNALS": [(
                    "valueChanged",
                    lambda state, x='buffer_segments': d.layer_property_changed(x, state)
                )]
            }
        }
        
        # EXPORTING widgets - Export configuration
        widgets["EXPORTING"] = {
            "HAS_LAYERS_TO_EXPORT": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_checkable_exporting_layers,
                "SIGNALS": [(
                    "toggled",
                    lambda state, x='has_layers_to_export': d.project_property_changed(x, state)
                )],
                "ICON": None
            },
            "HAS_PROJECTION_TO_EXPORT": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_checkable_exporting_projection,
                "SIGNALS": [(
                    "toggled",
                    lambda state, x='has_projection_to_export': d.project_property_changed(x, state)
                )],
                "ICON": None
            },
            "HAS_STYLES_TO_EXPORT": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_checkable_exporting_styles,
                "SIGNALS": [(
                    "toggled",
                    lambda state, x='has_styles_to_export': d.project_property_changed(x, state)
                )],
                "ICON": None
            },
            "HAS_DATATYPE_TO_EXPORT": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_checkable_exporting_datatype,
                "SIGNALS": [(
                    "toggled",
                    lambda state, x='has_datatype_to_export': d.project_property_changed(x, state)
                )],
                "ICON": None
            },
            "HAS_OUTPUT_FOLDER_TO_EXPORT": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_checkable_exporting_output_folder,
                "SIGNALS": [(
                    "clicked",  # v4.0.6 FIX: Use clicked (not toggled) to open file dialog
                    lambda state, x='has_output_folder_to_export', custom_functions={
                        "ON_CHANGE": lambda x: d.dialog_export_output_path()
                    }: d.project_property_changed(x, state, custom_functions)
                )],
                "ICON": None
            },
            "HAS_ZIP_TO_EXPORT": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_checkable_exporting_zip,
                "SIGNALS": [(
                    "clicked",  # v4.0.6 FIX: Use clicked (not toggled) to open file dialog
                    lambda state, x='has_zip_to_export', custom_functions={
                        "ON_CHANGE": lambda x: d.dialog_export_output_pathzip()
                    }: d.project_property_changed(x, state, custom_functions)
                )],
                "ICON": None
            },
            "BATCH_OUTPUT_FOLDER": {
                "TYPE": "CheckBox",
                "WIDGET": d.checkBox_batch_exporting_output_folder,
                "SIGNALS": [(
                    "stateChanged",
                    lambda state, x='batch_output_folder': d.project_property_changed(x, bool(state))
                )],
                "ICON": None
            },
            "BATCH_ZIP": {
                "TYPE": "CheckBox",
                "WIDGET": d.checkBox_batch_exporting_zip,
                "SIGNALS": [(
                    "stateChanged",
                    lambda state, x='batch_zip': d.project_property_changed(x, bool(state))
                )],
                "ICON": None
            },
            "LAYERS_TO_EXPORT": {
                "TYPE": "CustomCheckableLayerComboBox",
                "WIDGET": d.checkableComboBoxLayer_exporting_layers,
                "CUSTOM_LOAD_FUNCTION": lambda x: d.get_layers_to_export(),
                "SIGNALS": [(
                    "checkedItemsChanged",
                    lambda state, custom_functions={
                        "CUSTOM_DATA": lambda x: d.get_layers_to_export()
                    }, x='layers_to_export': d.project_property_changed(x, state, custom_functions)
                )]
            },
            "PROJECTION_TO_EXPORT": {
                "TYPE": "QgsProjectionSelectionWidget",
                "WIDGET": d.mQgsProjectionSelectionWidget_exporting_projection,
                "SIGNALS": [(
                    "crsChanged",
                    lambda state, x='projection_to_export', custom_functions={
                        "CUSTOM_DATA": lambda x: d.get_current_crs_authid()
                    }: d.project_property_changed(x, state, custom_functions)
                )]
            },
            "STYLES_TO_EXPORT": {
                "TYPE": "ComboBox",
                "WIDGET": d.comboBox_exporting_styles,
                "SIGNALS": [(
                    "currentTextChanged",
                    lambda state, x='styles_to_export': d.project_property_changed(x, state)
                )]
            },
            "DATATYPE_TO_EXPORT": {
                "TYPE": "ComboBox",
                "WIDGET": d.comboBox_exporting_datatype,
                "SIGNALS": [(
                    "currentTextChanged",
                    lambda state, x='datatype_to_export': d.project_property_changed(x, state)
                )]
            },
            "OUTPUT_FOLDER_TO_EXPORT": {
                "TYPE": "LineEdit",
                "WIDGET": d.lineEdit_exporting_output_folder,
                "SIGNALS": [(
                    "textEdited",
                    lambda state, x='output_folder_to_export', custom_functions={
                        "ON_CHANGE": lambda x: d.reset_export_output_path()
                    }: d.project_property_changed(x, state, custom_functions)
                )]
            },
            "ZIP_TO_EXPORT": {
                "TYPE": "LineEdit",
                "WIDGET": d.lineEdit_exporting_zip,
                "SIGNALS": [(
                    "textEdited",
                    lambda state, x='zip_to_export', custom_functions={
                        "ON_CHANGE": lambda x: d.reset_export_output_pathzip()
                    }: d.project_property_changed(x, state, custom_functions)
                )]
            }
        }
        
        # QGIS widgets - QGIS interface integration
        # FIX 2026-01-14: When AUTO_CURRENT_LAYER is enabled (user explicitly wants sync),
        # treat LAYER_TREE_VIEW changes as "manual" to bypass protection windows.
        # This ensures the user can switch layers via QGIS panel when auto-sync is enabled.
        widgets["QGIS"] = {
            "LAYER_TREE_VIEW": {
                "TYPE": "LayerTreeView",
                "WIDGET": d.iface.layerTreeView(),
                "SIGNALS": [("currentLayerChanged", lambda layer: d.current_layer_changed(
                    layer, 
                    manual_change=d.project_props.get("OPTIONS", {}).get("LAYERS", {}).get("LINK_LEGEND_LAYERS_AND_CURRENT_LAYER_FLAG", False)
                ))]
            }
        }
        
        logger.info(f"✓ ConfigurationManager configured {sum(len(v) for v in widgets.values())} widgets")
        return widgets
    
    def configure_pushbuttons(self, pushButton_config, icons_sizes, font):
        """v4.0 Sprint 16: Configure push buttons with icons, sizes, and cursors (migrated from dockwidget)."""
        from qgis.PyQt.QtCore import Qt, QSize
        from qgis.PyQt import QtGui, QtCore
        from qgis.PyQt.QtWidgets import QSizePolicy
        import os
        
        # v4.0.2 FIX: Use IconManager instead of get_themed_icon
        try:
            from ..config import UIConfig
            UI_CONFIG_AVAILABLE = True
        except ImportError:
            UI_CONFIG_AVAILABLE = False
        
        # Get IconManager from dockwidget if available
        icon_manager = getattr(self.dockwidget, '_icon_manager', None)
        
        icons_config = pushButton_config.get("ICONS", {})
        exploring_tooltips = {
            "IDENTIFY": self.dockwidget.tr("Identify selected feature"),
            "ZOOM": self.dockwidget.tr("Zoom to selected feature"),
            "IS_SELECTING": self.dockwidget.tr("Toggle feature selection on map"),
            "IS_TRACKING": self.dockwidget.tr("Auto-zoom when feature changes"),
            "IS_LINKING": self.dockwidget.tr("Link exploring widgets together"),
            "RESET_ALL_LAYER_PROPERTIES": self.dockwidget.tr("Reset all layer exploring properties")
        }
        
        for widget_group in self.dockwidget.widgets:
            for widget_name, widget_data in self.dockwidget.widgets[widget_group].items():
                if widget_data["TYPE"] != "PushButton":
                    continue
                widget_obj = widget_data["WIDGET"]
                
                # v4.0.2 FIX: Load icon using IconManager for proper theming
                icon_file = icons_config.get(widget_group, {}).get(widget_name)
                if icon_file:
                    if icon_manager and hasattr(icon_manager, 'set_button_icon'):
                        # Use new IconManager system (theme-aware + stores icon_name)
                        icon_manager.set_button_icon(widget_obj, icon_file)
                        widget_data["ICON"] = os.path.join(self.dockwidget.plugin_dir, "icons", icon_file)
                    else:
                        # Fallback to old method
                        icon_path = os.path.join(self.dockwidget.plugin_dir, "icons", icon_file)
                        if os.path.exists(icon_path):
                            widget_obj.setIcon(QtGui.QIcon(icon_path))
                            widget_data["ICON"] = icon_path
                
                widget_obj.setCursor(Qt.PointingHandCursor)
                if widget_group == "EXPLORING" and widget_name in exploring_tooltips:
                    widget_obj.setToolTip(exploring_tooltips[widget_name])
                
                # Apply dimensions
                icon_size = icons_sizes.get(widget_group, icons_sizes["OTHERS"])
                if UI_CONFIG_AVAILABLE:
                    btn_type = "action_button" if widget_group == "ACTION" else ("tool_button" if widget_group in ["EXPLORING", "FILTERING", "EXPORTING"] else "button")
                    h = UIConfig.get_button_height(btn_type)
                    s = UIConfig.get_icon_size(btn_type)
                else:
                    h = 36 if widget_group in ["EXPLORING", "FILTERING", "EXPORTING"] else icon_size * 2
                    s = icon_size
                
                widget_obj.setMinimumSize(h, h)
                widget_obj.setMaximumSize(h, h)
                widget_obj.setIconSize(QSize(s, s))
                widget_obj.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                widget_obj.setFont(font)
    
    def configure_other_widgets(self, font):
        """v4.0 Sprint 16: Configure non-button widgets (migrated from dockwidget)."""
        from qgis.PyQt.QtCore import Qt
        
        for widget_group in self.dockwidget.widgets:
            for widget_name in self.dockwidget.widgets[widget_group]:
                widget_type = self.dockwidget.widgets[widget_group][widget_name]["TYPE"]
                widget_obj = self.dockwidget.widgets[widget_group][widget_name]["WIDGET"]
                
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
    
    def configure_key_widgets_sizes(self, icons_sizes):
        """v4.0 Sprint 16: Configure sizes for widget_keys and frame_actions (migrated from dockwidget)."""
        from qgis.PyQt.QtWidgets import QSizePolicy
        
        # Check if UI config available
        try:
            from ..config.ui_config import UIConfig
            UI_CONFIG_AVAILABLE = True
        except ImportError:
            UI_CONFIG_AVAILABLE = False
        
        d = self.dockwidget
        
        if UI_CONFIG_AVAILABLE:
            # Get widget_keys width directly from config
            widget_keys_width = UIConfig.get_config('widget_keys', 'max_width') or 56
            
            for widget in [d.widget_exploring_keys, d.widget_filtering_keys, d.widget_exporting_keys]:
                widget.setMinimumWidth(widget_keys_width)
                widget.setMaximumWidth(widget_keys_width)
                widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            
            # Set frame actions size (convert to int to avoid float)
            action_button_height = UIConfig.get_button_height("action_button")
            frame_height = max(int(action_button_height * 1.8), 56)  # Minimum 56px to prevent clipping
            d.frame_actions.setMinimumHeight(frame_height)
            d.frame_actions.setMaximumHeight(frame_height + 15)  # Allow flexibility
        else:
            # Fallback to hardcoded values
            icon_size = icons_sizes["OTHERS"]
            for widget in [d.widget_exploring_keys, d.widget_filtering_keys, d.widget_exporting_keys]:
                widget.setMinimumWidth(80)
                widget.setMaximumWidth(80)
                widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            
            # Set frame actions size
            icon_size = icons_sizes["ACTION"]
            d.frame_actions.setMinimumHeight(max(icon_size * 2, 56))
            d.frame_actions.setMaximumHeight(max(icon_size * 2, 56) + 15)
    
    def setup_exploring_tab_widgets(self):
        """v4.0 Sprint 16: Configure Exploring tab widgets (migrated from dockwidget)."""
        from qgis.core import QgsFieldProxyModel
        
        d = self.dockwidget
        # Insert the multiple selection widget into the layout
        d.horizontalLayout_exploring_multiple_feature_picker.insertWidget(
            0, d.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection, 1)
        # Ensure visibility after insertion
        d.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection.show()
        logger.debug(f"Inserted multiple selection widget into layout, count: {d.horizontalLayout_exploring_multiple_feature_picker.count()}")
        
        field_filters = QgsFieldProxyModel.AllTypes
        for widget in [d.mFieldExpressionWidget_exploring_single_selection,
                       d.mFieldExpressionWidget_exploring_multiple_selection,
                       d.mFieldExpressionWidget_exploring_custom_selection]:
            widget.setFilters(field_filters)
            # FIX v4.1 Simon 2026-01-16: INTERDIRE les valeurs NULL dans les combobox field
            # Les QgsFieldExpressionWidget autorisent par défaut la sélection d'une valeur vide
            # qui s'affiche comme "NULL". On doit désactiver cette option pour garantir qu'un
            # champ est TOUJOURS sélectionné.
            widget.setAllowEmptyFieldName(False)
        # v4.0.1 CLEAN #1: Removed direct fieldChanged connections to avoid triple-connection
        # fieldChanged signals now handled ONLY by ExploringController via SignalManager
        # setup_expression_widget_direct_connections() REMOVED in v4.0.1 Phase 1 cleanup
        # ExploringController now handles ALL fieldChanged signals via SignalManager
    
    #         widget.fieldChanged.connect(lambda f, g=groupbox: d._schedule_expression_change(g, f))
    
    def setup_filtering_tab_widgets(self):
        """v4.0 Sprint 16: Configure widgets for Filtering tab (migrated from dockwidget)."""
        import os
        from qgis.PyQt import QtGui, QtCore, QtWidgets
        
        # FIX 2026-01-21: Import from correct location (gui in QGIS 3.30+, core in older versions)
        try:
            from qgis.gui import QgsMapLayerProxyModel
        except ImportError:
            from qgis.core import QgsMapLayerProxyModel
        
        d = self.dockwidget
        # Note: Filter to show vector layers WITH geometry AND raster layers
        # HasGeometry = PointLayer | LineLayer | PolygonLayer = 4 | 8 | 16 = 28
        # RasterLayer = 1
        # This excludes tables without geometry (NoGeometry = 2)
        try:
            # Note: Accept both vector layers with geometry AND raster layers for unified exploring
            # QGIS 3.40+: setFilters() deprecated, use setProxyModelFilters()
            filters = QgsMapLayerProxyModel.HasGeometry | QgsMapLayerProxyModel.RasterLayer
            if hasattr(d.comboBox_filtering_current_layer, 'setProxyModelFilters'):
                d.comboBox_filtering_current_layer.setProxyModelFilters(filters)
            else:
                d.comboBox_filtering_current_layer.setFilters(filters)
            logger.info("comboBox_filtering_current_layer: Filter set to HasGeometry | RasterLayer (vector + raster)")
        except Exception as e:
            logger.warning(f"Could not set HasGeometry | RasterLayer filter: {e}")
            # Fallback to VectorLayer only
            if hasattr(d.comboBox_filtering_current_layer, 'setProxyModelFilters'):
                d.comboBox_filtering_current_layer.setProxyModelFilters(QgsMapLayerProxyModel.VectorLayer)
            else:
                d.comboBox_filtering_current_layer.setFilters(QgsMapLayerProxyModel.VectorLayer)
        
        # Apply themed icon to centroids checkbox
        try:
            from ..icons import get_themed_icon, ICON_THEME_AVAILABLE
        except ImportError:
            ICON_THEME_AVAILABLE = False
        
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "icons", "centroid.png")
        if os.path.exists(icon_path) and hasattr(d, 'checkBox_filtering_use_centroids_source_layer'):
            icon = get_themed_icon(icon_path) if ICON_THEME_AVAILABLE else QtGui.QIcon(icon_path)
            d.checkBox_filtering_use_centroids_source_layer.setIcon(icon)
            d.checkBox_filtering_use_centroids_source_layer.setText("")
            d.checkBox_filtering_use_centroids_source_layer.setLayoutDirection(QtCore.Qt.RightToLeft)

        # Configure centroids distant layers checkbox (created in setupUiCustom)
        # Widget already created in setupUiCustom() - just configure appearance
        if hasattr(d, 'checkBox_filtering_use_centroids_distant_layers'):
            d.checkBox_filtering_use_centroids_distant_layers.setText("")
            d.checkBox_filtering_use_centroids_distant_layers.setToolTip(d.tr("Use centroids instead of full geometries for distant layers"))
            d.checkBox_filtering_use_centroids_distant_layers.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            if os.path.exists(icon_path):
                icon = get_themed_icon(icon_path) if ICON_THEME_AVAILABLE else QtGui.QIcon(icon_path)
                d.checkBox_filtering_use_centroids_distant_layers.setIcon(icon)
            d.checkBox_filtering_use_centroids_distant_layers.setLayoutDirection(QtCore.Qt.RightToLeft)
            d.checkBox_filtering_use_centroids_distant_layers.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)

        
        # Create horizontal layout and insert widgets
        d.horizontalLayout_filtering_distant_layers = QtWidgets.QHBoxLayout()
        d.horizontalLayout_filtering_distant_layers.setSpacing(4)
        d.horizontalLayout_filtering_distant_layers.addWidget(d.checkableComboBoxLayer_filtering_layers_to_filter)
        d.horizontalLayout_filtering_distant_layers.addWidget(d.checkBox_filtering_use_centroids_distant_layers)
        
        # Insert into main vertical layout at position 2 (after current layer, before predicates)
        if hasattr(d, 'verticalLayout_filtering_values'):
            d.verticalLayout_filtering_values.insertLayout(2, d.horizontalLayout_filtering_distant_layers)
            # Ensure visibility
            d.checkableComboBoxLayer_filtering_layers_to_filter.show()
            d.checkBox_filtering_use_centroids_distant_layers.show()
            logger.debug(f"Inserted filtering layers layout, widget visible: {d.checkableComboBoxLayer_filtering_layers_to_filter.isVisible()}")
        
        try:
            from ..config import UIConfig
            h = UIConfig.get_config('combobox', 'height')
            d.checkableComboBoxLayer_filtering_layers_to_filter.setMinimumHeight(h)
            d.checkableComboBoxLayer_filtering_layers_to_filter.setMaximumHeight(h)
        except Exception:
            pass
    
    def setup_exporting_tab_widgets(self):
        """v4.0 Sprint 16: Configure widgets for Exporting tab (migrated from dockwidget)."""
        from qgis.PyQt import QtWidgets
        from qgis.PyQt.QtGui import QColor
        
        d = self.dockwidget
        # Widget already created in setupUiCustom() - just configure it
        
        if hasattr(d, 'verticalLayout_exporting_values'):
            d.verticalLayout_exporting_values.insertWidget(0, d.checkableComboBoxLayer_exporting_layers)
            d.checkableComboBoxLayer_exporting_layers.show()
            logger.debug(f"Inserted exporting layers widget, visible: {d.checkableComboBoxLayer_exporting_layers.isVisible()}")
            d.verticalLayout_exporting_values.insertItem(1, QtWidgets.QSpacerItem(20, 4, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding))
        
        try:
            from ..config import UIConfig
            h = UIConfig.get_config('combobox', 'height')
            d.checkableComboBoxLayer_exporting_layers.setMinimumHeight(h)
            d.checkableComboBoxLayer_exporting_layers.setMaximumHeight(h)
        except Exception:
            pass
        
        for btn in ['pushButton_checkable_exporting_layers', 'pushButton_checkable_exporting_projection',
                    'pushButton_checkable_exporting_styles', 'pushButton_checkable_exporting_datatype',
                    'pushButton_checkable_exporting_output_folder', 'pushButton_checkable_exporting_zip']:
            if hasattr(d, btn):
                getattr(d, btn).setEnabled(False)
        
        d.iface.mapCanvas().setSelectionColor(QColor(237, 97, 62, 75))

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
from infrastructure.logging import get_app_logger

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
                    "clicked",
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
                    "clicked",
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
                    "clicked",
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
                    "clicked",
                    lambda state, x='has_buffer_value', custom_functions={
                        "ON_CHANGE": lambda x: d.filtering_buffer_property_changed()
                    }: d.layer_property_changed(x, state, custom_functions)
                )],
                "ICON": None
            },
            "HAS_BUFFER_TYPE": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_checkable_filtering_buffer_type,
                "SIGNALS": [(
                    "clicked",
                    lambda state, x='has_buffer_type', custom_functions={
                        "ON_CHANGE": lambda x: d.filtering_buffer_type_state_changed()
                    }: d.layer_property_changed(x, state, custom_functions)
                )],
                "ICON": None
            },
            "CURRENT_LAYER": {
                "TYPE": "ComboBox",
                "WIDGET": d.comboBox_filtering_current_layer,
                "SIGNALS": [("layerChanged", d.current_layer_changed)]
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
                    "clicked",
                    lambda state, x='has_layers_to_export': d.project_property_changed(x, state)
                )],
                "ICON": None
            },
            "HAS_PROJECTION_TO_EXPORT": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_checkable_exporting_projection,
                "SIGNALS": [(
                    "clicked",
                    lambda state, x='has_projection_to_export': d.project_property_changed(x, state)
                )],
                "ICON": None
            },
            "HAS_STYLES_TO_EXPORT": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_checkable_exporting_styles,
                "SIGNALS": [(
                    "clicked",
                    lambda state, x='has_styles_to_export': d.project_property_changed(x, state)
                )],
                "ICON": None
            },
            "HAS_DATATYPE_TO_EXPORT": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_checkable_exporting_datatype,
                "SIGNALS": [(
                    "clicked",
                    lambda state, x='has_datatype_to_export': d.project_property_changed(x, state)
                )],
                "ICON": None
            },
            "HAS_OUTPUT_FOLDER_TO_EXPORT": {
                "TYPE": "PushButton",
                "WIDGET": d.pushButton_checkable_exporting_output_folder,
                "SIGNALS": [(
                    "clicked",
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
                    "clicked",
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
        widgets["QGIS"] = {
            "LAYER_TREE_VIEW": {
                "TYPE": "LayerTreeView",
                "WIDGET": d.iface.layerTreeView(),
                "SIGNALS": [("currentLayerChanged", d.current_layer_changed)]
            }
        }
        
        logger.info(f"✓ ConfigurationManager configured {sum(len(v) for v in widgets.values())} widgets")
        return widgets

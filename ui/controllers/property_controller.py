"""
PropertyController - Layer Property Management.

Handles layer property changes (is_*, selection_expression, filtering/exploring/exporting
properties) with centralized validation and callback management.

Story: MIG-074
Phase: 6 - God Class DockWidget Migration
Pattern: Strangler Fig - Gradual extraction from filter_mate_dockwidget.py
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Callable, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum, auto

try:
    from qgis.PyQt.QtCore import pyqtSignal
except ImportError:
    from PyQt5.QtCore import pyqtSignal

from .base_controller import BaseController

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class PropertyType(Enum):
    """Types of layer properties."""
    IS = auto()           # Boolean toggles (is_selecting, is_tracking, etc.)
    EXPRESSION = auto()   # Selection expressions
    FILTERING = auto()    # Filtering properties
    EXPLORING = auto()    # Exploring properties
    EXPORTING = auto()    # Exporting properties
    SOURCE_LAYER = auto()  # Source layer properties (use_centroids)
    OTHER = auto()        # Other properties


@dataclass
class PropertyChange:
    """Represents a property change operation."""
    property_name: str
    group_key: str
    new_value: Any
    old_value: Any = None
    property_type: PropertyType = PropertyType.OTHER
    custom_functions: Dict[str, Callable] = field(default_factory=dict)
    value_changed: bool = False


class PropertyController(BaseController):
    """
    Controller for layer property management.

    Handles:
    - Property change validation
    - Property path resolution
    - Custom function callbacks (ON_TRUE, ON_FALSE, ON_CHANGE)
    - PROJECT_LAYERS updates
    - Buffer styling

    Emits:
    - property_changed: When a property value changes
    - property_validated: When a property is validated (before change)
    - property_error: When a property change fails
    - buffer_style_changed: When buffer value styling changes
    """

    # Signals
    property_changed = pyqtSignal(str, object, object)  # property_name, new_value, old_value
    property_validated = pyqtSignal(str, bool)  # property_name, is_valid
    property_error = pyqtSignal(str, str)  # property_name, error_message
    buffer_style_changed = pyqtSignal(float)  # buffer_value

    def __init__(self, dockwidget: "FilterMateDockWidget"):
        """
        Initialize PropertyController.

        Args:
            dockwidget: Parent dockwidget reference
        """
        super().__init__(dockwidget)

        # Property type mappings
        self._property_type_cache: Dict[str, PropertyType] = {}

        # Widgets to disconnect during property changes
        self._widgets_to_disconnect: List[List[str]] = [
            ["EXPLORING", "SINGLE_SELECTION_FEATURES"],
            ["EXPLORING", "SINGLE_SELECTION_EXPRESSION"],
            ["EXPLORING", "MULTIPLE_SELECTION_FEATURES"],
            ["EXPLORING", "MULTIPLE_SELECTION_EXPRESSION"],
            ["EXPLORING", "CUSTOM_SELECTION_EXPRESSION"]
        ]

        # Buffer styling configuration
        self._buffer_erosion_style = """
            QgsDoubleSpinBox {
                background-color: #FFF3CD;
                border: 2px solid #FFC107;
                color: #856404;
            }
            QgsDoubleSpinBox:focus {
                border: 2px solid #FF9800;
            }
        """

    def setup(self) -> None:
        """Initialize the controller."""
        self._is_initialized = True
        logger.debug("PropertyController setup complete")

    def teardown(self) -> None:
        """Cleanup controller resources."""
        self._property_type_cache.clear()
        self._is_initialized = False
        logger.debug("PropertyController teardown complete")

    def on_tab_activated(self) -> None:
        """Handle tab activation."""
        pass  # Property controller is always active

    # ─────────────────────────────────────────────────────────────────
    # Property Change Handling
    # ─────────────────────────────────────────────────────────────────

    def change_property(
        self,
        input_property: str,
        input_data: Any = None,
        custom_functions: Optional[Dict[str, Callable]] = None
    ) -> bool:
        """
        Handle property changes for the current layer.

        Main entry point for property changes. Orchestrates:
        1. Widget disconnection
        2. Property parsing and validation
        3. Property path resolution
        4. Type-specific update
        5. Callbacks and variable events
        6. Widget reconnection

        Args:
            input_property: Property identifier string
            input_data: New value
            custom_functions: Optional callbacks dict

        Returns:
            bool: True if property was changed
        """
        if custom_functions is None:
            custom_functions = {}

        dw = self.dockwidget

        # Guard: widgets must be initialized
        if not getattr(dw, 'widgets_initialized', False):
            return False

        # Guard: must have current layer
        current_layer = getattr(dw, 'current_layer', None)
        if current_layer is None:
            return False

        # Guard: layer must be in PROJECT_LAYERS
        layer_id = current_layer.id()
        project_layers = getattr(dw, 'PROJECT_LAYERS', {})
        if layer_id not in project_layers:
            logger.warning(
                f"change_property: layer {current_layer.name()} not in PROJECT_LAYERS"
            )
            self.property_error.emit(input_property, "Layer not in PROJECT_LAYERS")
            return False

        # Disconnect exploring widgets during property change
        self._disconnect_exploring_widgets()

        try:
            # Parse input data
            parsed_data, state = self._parse_property_data(input_data)

            # Find property path
            layer_props = project_layers[layer_id]
            result = self._find_property_path(input_property)
            group_key, property_path, properties_tuples, index = result

            if group_key is None or property_path is None:
                logger.warning(
                    f"change_property: property '{input_property}' not found"
                )
                self.property_error.emit(input_property, "Property not found")
                return False

            # Validate property
            self.property_validated.emit(input_property, True)

            # Create change object
            change = PropertyChange(
                property_name=input_property,
                group_key=group_key,
                new_value=parsed_data,
                old_value=self._get_current_value(layer_props, property_path),
                property_type=self._get_property_type(group_key),
                custom_functions=custom_functions
            )

            # Update by property type
            if group_key == 'is':
                change.value_changed = self._update_is_property(
                    property_path, layer_props, parsed_data, custom_functions
                )
            elif group_key == 'selection_expression':
                change.value_changed = self._update_selection_expression(
                    property_path, layer_props, parsed_data, custom_functions
                )
            else:
                change.value_changed = self._update_other_property(
                    property_path, properties_tuples, group_key,
                    layer_props, parsed_data, custom_functions
                )

            # Trigger change callbacks
            if change.value_changed:
                if "ON_CHANGE" in custom_functions:
                    custom_functions["ON_CHANGE"](0)

                # Update layer variables
                if hasattr(dw, 'setLayerVariableEvent'):
                    dw.setLayerVariableEvent(current_layer, [property_path])

                # Emit signal
                self.property_changed.emit(
                    input_property,
                    change.new_value,
                    change.old_value
                )

            return change.value_changed

        finally:
            # Always reconnect widgets
            self._reconnect_exploring_widgets()

    def change_property_with_buffer_style(
        self,
        input_property: str,
        input_data: Any = None
    ) -> bool:
        """
        Handle buffer value changes with visual style feedback.

        Applies visual styling for negative (erosion) vs positive (expansion).

        Args:
            input_property: Property name
            input_data: Buffer value

        Returns:
            bool: True if property was changed
        """
        # First, call normal property change
        changed = self.change_property(input_property, input_data)

        # Then update visual style
        self._update_buffer_style(input_data)

        return changed

    # ─────────────────────────────────────────────────────────────────
    # Property Parsing and Resolution
    # ─────────────────────────────────────────────────────────────────

    def _parse_property_data(self, input_data: Any) -> Tuple[Any, Optional[bool]]:
        """
        Parse and validate input data for property updates.

        Args:
            input_data: Property value

        Returns:
            tuple: (parsed_data, state) where state indicates validity
        """
        state = None

        if isinstance(input_data, (dict, list, str)):
            state = len(input_data) >= 0
        elif isinstance(input_data, (int, float)):
            state = int(input_data) >= 0
            if isinstance(input_data, float):
                # Truncate to 2 decimal places
                input_data = round(input_data, 2)
        elif isinstance(input_data, bool):
            state = input_data
        elif input_data is None:
            state = False

        return input_data, state

    def _find_property_path(
        self,
        input_property: str
    ) -> Tuple[Optional[str], Optional[tuple], Optional[list], Optional[int]]:
        """
        Find property path and group key from input property name.

        Args:
            input_property: Property identifier string

        Returns:
            tuple: (group_key, property_path, properties_tuples, index)
        """
        dw = self.dockwidget
        properties_dict = getattr(dw, 'layer_properties_tuples_dict', {})

        for group_key, properties_tuples in properties_dict.items():
            for i, property_tuple in enumerate(properties_tuples):
                if property_tuple[1] == input_property:
                    return group_key, property_tuple, properties_tuples, i

        return None, None, None, None

    def _get_property_type(self, group_key: str) -> PropertyType:
        """
        Get property type from group key.

        Args:
            group_key: Property group key

        Returns:
            PropertyType enum value
        """
        if group_key in self._property_type_cache:
            return self._property_type_cache[group_key]

        type_map = {
            'is': PropertyType.IS,
            'selection_expression': PropertyType.EXPRESSION,
            'filtering': PropertyType.FILTERING,
            'exploring': PropertyType.EXPLORING,
            'exporting': PropertyType.EXPORTING,
            'source_layer': PropertyType.SOURCE_LAYER
        }

        result = type_map.get(group_key, PropertyType.OTHER)
        self._property_type_cache[group_key] = result
        return result

    def _get_current_value(
        self,
        layer_props: Dict,
        property_path: tuple
    ) -> Any:
        """
        Get current value of a property.

        Args:
            layer_props: Layer properties dict
            property_path: Property path tuple

        Returns:
            Current property value or None
        """
        if len(property_path) >= 2:
            return layer_props.get(property_path[0], {}).get(property_path[1])
        return None

    # ─────────────────────────────────────────────────────────────────
    # Type-Specific Property Updates
    # ─────────────────────────────────────────────────────────────────

    def _update_is_property(
        self,
        property_path: tuple,
        layer_props: Dict,
        input_data: Any,
        custom_functions: Dict
    ) -> bool:
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
        dw = self.dockwidget
        layer_id = dw.current_layer.id()
        project_layers = dw.PROJECT_LAYERS

        current_value = layer_props.get(property_path[0], {}).get(property_path[1])

        # Special case: is_changing_all_layer_properties toggles
        if property_path[1] == "is_changing_all_layer_properties":
            if current_value is True:
                project_layers[layer_id][property_path[0]][property_path[1]] = False
                if "ON_TRUE" in custom_functions:
                    custom_functions["ON_TRUE"](0)
                if hasattr(dw, 'switch_widget_icon'):
                    dw.switch_widget_icon(property_path, False)
                return True
            elif current_value is False:
                project_layers[layer_id][property_path[0]][property_path[1]] = True
                if "ON_FALSE" in custom_functions:
                    custom_functions["ON_FALSE"](0)
                if hasattr(dw, 'switch_widget_icon'):
                    dw.switch_widget_icon(property_path, True)
                return True

        # Normal boolean property
        if current_value != input_data:
            # Ensure property path exists
            if property_path[0] not in project_layers[layer_id]:
                project_layers[layer_id][property_path[0]] = {}

            project_layers[layer_id][property_path[0]][property_path[1]] = input_data

            if input_data is True and "ON_TRUE" in custom_functions:
                custom_functions["ON_TRUE"](0)
            elif input_data is False and "ON_FALSE" in custom_functions:
                custom_functions["ON_FALSE"](0)

            return True

        return False

    def _update_selection_expression(
        self,
        property_path: tuple,
        layer_props: Dict,
        input_data: Any,
        custom_functions: Dict
    ) -> bool:
        """
        Update selection expression properties.

        Args:
            property_path: Property path tuple
            layer_props: Layer properties dict
            input_data: New expression value
            custom_functions: Callbacks dict

        Returns:
            bool: Always True to ensure display update
        """
        dw = self.dockwidget
        layer_id = dw.current_layer.id()
        project_layers = dw.PROJECT_LAYERS

        current_value = str(layer_props.get(property_path[0], {}).get(property_path[1], ''))

        if current_value != str(input_data):
            # Ensure property path exists
            if property_path[0] not in project_layers[layer_id]:
                project_layers[layer_id][property_path[0]] = {}

            project_layers[layer_id][property_path[0]][property_path[1]] = input_data

            if "ON_TRUE" in custom_functions:
                custom_functions["ON_TRUE"](0)

        # CRITICAL: Always return True to update FeaturePicker display
        return True

    def _update_other_property(
        self,
        property_path: tuple,
        properties_tuples: list,
        group_key: str,
        layer_props: Dict,
        input_data: Any,
        custom_functions: Dict
    ) -> bool:
        """
        Update other property types.

        Args:
            property_path: Property path tuple
            properties_tuples: Property tuples list
            group_key: Group key
            layer_props: Layer properties dict
            input_data: New value
            custom_functions: Callbacks dict

        Returns:
            bool: True if value changed
        """
        dw = self.dockwidget
        layer_id = dw.current_layer.id()
        project_layers = dw.PROJECT_LAYERS
        widgets = getattr(dw, 'widgets', {})

        if not properties_tuples:
            logger.warning("_update_other_property: empty properties_tuples")
            return False

        # Source layer group has no parent toggle, always enabled
        if group_key == 'source_layer':
            group_state = True
        else:
            group_property = properties_tuples[0]
            group_widget = widgets.get(
                group_property[0].upper(), {}
            ).get(group_property[1].upper(), {}).get("WIDGET")

            if group_widget is not None and hasattr(group_widget, 'isChecked'):
                group_state = group_widget.isChecked()
            else:
                group_state = True

        logger.debug(f"_update_other_property: {property_path}, group_state={group_state}")

        if not group_state:
            # Group disabled - reset to defaults
            if hasattr(dw, 'properties_group_state_reset_to_default'):
                dw.properties_group_state_reset_to_default(
                    properties_tuples, group_key, group_state
                )
            return True

        # Group enabled - update property
        if hasattr(dw, 'properties_group_state_enabler'):
            dw.properties_group_state_enabler(properties_tuples)

        widget_type = widgets.get(
            property_path[0].upper(), {}
        ).get(property_path[1].upper(), {}).get("TYPE")

        current_value = layer_props.get(property_path[0], {}).get(property_path[1])

        if widget_type == 'PushButton':
            return self._update_pushbutton_property(
                property_path, layer_id, project_layers,
                current_value, input_data, custom_functions
            )
        else:
            return self._update_widget_property(
                property_path, layer_id, project_layers,
                current_value, input_data, custom_functions
            )

    def _update_pushbutton_property(
        self,
        property_path: tuple,
        layer_id: str,
        project_layers: Dict,
        current_value: Any,
        input_data: Any,
        custom_functions: Dict
    ) -> bool:
        """
        Update PushButton property.

        Args:
            property_path: Property path tuple
            layer_id: Current layer ID
            project_layers: PROJECT_LAYERS dict
            current_value: Current property value
            input_data: New value
            custom_functions: Callbacks dict

        Returns:
            bool: True if value changed
        """
        self.dockwidget

        if current_value == input_data:
            return False

        # Ensure property path exists
        if property_path[0] not in project_layers[layer_id]:
            project_layers[layer_id][property_path[0]] = {}

        project_layers[layer_id][property_path[0]][property_path[1]] = input_data

        if input_data is True:
            if "ON_TRUE" in custom_functions:
                custom_functions["ON_TRUE"](0)

            # Special: refresh layers list when has_layers_to_filter is activated
            if property_path[1] == 'has_layers_to_filter':
                self._refresh_layers_to_filter()

        elif input_data is False:
            if "ON_FALSE" in custom_functions:
                custom_functions["ON_FALSE"](0)

        return True

    def _update_widget_property(
        self,
        property_path: tuple,
        layer_id: str,
        project_layers: Dict,
        current_value: Any,
        input_data: Any,
        custom_functions: Dict
    ) -> bool:
        """
        Update non-PushButton widget property.

        Args:
            property_path: Property path tuple
            layer_id: Current layer ID
            project_layers: PROJECT_LAYERS dict
            current_value: Current property value
            input_data: New value
            custom_functions: Callbacks dict

        Returns:
            bool: True if value changed
        """
        # Get value from custom function if available
        if "CUSTOM_DATA" in custom_functions:
            new_value = custom_functions["CUSTOM_DATA"](0)
        else:
            new_value = input_data

        logger.debug(f"_update_widget_property: new={new_value}, old={current_value}")

        if current_value == new_value:
            logger.debug("  Value unchanged, skipping update")
            return False

        # Ensure property path exists
        if property_path[0] not in project_layers[layer_id]:
            project_layers[layer_id][property_path[0]] = {}

        project_layers[layer_id][property_path[0]][property_path[1]] = new_value

        if new_value and "ON_TRUE" in custom_functions:
            custom_functions["ON_TRUE"](0)
        elif not new_value and "ON_FALSE" in custom_functions:
            custom_functions["ON_FALSE"](0)

        if property_path[1] == 'layers_to_filter':
            logger.info(f"  layers_to_filter updated: {new_value}")

        return True

    # ─────────────────────────────────────────────────────────────────
    # Widget Management
    # ─────────────────────────────────────────────────────────────────

    def _disconnect_exploring_widgets(self) -> None:
        """Disconnect exploring widgets during property changes."""
        dw = self.dockwidget
        if not hasattr(dw, 'manageSignal'):
            return

        for widget_path in self._widgets_to_disconnect:
            try:
                dw.manageSignal(widget_path, 'disconnect')
            except Exception as e:
                logger.debug(f"Could not disconnect {widget_path}: {e}")

    def _reconnect_exploring_widgets(self) -> None:
        """Reconnect exploring widgets after property changes."""
        dw = self.dockwidget
        if not hasattr(dw, 'manageSignal'):
            return

        # CRITICAL: Use direct connection for featureChanged signal
        if hasattr(dw, 'widgets') and hasattr(dw, 'exploring_features_changed'):
            widgets = dw.widgets
            picker = widgets.get("EXPLORING", {}).get(
                "SINGLE_SELECTION_FEATURES", {}
            ).get("WIDGET")

            if picker is not None:
                try:
                    picker.featureChanged.disconnect(dw.exploring_features_changed)
                except TypeError:
                    pass
                picker.featureChanged.connect(dw.exploring_features_changed)

        # Reconnect other widgets via manageSignal
        for widget_path in self._widgets_to_disconnect[1:]:  # Skip SINGLE_SELECTION_FEATURES
            try:
                dw.manageSignal(widget_path, 'connect')
            except Exception as e:
                logger.debug(f"Could not reconnect {widget_path}: {e}")

    def _refresh_layers_to_filter(self) -> None:
        """Refresh layers_to_filter combobox."""
        dw = self.dockwidget

        if not hasattr(dw, 'manageSignal'):
            return

        try:
            dw.manageSignal(["FILTERING", "LAYERS_TO_FILTER"], 'disconnect')

            if hasattr(dw, 'filtering_populate_layers_chekableCombobox'):
                # Pass current_layer to ensure it's excluded from the list
                layer = getattr(dw, 'current_layer', None)
                dw.filtering_populate_layers_chekableCombobox(layer)

            dw.manageSignal(
                ["FILTERING", "LAYERS_TO_FILTER"],
                'connect',
                'checkedItemsChanged'
            )
        except Exception as e:
            logger.warning(f"Could not refresh layers_to_filter: {e}")

    # ─────────────────────────────────────────────────────────────────
    # Buffer Styling
    # ─────────────────────────────────────────────────────────────────

    def _update_buffer_style(self, buffer_value: Any) -> None:
        """
        Update buffer spinbox visual style based on value.

        Negative values get distinctive style for erosion mode.

        Args:
            buffer_value: Current buffer value
        """
        dw = self.dockwidget
        spinbox = getattr(dw, 'mQgsDoubleSpinBox_filtering_buffer_value', None)

        if spinbox is None:
            return

        if buffer_value is not None and buffer_value < 0:
            # Negative buffer (erosion) - orange/yellow style
            spinbox.setStyleSheet(self._buffer_erosion_style)
            if hasattr(dw, 'tr'):
                spinbox.setToolTip(
                    dw.tr("Negative buffer (erosion): shrinks polygons inward")
                )
        else:
            # Zero or positive - default style
            spinbox.setStyleSheet("")
            if hasattr(dw, 'tr'):
                spinbox.setToolTip(
                    dw.tr("Buffer value in meters (positive=expand, negative=shrink polygons)")
                )

        self.buffer_style_changed.emit(float(buffer_value) if buffer_value else 0.0)

    def update_buffer_validation(self) -> None:
        """
        Update buffer spinbox validation based on source layer geometry.

        Negative buffers (erosion) only work on polygon/multipolygon geometries.
        For point and line geometries, the minimum value is set to 0 to prevent
        negative buffer input.

        Also checks if centroids are enabled (which converts source to points).
        """
        from qgis.core import QgsWkbTypes

        dw = self.dockwidget
        spinbox = getattr(dw, 'mQgsDoubleSpinBox_filtering_buffer_value', None)

        if spinbox is None:
            return

        # Default: allow negative buffers (for polygons)
        min_value = -1000000.0
        tooltip = "Buffer value in meters (positive=expand, negative=shrink polygons)"

        current_layer = getattr(dw, 'current_layer', None)

        if current_layer is not None:
            try:
                geom_type = current_layer.geometryType()

                # Check if geometry is polygon/multipolygon
                is_polygon = geom_type == QgsWkbTypes.PolygonGeometry

                # Check if centroids are enabled for source layer
                # When using centroids, the source layer becomes points
                use_centroids_source = False
                centroids_checkbox = getattr(dw, 'checkBox_filtering_use_centroids_source_layer', None)
                if centroids_checkbox:
                    use_centroids_source = centroids_checkbox.isChecked()

                if use_centroids_source:
                    # Centroids enabled: source layer is effectively points
                    min_value = 0.0
                    tooltip = (
                        "Buffer value in meters (positive only when centroids are enabled. "
                        "Negative buffers cannot be applied to points)"
                    )

                    # Reset negative value to 0
                    current_value = spinbox.value()
                    if current_value < 0:
                        logger.info("Resetting negative buffer to 0: centroids enabled for source layer")
                        spinbox.setValue(0.0)
                        self._update_project_layers_buffer(dw, current_layer, 0.0)

                    logger.debug("Buffer validation: Centroids enabled, negative buffers disabled")

                elif not is_polygon:
                    # Point or Line geometry: disable negative buffers
                    min_value = 0.0

                    # Get geometry type name for tooltip
                    if geom_type == QgsWkbTypes.PointGeometry:
                        geom_name = "point"
                    elif geom_type == QgsWkbTypes.LineGeometry:
                        geom_name = "line"
                    else:
                        geom_name = "non-polygon"

                    tooltip = (
                        f"Buffer value in meters (positive only for {geom_name} layers. "
                        "Negative buffers only work on polygon layers)"
                    )

                    # Reset negative value to 0
                    current_value = spinbox.value()
                    if current_value < 0:
                        logger.info(f"Resetting negative buffer to 0 for {geom_name} layer: {current_layer.name()}")
                        spinbox.setValue(0.0)
                        self._update_project_layers_buffer(dw, current_layer, 0.0)

                    logger.debug(f"Buffer validation: {geom_name} geometry, minimum set to 0")
                else:
                    logger.debug("Buffer validation: Polygon geometry, negative buffers allowed")

            except Exception as e:
                logger.warning(f"update_buffer_validation: Error checking geometry type: {e}")

        # Apply validation
        spinbox.setMinimum(min_value)

        # Update tooltip (unless it's already in orange/negative mode)
        current_value = spinbox.value()
        if current_value is None or current_value >= 0:
            if hasattr(dw, 'tr'):
                spinbox.setToolTip(dw.tr(tooltip))
            else:
                spinbox.setToolTip(tooltip)

    def _update_project_layers_buffer(self, dw, layer, value: float) -> None:
        """
        Update buffer value in PROJECT_LAYERS dictionary.

        Args:
            dw: Dockwidget reference
            layer: Current layer
            value: New buffer value
        """
        project_layers = getattr(dw, 'PROJECT_LAYERS', None)
        if project_layers and layer and layer.id() in project_layers:
            try:
                project_layers[layer.id()]["filtering"]["buffer_value"] = value
            except (KeyError, TypeError):
                pass  # Structure not as expected

    # =========================================================================
    # Sprint 3: Property Reset and Project Property Methods
    # =========================================================================

    def reset_property_group_to_default(
        self,
        tuple_group: list,
        group_name: str,
        state: bool
    ) -> bool:
        """
        Reset a property group to its default values.

        Migrated from filter_mate_dockwidget.properties_group_state_reset_to_default.

        v4.0 Sprint 3: Full migration from dockwidget.

        Args:
            tuple_group: List of property tuples in the group
            group_name: Name of the property group
            state: Target state (usually False for reset)

        Returns:
            True if reset was performed
        """
        dw = self.dockwidget

        # Guard: widgets must be initialized
        if not getattr(dw, 'widgets_initialized', False):
            return False
        if not getattr(dw, 'has_loaded_layers', False):
            return False

        current_layer = getattr(dw, 'current_layer', None)
        if current_layer is None:
            return False

        widgets = getattr(dw, 'widgets', {})
        project_layers = getattr(dw, 'PROJECT_LAYERS', {})
        project_props = getattr(dw, 'project_props', {})
        layer_properties_dict = getattr(dw, 'layer_properties_tuples_dict', {})
        export_properties_dict = getattr(dw, 'export_properties_tuples_dict', {})

        layer_id = current_layer.id()
        if layer_id not in project_layers:
            return False

        properties_to_save = []

        for i, property_path in enumerate(tuple_group):
            # Skip data-only properties
            if property_path[0].upper() not in widgets:
                continue
            if property_path[1].upper() not in widgets.get(property_path[0].upper(), {}):
                continue

            if state is False:
                widget_info = widgets[property_path[0].upper()][property_path[1].upper()]
                widget_type = widget_info.get("TYPE")
                widget = widget_info.get("WIDGET")

                if widget is None:
                    continue

                # Disconnect signal
                if hasattr(dw, 'manageSignal'):
                    dw.manageSignal([property_path[0].upper(), property_path[1].upper()], 'disconnect')

                # Reset based on property dict type
                if group_name in layer_properties_dict:
                    self._reset_layer_property_widget(
                        widget, widget_type, property_path, layer_id,
                        project_layers, current_layer, state, dw
                    )
                    # Track for persistence
                    if property_path[0] in ("infos", "exploring", "filtering"):
                        value = project_layers[layer_id].get(
                            property_path[0], {}
                        ).get(property_path[1])
                        properties_to_save.append((
                            property_path[0],
                            property_path[1],
                            value,
                            type(value)
                        ))

                elif group_name in export_properties_dict:
                    self._reset_export_property_widget(
                        widget, widget_type, property_path,
                        project_props, state, dw
                    )

                # Reconnect signal
                if hasattr(dw, 'manageSignal'):
                    dw.manageSignal([property_path[0].upper(), property_path[1].upper()], 'connect')

            # Handle widget enabled state
            if i == 0 and property_path[1].upper().find('HAS') >= 0:
                widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setEnabled(True)
            else:
                widgets[property_path[0].upper()][property_path[1].upper()]["WIDGET"].setEnabled(state)

        # Persist reset properties to database
        if state is False and properties_to_save:
            self._persist_reset_properties(current_layer, properties_to_save, dw)

        return True

    def _reset_layer_property_widget(
        self,
        widget,
        widget_type: str,
        property_path: tuple,
        layer_id: str,
        project_layers: dict,
        current_layer,
        state: bool,
        dw
    ) -> None:
        """
        Reset a layer property widget to its default value.

        Args:
            widget: The widget to reset
            widget_type: Type of widget
            property_path: Property path tuple
            layer_id: Current layer ID
            project_layers: PROJECT_LAYERS dict
            current_layer: Current layer reference
            state: Target state
            dw: Dockwidget reference
        """
        try:
            if widget_type == 'PushButton':
                widget.setChecked(state)
                project_layers[layer_id][property_path[0]][property_path[1]] = widget.isChecked()

            elif widget_type == 'CheckableComboBox':
                widget.deselectAllOptions()
                project_layers[layer_id][property_path[0]][property_path[1]] = widget.checkedItems()

            elif widget_type == 'ComboBox':
                widget.setCurrentIndex(0)
                project_layers[layer_id][property_path[0]][property_path[1]] = widget.currentText()

            elif widget_type == 'QgsFieldExpressionWidget':
                if current_layer is not None:
                    widget.setLayer(current_layer)
                pk_name = project_layers[layer_id].get("infos", {}).get("primary_key_name", "")
                widget.setField(pk_name)
                project_layers[layer_id][property_path[0]][property_path[1]] = widget.expression()

            elif widget_type == 'QgsDoubleSpinBox':
                widget.clearValue()
                project_layers[layer_id][property_path[0]][property_path[1]] = widget.value()

            elif widget_type == 'LineEdit':
                widget.setText('')
                project_layers[layer_id][property_path[0]][property_path[1]] = widget.text()

            elif widget_type == 'QgsProjectionSelectionWidget':
                project = getattr(dw, 'PROJECT', None)
                if project:
                    widget.setCrs(project.crs())
                    project_layers[layer_id][property_path[0]][property_path[1]] = widget.crs().authid()

            elif widget_type == 'PropertyOverrideButton':
                widget.setActive(False)
                project_layers[layer_id][property_path[0]][property_path[1]] = False

        except Exception as e:
            logger.warning(f"Error resetting layer property {property_path}: {e}")

    def _reset_export_property_widget(
        self,
        widget,
        widget_type: str,
        property_path: tuple,
        project_props: dict,
        state: bool,
        dw
    ) -> None:
        """
        Reset an export property widget to its default value.

        Args:
            widget: The widget to reset
            widget_type: Type of widget
            property_path: Property path tuple
            project_props: Project properties dict
            state: Target state
            dw: Dockwidget reference
        """
        try:
            key_upper = property_path[0].upper()
            prop_upper = property_path[1].upper()

            if widget_type == 'PushButton':
                widget.setChecked(state)
                project_props[key_upper][prop_upper] = widget.isChecked()

            elif widget_type == 'CheckBox':
                widget.setChecked(state)
                project_props[key_upper][prop_upper] = widget.isChecked()

            elif widget_type == 'CheckableComboBox':
                widget.deselectAllOptions()
                project_props[key_upper][prop_upper] = widget.checkedItems()

            elif widget_type == 'ComboBox':
                index = widget.findText('GPKG')
                if index < 0:
                    index = 0
                widget.setCurrentIndex(index)
                project_props[key_upper][prop_upper] = widget.currentText()

            elif widget_type == 'QgsDoubleSpinBox':
                widget.clearValue()
                project_props[key_upper][prop_upper] = widget.value()

            elif widget_type == 'LineEdit':
                widget.setText('')
                project_props[key_upper][prop_upper] = widget.text()

            elif widget_type == 'QgsProjectionSelectionWidget':
                project = getattr(dw, 'PROJECT', None)
                if project:
                    widget.setCrs(project.crs())
                    project_props[key_upper][prop_upper] = widget.crs().authid()

            elif widget_type == 'PropertyOverrideButton':
                widget.setActive(False)
                project_props[key_upper][prop_upper] = False

        except Exception as e:
            logger.warning(f"Error resetting export property {property_path}: {e}")

    def _persist_reset_properties(
        self,
        current_layer,
        properties_to_save: list,
        dw
    ) -> None:
        """
        Persist reset properties to database.

        Args:
            current_layer: Current layer
            properties_to_save: List of property tuples to save
            dw: Dockwidget reference
        """
        app = getattr(dw, 'app', None)
        if not app or not properties_to_save:
            return

        try:
            logger.debug(
                f"💾 Persisting {len(properties_to_save)} reset properties "
                f"for layer {current_layer.name()}"
            )
            app.save_variables_from_layer(current_layer, properties_to_save)
        except Exception as e:
            logger.warning(f"Failed to persist reset properties to DB: {e}")

    def change_project_property(
        self,
        input_property: str,
        input_data: Any = None,
        custom_functions: Optional[Dict[str, Callable]] = None
    ) -> bool:
        """
        Handle property changes for project-level (export) properties.

        Migrated from filter_mate_dockwidget.project_property_changed.

        v4.0 Sprint 3: Full migration from dockwidget.

        Args:
            input_property: Property identifier string
            input_data: New value
            custom_functions: Optional callbacks dict

        Returns:
            True if property was changed
        """
        if custom_functions is None:
            custom_functions = {}

        dw = self.dockwidget

        # Guard: widgets must be initialized
        if not getattr(dw, 'widgets_initialized', False):
            return False
        if not getattr(dw, 'has_loaded_layers', False):
            return False

        project_props = getattr(dw, 'project_props', None)
        export_properties_dict = getattr(dw, 'export_properties_tuples_dict', {})
        widgets = getattr(dw, 'widgets', {})

        if project_props is None:
            return False

        # Parse input data
        parsed_data, state = self._parse_property_data(input_data)

        # Find property path in export properties
        properties_group_key = None
        property_path = None
        properties_tuples = None

        for key, tuples in export_properties_dict.items():
            if input_property.find(key) >= 0:
                properties_group_key = key
                properties_tuples = tuples
                for i, prop_tuple in enumerate(tuples):
                    if prop_tuple[1] == input_property:
                        property_path = prop_tuple
                        break
                break

        if property_path is None or properties_tuples is None:
            logger.warning(f"change_project_property: property '{input_property}' not found")
            return False

        # Get group enabled state
        group_property = properties_tuples[0]
        group_widget = widgets.get(
            group_property[0].upper(), {}
        ).get(group_property[1].upper(), {}).get("WIDGET")

        group_state = group_widget.isChecked() if group_widget else True

        flag_value_changed = False

        if not group_state:
            # Group disabled - reset to defaults
            self.reset_property_group_to_default(
                properties_tuples, properties_group_key, group_state
            )
            flag_value_changed = True
        else:
            # Group enabled - enable widgets
            if hasattr(dw, 'properties_group_state_enabler'):
                dw.properties_group_state_enabler(properties_tuples)

            widget_info = widgets.get(
                property_path[0].upper(), {}
            ).get(property_path[1].upper(), {})
            widget_type = widget_info.get("TYPE")

            key_upper = property_path[0].upper()
            prop_upper = property_path[1].upper()
            current_value = project_props.get(key_upper, {}).get(prop_upper)

            if widget_type == 'PushButton':
                if current_value != parsed_data:
                    project_props[key_upper][prop_upper] = parsed_data
                    flag_value_changed = True

                    if parsed_data is True and "ON_TRUE" in custom_functions:
                        custom_functions["ON_TRUE"](0)
                    elif parsed_data is False and "ON_FALSE" in custom_functions:
                        custom_functions["ON_FALSE"](0)
            else:
                # Non-PushButton widgets
                new_value = custom_functions.get("CUSTOM_DATA", lambda x: parsed_data)(0)

                if current_value != new_value:
                    project_props[key_upper][prop_upper] = new_value
                    flag_value_changed = True

                    # FIX 2026-01-16: Auto-enable HAS_LAYERS_TO_EXPORT when layers are selected
                    if input_property == 'layers_to_export' and isinstance(new_value, list):
                        has_layers = len(new_value) > 0
                        current_has_layers = project_props.get('EXPORTING', {}).get('HAS_LAYERS_TO_EXPORT')
                        if current_has_layers != has_layers:
                            project_props['EXPORTING']['HAS_LAYERS_TO_EXPORT'] = has_layers
                            logger.info(f"Auto-set HAS_LAYERS_TO_EXPORT = {has_layers} (based on {len(new_value)} selected layers)")

                            # Update the button widget state
                            has_layers_widget = widgets.get('EXPORTING', {}).get('HAS_LAYERS_TO_EXPORT', {}).get('WIDGET')
                            if has_layers_widget and hasattr(has_layers_widget, 'setChecked'):
                                has_layers_widget.blockSignals(True)
                                has_layers_widget.setChecked(has_layers)
                                has_layers_widget.blockSignals(False)

                    if new_value and "ON_TRUE" in custom_functions:
                        custom_functions["ON_TRUE"](0)
                    elif not new_value and "ON_FALSE" in custom_functions:
                        custom_functions["ON_FALSE"](0)

        # Trigger change callbacks
        if flag_value_changed:
            if "ON_CHANGE" in custom_functions:
                custom_functions["ON_CHANGE"](0)

            # Update config
            config_data = getattr(dw, 'CONFIG_DATA', {})
            if 'CURRENT_PROJECT' in config_data:
                config_data['CURRENT_PROJECT']['EXPORTING'] = project_props.get('EXPORTING', {})

            # Set project variables
            if hasattr(dw, 'setProjectVariablesEvent'):
                dw.setProjectVariablesEvent()

        return flag_value_changed

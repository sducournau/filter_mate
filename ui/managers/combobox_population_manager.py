# -*- coding: utf-8 -*-
"""
ComboboxPopulationManager - Extracted from filter_mate_dockwidget.py

v5.0 Phase 2 P2-2 E3: Extract combobox population logic
from God Class (6,906 lines).

Manages:
    - Filtering predicates combobox population
    - Filtering buffer type combobox population
    - Filtering layers-to-filter combobox population (with controller + direct fallback)
    - Exporting layers combobox population (with controller + direct fallback)
    - Direct population methods for export and filtering comboboxes

Note: _on_project_layers_ready remains in the dockwidget as an orchestrator
that calls these population methods.

Author: FilterMate Team
Created: February 2026
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class ComboboxPopulationManager:
    """
    Manages combobox population for filtering and exporting tabs.

    Extracted from FilterMateDockWidget to reduce God Class complexity.
    Handles predicates, buffer types, layer lists for both filtering
    and exporting, with controller delegation and direct fallbacks.

    Args:
        dockwidget: Reference to FilterMateDockWidget instance.
    """

    def __init__(self, dockwidget: 'FilterMateDockWidget'):
        self.dockwidget = dockwidget
        logger.debug("ComboboxPopulationManager initialized")

    # ========================================
    # FILTERING PREDICATES & BUFFER TYPE
    # ========================================

    def filtering_populate_predicates_checkable_combobox(self):
        """Populate geometric predicates combobox."""
        dw = self.dockwidget
        try:
            predicates = (
                dw._controller_integration.delegate_filtering_get_available_predicates()
                if dw._controller_integration else None
            )
            dw.predicates = predicates or [
                "Intersect", "Contain", "Disjoint", "Equal",
                "Touch", "Overlap", "Are within", "Cross",
            ]
            logger.info(
                f"filtering_populate_predicates: predicates={dw.predicates}"
            )

            # Get widget from configuration with fallbacks
            if not hasattr(dw, 'widgets') or dw.widgets is None:
                logger.error("self.widgets is None or not initialized!")
                w = dw.comboBox_filtering_geometric_predicates
            elif "FILTERING" not in dw.widgets:
                logger.error("'FILTERING' not in self.widgets!")
                w = dw.comboBox_filtering_geometric_predicates
            elif "GEOMETRIC_PREDICATES" not in dw.widgets["FILTERING"]:
                logger.error(
                    "'GEOMETRIC_PREDICATES' not in self.widgets['FILTERING']!"
                )
                w = dw.comboBox_filtering_geometric_predicates
            else:
                w = dw.widgets["FILTERING"]["GEOMETRIC_PREDICATES"]["WIDGET"]

            logger.info(
                f"Widget type: {type(w).__name__}, count before: {w.count()}"
            )
            w.clear()

            for pred in dw.predicates:
                w.addItem(pred)

            logger.info(
                f"Widget count after addItems: {w.count()}, "
                f"items: {[w.itemText(i) for i in range(w.count())]}"
            )

        except Exception as e:
            logger.error(
                f"filtering_populate_predicates FAILED: {e}", exc_info=True
            )
            # Fallback: try direct widget access
            try:
                w = dw.comboBox_filtering_geometric_predicates
                w.clear()
                w.addItems([
                    "Intersect", "Contain", "Disjoint", "Equal",
                    "Touch", "Overlap", "Are within", "Cross",
                ])
                logger.info(f"Fallback succeeded, widget count: {w.count()}")
            except Exception as e2:
                logger.error(f"Fallback also failed: {e2}", exc_info=True)

    def filtering_populate_buffer_type_combobox(self):
        """Populate buffer type combobox."""
        dw = self.dockwidget
        buffer_types = (
            dw._controller_integration.delegate_filtering_get_available_buffer_types()
            if dw._controller_integration else None
        )
        w = dw.widgets["FILTERING"]["BUFFER_TYPE"]["WIDGET"]
        w.clear()
        w.addItems(buffer_types or ["Round", "Flat", "Square"])
        if not w.currentText():
            w.setCurrentIndex(0)

    # ========================================
    # FILTERING LAYERS POPULATION
    # ========================================

    def filtering_populate_layers_checkable_combobox(self, layer=None):
        """Populate layers-to-filter combobox.

        Tries controller delegation first, falls back to direct method.
        """
        dw = self.dockwidget
        logger.info(
            f"filtering_populate_layers called for layer: "
            f"{layer.name() if layer else 'None'}"
        )
        logger.info(
            f"  widgets_initialized={dw.widgets_initialized}, "
            f"_controller_integration={dw._controller_integration is not None}"
        )
        logger.info(
            f"  PROJECT_LAYERS count="
            f"{len(dw.PROJECT_LAYERS) if dw.PROJECT_LAYERS else 0}"
        )

        success = False

        # Try controller delegation first
        if dw.widgets_initialized and dw._controller_integration:
            result = dw._controller_integration.delegate_populate_layers_checkable_combobox(
                layer
            )
            logger.info(f"  Controller delegation returned: {result}")
            if result:
                success = True
                # Force visual refresh
                if (
                    "FILTERING" in dw.widgets
                    and "LAYERS_TO_FILTER" in dw.widgets["FILTERING"]
                ):
                    widget = dw.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"]
                    if widget:
                        logger.info(
                            f"  Widget count after controller: {widget.count()}"
                        )
                        widget.update()
                        widget.repaint()

        # FALLBACK: Use direct method if controller failed
        if not success:
            logger.warning(
                "Controller delegation failed - using direct fallback"
            )
            try:
                dw.manageSignal(
                    ["FILTERING", "LAYERS_TO_FILTER"], 'disconnect'
                )
                target_layer = layer or dw.current_layer
                if target_layer:
                    result = self.populate_filtering_layers_direct(target_layer)
                    logger.info(f"  Direct fallback returned: {result}")
                    if (
                        "FILTERING" in dw.widgets
                        and "LAYERS_TO_FILTER" in dw.widgets["FILTERING"]
                    ):
                        widget = dw.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"]
                        if widget:
                            logger.info(
                                f"  Widget count after direct: {widget.count()}"
                            )
                else:
                    logger.warning("No layer available for direct population")
                dw.manageSignal(
                    ["FILTERING", "LAYERS_TO_FILTER"],
                    'connect',
                    'checkedItemsChanged',
                )
            except Exception as e:
                logger.error(
                    f"Direct fallback failed: {e}", exc_info=True
                )

    # ========================================
    # EXPORTING LAYERS POPULATION
    # ========================================

    def exporting_populate_combobox(self):
        """Populate export layers combobox.

        Tries controller delegation first, falls back to direct method.
        """
        dw = self.dockwidget
        logger.info("exporting_populate_combobox called")
        logger.info(
            f"  _controller_integration="
            f"{dw._controller_integration is not None}"
        )
        logger.info(
            f"  PROJECT_LAYERS count="
            f"{len(dw.PROJECT_LAYERS) if dw.PROJECT_LAYERS else 0}"
        )

        success = False

        # Try controller delegation first
        if dw._controller_integration:
            result = dw._controller_integration.delegate_populate_export_combobox()
            logger.info(f"  Controller delegation returned: {result}")
            if result:
                success = True
                if (
                    "EXPORTING" in dw.widgets
                    and "LAYERS_TO_EXPORT" in dw.widgets["EXPORTING"]
                ):
                    widget = dw.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"]
                    if widget:
                        logger.info(
                            f"  Widget count after controller: {widget.count()}"
                        )

        # FALLBACK: Use direct method if controller failed
        if not success:
            logger.warning(
                "Controller delegation failed - using direct fallback"
            )
            try:
                dw.manageSignal(
                    ["EXPORTING", "LAYERS_TO_EXPORT"], 'disconnect'
                )
                result = self.populate_export_combobox_direct()
                logger.info(f"  Direct fallback returned: {result}")
                if (
                    "EXPORTING" in dw.widgets
                    and "LAYERS_TO_EXPORT" in dw.widgets["EXPORTING"]
                ):
                    widget = dw.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"]
                    if widget:
                        logger.info(
                            f"  Widget count after direct: {widget.count()}"
                        )
                dw.manageSignal(
                    ["EXPORTING", "LAYERS_TO_EXPORT"],
                    'connect',
                    'checkedItemsChanged',
                )
            except Exception as e:
                logger.error(
                    f"Direct fallback failed: {e}", exc_info=True
                )

    # ========================================
    # DIRECT POPULATION METHODS (FALLBACKS)
    # ========================================

    def populate_export_combobox_direct(self) -> bool:
        """Direct population of export combobox without controller dependency.

        Fallback method that populates the combobox directly, bypassing
        the controller integration which may not be initialized.

        Returns:
            True if population succeeded, False otherwise.
        """
        dw = self.dockwidget
        try:
            from qgis.core import QgsVectorLayer, QgsProject
            from qgis.PyQt.QtCore import Qt

            if not dw.widgets_initialized:
                logger.warning("populate_export_direct: widgets not initialized")
                return False
            if not dw.PROJECT_LAYERS:
                logger.warning("populate_export_direct: PROJECT_LAYERS empty")
                return False

            logger.info(
                f"populate_export_direct: PROJECT_LAYERS has "
                f"{len(dw.PROJECT_LAYERS)} layers"
            )

            # Get saved preferences
            layers_to_export = []
            datatype_to_export = ''
            if dw.project_props.get('EXPORTING', {}).get('HAS_LAYERS_TO_EXPORT'):
                layers_to_export = dw.project_props['EXPORTING'].get(
                    'LAYERS_TO_EXPORT', []
                )
            if dw.project_props.get('EXPORTING', {}).get('HAS_DATATYPE_TO_EXPORT'):
                datatype_to_export = dw.project_props['EXPORTING'].get(
                    'DATATYPE_TO_EXPORT', ''
                )

            # Import validation
            try:
                from ...infrastructure.utils.validation_utils import (
                    is_layer_source_available,
                )
            except ImportError:
                def is_layer_source_available(layer, require_psycopg2=False):
                    return layer.isValid()

            project = QgsProject.instance()

            # Clear and populate layers widget
            layers_widget = dw.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"]
            layers_widget.clear()
            item_index = 0

            for key in list(dw.PROJECT_LAYERS.keys()):
                if key not in dw.PROJECT_LAYERS or "infos" not in dw.PROJECT_LAYERS[key]:
                    continue

                layer_info = dw.PROJECT_LAYERS[key]["infos"]
                required_keys = [
                    "layer_id", "layer_name",
                    "layer_crs_authid", "layer_geometry_type",
                ]
                if any(
                    k not in layer_info or layer_info[k] is None
                    for k in required_keys
                ):
                    continue

                layer_id = layer_info["layer_id"]
                layer_name = layer_info["layer_name"]
                layer_crs_authid = layer_info["layer_crs_authid"]
                geom_type = layer_info["layer_geometry_type"]
                layer_icon = dw.icon_per_geometry_type(geom_type)

                # Validate layer
                layer_obj = project.mapLayer(layer_id)
                if (
                    layer_obj
                    and isinstance(layer_obj, QgsVectorLayer)
                    and is_layer_source_available(
                        layer_obj, require_psycopg2=False
                    )
                ):
                    display_name = f"{layer_name} [{layer_crs_authid}]"
                    item_data = {
                        "layer_id": key,
                        "layer_geometry_type": geom_type,
                    }
                    layers_widget.addItem(layer_icon, display_name, item_data)
                    item = layers_widget.model().item(item_index)
                    item.setCheckState(
                        Qt.Checked if key in layers_to_export else Qt.Unchecked
                    )
                    item_index += 1

            logger.info(
                f"populate_export_direct: Added {item_index} layers to combobox"
            )

            # Populate datatype/format combobox
            try:
                from osgeo import ogr
                datatype_widget = dw.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"]
                datatype_widget.clear()
                ogr_driver_list = sorted([
                    ogr.GetDriver(i).GetDescription()
                    for i in range(ogr.GetDriverCount())
                ])
                datatype_widget.addItems(ogr_driver_list)
                logger.info(
                    f"populate_export_direct: Added {len(ogr_driver_list)} "
                    f"export formats"
                )

                if datatype_to_export:
                    idx = datatype_widget.findText(datatype_to_export)
                    datatype_widget.setCurrentIndex(
                        idx if idx >= 0 else datatype_widget.findText('GPKG')
                    )
                else:
                    datatype_widget.setCurrentIndex(
                        datatype_widget.findText('GPKG')
                    )
            except ImportError:
                logger.warning("populate_export_direct: OGR not available")

            return item_index > 0

        except Exception as e:
            logger.error(
                f"populate_export_direct failed: {e}", exc_info=True
            )
            return False

    def populate_filtering_layers_direct(self, layer) -> bool:
        """Direct population of filtering layers combobox without controller.

        Args:
            layer: Source layer for which to populate target layers.

        Returns:
            True if population succeeded, False otherwise.
        """
        dw = self.dockwidget
        try:
            from qgis.core import QgsVectorLayer, QgsProject
            from qgis.PyQt.QtCore import Qt

            if not dw.widgets_initialized:
                logger.warning(
                    "populate_filtering_direct: widgets not initialized"
                )
                return False
            if not dw.PROJECT_LAYERS:
                logger.warning(
                    "populate_filtering_direct: PROJECT_LAYERS empty"
                )
                return False
            if not layer or not isinstance(layer, QgsVectorLayer):
                logger.warning(
                    "populate_filtering_direct: invalid layer"
                )
                return False
            if layer.id() not in dw.PROJECT_LAYERS:
                logger.warning(
                    f"populate_filtering_direct: layer {layer.name()} "
                    f"not in PROJECT_LAYERS"
                )
                return False

            logger.info(
                f"populate_filtering_direct: PROJECT_LAYERS has "
                f"{len(dw.PROJECT_LAYERS)} layers"
            )

            # Import validation
            try:
                from ...infrastructure.utils.validation_utils import (
                    is_layer_source_available,
                )
            except ImportError:
                def is_layer_source_available(layer, require_psycopg2=False):
                    return layer.isValid()

            layer_props = dw.PROJECT_LAYERS[layer.id()]
            project = QgsProject.instance()

            # Get saved layers to filter
            has_layers = layer_props.get("filtering", {}).get(
                "has_layers_to_filter", False
            )
            layers_to_filter = layer_props.get("filtering", {}).get(
                "layers_to_filter", []
            )

            # Remove source layer from targets if present
            source_layer_id = layer.id()
            if source_layer_id in layers_to_filter:
                layers_to_filter = [
                    lid for lid in layers_to_filter if lid != source_layer_id
                ]

            # Clear and populate widget
            layers_widget = dw.widgets["FILTERING"]["LAYERS_TO_FILTER"]["WIDGET"]
            layers_widget.clear()
            item_index = 0

            for key in list(dw.PROJECT_LAYERS.keys()):
                # Skip source layer
                if key == layer.id():
                    continue

                if (
                    key not in dw.PROJECT_LAYERS
                    or "infos" not in dw.PROJECT_LAYERS[key]
                ):
                    continue

                layer_info = dw.PROJECT_LAYERS[key]["infos"]
                required_keys = [
                    "layer_id", "layer_name",
                    "layer_crs_authid", "layer_geometry_type",
                ]
                if any(
                    k not in layer_info or layer_info[k] is None
                    for k in required_keys
                ):
                    continue

                layer_id = layer_info["layer_id"]
                layer_name = layer_info["layer_name"]
                layer_crs = layer_info["layer_crs_authid"]
                geom_type = layer_info["layer_geometry_type"]
                layer_icon = dw.icon_per_geometry_type(geom_type)

                # Validate layer
                layer_obj = project.mapLayer(layer_id)
                if not layer_obj or not isinstance(layer_obj, QgsVectorLayer):
                    continue
                # Skip non-spatial tables
                if not layer_obj.isSpatial():
                    continue
                if not is_layer_source_available(
                    layer_obj, require_psycopg2=False
                ):
                    continue

                # Add to combobox
                display_name = f"{layer_name} [{layer_crs}]"
                item_data = {
                    "layer_id": key,
                    "layer_geometry_type": geom_type,
                }
                layers_widget.addItem(layer_icon, display_name, item_data)

                item = layers_widget.model().item(item_index)
                if has_layers and layer_id in layers_to_filter:
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)
                item_index += 1

            logger.info(
                f"populate_filtering_direct: Added {item_index} layers "
                f"(source '{layer.name()}' excluded)"
            )
            return item_index > 0

        except Exception as e:
            logger.error(
                f"populate_filtering_direct failed: {e}", exc_info=True
            )
            return False

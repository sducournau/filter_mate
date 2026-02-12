# -*- coding: utf-8 -*-
"""
ExportDialogManager - Extracted from filter_mate_dockwidget.py

v5.0 Phase 2 P2-2 E4: Extract export dialog and path management
from God Class (6,586 lines).

Manages:
    - Export output path dialog and reset
    - Zip export path dialog and reset
    - Export buttons state update
    - Widget value setting for export properties
    - Export properties setup from project state

Author: FilterMate Team
Created: February 2026
"""

import os
import re
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class ExportDialogManager:
    """
    Manages export dialogs, paths, and export property setup for FilterMate.

    Extracted from FilterMateDockWidget to reduce God Class complexity.
    Handles file dialogs for export output paths, zip paths,
    widget value setting, and export property synchronization.

    Args:
        dockwidget: Reference to FilterMateDockWidget instance.
    """

    def __init__(self, dockwidget: 'FilterMateDockWidget'):
        self.dockwidget = dockwidget
        logger.debug("ExportDialogManager initialized")

    # ========================================
    # EXPORT OUTPUT PATH DIALOGS
    # ========================================

    def dialog_export_output_path(self):
        """Open file dialog for export output path.

        Shows save dialog for single layer + datatype, or folder dialog
        for multiple layers. Updates widget text and project properties.
        """
        from qgis.PyQt import QtWidgets
        dw = self.dockwidget
        if not dw._is_ui_ready():
            return
        path = ''
        state = dw.widgets["EXPORTING"]["HAS_OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].isChecked()
        datatype = (
            dw.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"].currentText()
            if dw.widgets["EXPORTING"]["HAS_DATATYPE_TO_EXPORT"]["WIDGET"].isChecked()
            else ''
        )

        if state:
            if dw.widgets["EXPORTING"]["HAS_LAYERS_TO_EXPORT"]["WIDGET"].isChecked():
                layers = dw.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"].checkedItems()
                if len(layers) == 1 and datatype:
                    layer = layers[0]
                    match = re.search('.* ', layer)
                    layer = match.group() if match else layer
                    path = str(QtWidgets.QFileDialog.getSaveFileName(
                        dw,
                        'Save your layer to a file',
                        os.path.join(
                            dw.current_project_path,
                            dw.output_name + '_' + layer.strip()
                        ),
                        f'*.{datatype}'
                    )[0])
                elif datatype.upper() == 'GPKG':
                    path = str(QtWidgets.QFileDialog.getSaveFileName(
                        dw,
                        'Save your layer to a file',
                        os.path.join(
                            dw.current_project_path,
                            dw.output_name + '.gpkg'
                        ),
                        '*.gpkg'
                    )[0])
                else:
                    path = str(QtWidgets.QFileDialog.getExistingDirectory(
                        dw,
                        'Select a folder where to export your layers',
                        dw.current_project_path
                    ))
            else:
                path = str(QtWidgets.QFileDialog.getExistingDirectory(
                    dw,
                    'Select a folder where to export your layers',
                    dw.current_project_path
                ))

            if path:
                dw.widgets["EXPORTING"]["OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].setText(
                    os.path.normcase(path)
                )
            else:
                state = False
                dw.widgets["EXPORTING"]["OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].clear()
        else:
            dw.widgets["EXPORTING"]["OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].clear()

        dw.project_property_changed('has_output_folder_to_export', state)
        dw.project_property_changed('output_folder_to_export', path)

    def reset_export_output_path(self):
        """Reset export output path widget and project property."""
        dw = self.dockwidget
        if (
            not dw.widgets_initialized
            or not dw.has_loaded_layers
            or dw.widgets["EXPORTING"]["OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].text()
        ):
            return
        dw.widgets["EXPORTING"]["OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].clear()
        dw.widgets["EXPORTING"]["HAS_OUTPUT_FOLDER_TO_EXPORT"]["WIDGET"].setChecked(False)
        dw.project_property_changed('has_output_folder_to_export', False)
        dw.project_property_changed('output_folder_to_export', '')

    # ========================================
    # ZIP EXPORT PATH DIALOGS
    # ========================================

    def dialog_export_output_pathzip(self):
        """Open file dialog for zip export path.

        Shows save dialog for .zip file, updates widget text
        and project properties.
        """
        from qgis.PyQt import QtWidgets
        dw = self.dockwidget
        if not dw._is_ui_ready():
            return
        path = ''
        state = dw.widgets["EXPORTING"]["HAS_ZIP_TO_EXPORT"]["WIDGET"].isChecked()
        if state:
            path = str(QtWidgets.QFileDialog.getSaveFileName(
                dw,
                'Save your exported data to a zip file',
                os.path.join(dw.current_project_path, dw.output_name),
                '*.zip'
            )[0])
            if path:
                dw.widgets["EXPORTING"]["ZIP_TO_EXPORT"]["WIDGET"].setText(
                    os.path.normcase(path)
                )
            else:
                state = False
                dw.widgets["EXPORTING"]["ZIP_TO_EXPORT"]["WIDGET"].clear()
        else:
            dw.widgets["EXPORTING"]["ZIP_TO_EXPORT"]["WIDGET"].clear()
        dw.project_property_changed('has_zip_to_export', state)
        dw.project_property_changed('zip_to_export', path)

    def reset_export_output_pathzip(self):
        """Reset zip export path widget and project property."""
        dw = self.dockwidget
        if (
            not dw.widgets_initialized
            or not dw.has_loaded_layers
            or dw.widgets["EXPORTING"]["ZIP_TO_EXPORT"]["WIDGET"].text()
        ):
            return
        dw.widgets["EXPORTING"]["ZIP_TO_EXPORT"]["WIDGET"].clear()
        dw.widgets["EXPORTING"]["HAS_ZIP_TO_EXPORT"]["WIDGET"].setChecked(False)
        dw.project_property_changed('has_zip_to_export', False)
        dw.project_property_changed('zip_to_export', '')

    # ========================================
    # EXPORT PROPERTIES SETUP
    # ========================================

    def set_exporting_properties(self):
        """Set exporting widgets from project properties.

        Iterates over export_properties_tuples_dict, enabling/disabling
        widget groups and setting their values from project_props.
        Disconnects/reconnects signals during batch updates.
        """
        dw = self.dockwidget
        if not dw._is_ui_ready():
            return

        widgets_to_stop = [
            ["EXPORTING", w] for w in [
                "HAS_LAYERS_TO_EXPORT", "HAS_PROJECTION_TO_EXPORT",
                "HAS_STYLES_TO_EXPORT", "HAS_DATATYPE_TO_EXPORT",
                "LAYERS_TO_EXPORT", "PROJECTION_TO_EXPORT",
                "STYLES_TO_EXPORT", "DATATYPE_TO_EXPORT",
            ]
        ]

        for wp in widgets_to_stop:
            dw.manageSignal(wp, 'disconnect')

        for group_key, properties_tuples in dw.export_properties_tuples_dict.items():
            group_state = dw.widgets[
                properties_tuples[0][0].upper()
            ][
                properties_tuples[0][1].upper()
            ]["WIDGET"].isChecked()

            if not group_state:
                dw.properties_group_state_reset_to_default(
                    properties_tuples, group_key, group_state
                )
            else:
                dw.properties_group_state_enabler(properties_tuples)
                for prop_path in properties_tuples:
                    key0 = prop_path[0].upper()
                    key1 = prop_path[1].upper()
                    if key0 not in dw.widgets or key1 not in dw.widgets.get(key0, {}):
                        continue
                    w = dw.widgets[key0][key1]
                    val = dw.project_props.get(key0, {}).get(key1)
                    self._set_widget_value(w, val, prop_path[1])

        for wp in widgets_to_stop:
            dw.manageSignal(wp, 'connect')
        dw.CONFIG_DATA["CURRENT_PROJECT"]['EXPORTING'] = dw.project_props['EXPORTING']

    def _set_widget_value(self, widget_data, value, prop_name=None):
        """Set widget value based on widget type.

        Handles PushButton, CheckBox, CheckableComboBox, ComboBox,
        QgsDoubleSpinBox, LineEdit, and QgsProjectionSelectionWidget.

        Args:
            widget_data: Dict with 'WIDGET' and 'TYPE' keys.
            value: The value to set on the widget.
            prop_name: Optional property name for special handling.
        """
        from qgis.core import QgsCoordinateReferenceSystem
        w = widget_data["WIDGET"]
        wt = widget_data["TYPE"]
        if wt in ('PushButton', 'CheckBox'):
            w.setChecked(value)
        elif wt == 'CheckableComboBox':
            w.setCheckedItems(value)
        elif wt == 'ComboBox':
            w.setCurrentIndex(w.findText(value))
        elif wt == 'QgsDoubleSpinBox':
            w.setValue(value)
        elif wt == 'LineEdit':
            if not value and prop_name == 'output_folder_to_export':
                self.reset_export_output_path()
            elif not value and prop_name == 'zip_to_export':
                self.reset_export_output_pathzip()
            else:
                w.setText(value)
        elif wt == 'QgsProjectionSelectionWidget':
            crs = QgsCoordinateReferenceSystem(value)
            if crs.isValid():
                w.setCrs(crs)

    # ========================================
    # EXPORT BUTTONS STATE
    # ========================================

    def update_export_buttons_state(self):
        """Update export buttons based on layer selection.

        NOTE: pushButton_checkable_exporting_output_folder and
        pushButton_checkable_exporting_zip are ALWAYS enabled
        (can be checked/unchecked anytime). They are excluded
        from this logic. Only their associated widgets should be
        controlled by toggle state.
        """
        # These buttons are always enabled - no state update needed here
        # The toggle state controls their associated widgets, not the buttons
        pass

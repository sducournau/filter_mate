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
from .config import *
import os
from functools import partial
from qgis.PyQt import QtGui, QtWidgets, uic
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *
from qgis.utils import iface
from qgis.PyQt.QtWidgets import QApplication, QVBoxLayout


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'filter_mate_dockwidget_base.ui'))


class FilterMateDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()
    launchingTask = pyqtSignal(str)

    gettingProjectLayers = pyqtSignal()
    settingProjectLayers = pyqtSignal(dict)

    def __init__(self, project_layers, parent=None):
        """Constructor."""
        super(FilterMateDockWidget, self).__init__(parent)
        
        self.iface = iface
        self.PROJECT_LAYERS = project_layers
        self.tabTools_current_index = 0
        self.tabWidgets_current_index = 0

        self.current_layer = self.iface.activeLayer()
        self.current_exploring_groupbox = None
        self.auto_change_current_layer_flag = False
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://doc.qt.io/qt-5/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.setupUiCustom()
        self.manage_ui_icons()
        self.manage_ui_style()
        self.manage_interactions()
        self.manage_output_name()

    def setupUiCustom(self):
        self.customCheckableComboBox_exploring_multiple_selection = QgsCustomCheckableListWidget(self)
        self.layout = self.verticalLayout_exploring_multiple_selection
        self.layout.insertWidget(0, self.customCheckableComboBox_exploring_multiple_selection)

        self.exploring_groupbox_init()


    def manage_output_name(self):
        self.output_name = 'export'
        self.current_project_title = PROJECT.fileName().split('.')[0]
        self.current_project_path = PROJECT.homePath()
        if self.current_project_title is not None:
            self.output_name = 'export' + '_' + str(self.current_project_title)


    def manage_ui_icons(self):

        """SET PUSHBUTTONS' ICONS"""

        """ACTION"""
        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/filter.png"))
        self.pushButton_action_filter.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/unfilter.png"))
        self.pushButton_action_unfilter.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/export.png"))
        self.pushButton_action_export.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/logo.png"))
        self.pushButton_action_help.setIcon(icon)


        """EXPLORING"""
        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/selection_3.png"))
        self.pushButton_checkable_exploring_selecting.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/zoom_1.png"))
        self.pushButton_checkable_exploring_tracking.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/zoom_2.png"))
        self.pushButton_exploring_zooming.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/link.png"))
        self.pushButton_checkable_exploring_saving_parameters.setIcon(icon)


        """FILTERING"""
        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/change_2.png"))
        self.pushButton_checkable_filtering_auto_current_layer.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/layers.png"))
        self.pushButton_checkable_filtering_layers_to_filter.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/add.png"))
        self.pushButton_checkable_filtering_current_layer_add.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/add_multi.png"))
        self.pushButton_checkable_filtering_layers_to_filter_add.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/geo_1.png"))
        self.pushButton_checkable_filtering_geometric_predicates.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/geo_tampon.png"))
        self.pushButton_checkable_filtering_buffer.setIcon(icon)


        """EXPORTING"""
        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/layers.png"))
        self.pushButton_checkable_exporting_layers.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/projection_1.png"))
        self.pushButton_checkable_exporting_projection.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/styles_1.png"))
        self.pushButton_checkable_exporting_styles.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/datatype.png"))
        self.pushButton_checkable_exporting_datatype.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/folder_white.png"))
        self.pushButton_checkable_exporting_output_folder.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/zip.png"))
        self.pushButton_checkable_exporting_zip.setIcon(icon)







    def manage_ui_style(self):

        """Manage the plugin style"""

        combobox_style = """
                        QgsFeaturePickerWidget
                        {
                        background-color:{color_1};
                        border: 1px solid {color_1};
                        border-radius: 3px;
                        padding: 3px 3px 3px 3px;
                        color:{color_3};
                        }
                        QgsFeaturePickerWidget:hover
                        {
                        border: 2px solid {color_3};
                        }
                        QgsFeaturePickerWidget QAbstractItemView 
                        {
                        background: {color_1};
                        selection-background-color:{color_3};
                        color:{color_3};
                        border: 2px solid {color_3};
                        }
                        QgsProjectionSelectionWidget
                        {
                        background-color:{color_1};
                        border: 1px solid {color_1};
                        border-radius: 3px;
                        padding: 3px 3px 3px 3px;
                        color:{color_3};
                        }
                        QgsProjectionSelectionWidget:hover
                        {
                        border: 2px solid {color_3};
                        }
                        QgsProjectionSelectionWidget QAbstractItemView 
                        {
                        background: {color_1};
                        selection-background-color:{color_3};
                        color:{color_3};
                        border: 2px solid {color_3};
                        }
                        QgsMapLayerComboBox
                        {
                        background-color:{color_1};
                        border: 1px solid {color_1};
                        border-radius: 3px;
                        padding: 3px 3px 3px 3px;
                        color:{color_3};
                        }
                        QgsMapLayerComboBox:hover
                        {
                        border: 2px solid {color_3};
                        }
                        QgsMapLayerComboBox QAbstractItemView 
                        {
                        background: {color_1};
                        selection-background-color:{color_3};
                        color:{color_3};
                        border: 2px solid {color_3};
                        }
                        QgsFieldComboBox
                        {
                        background-color:{color_1};
                        border: 1px solid {color_1};
                        border-radius: 3px;
                        padding: 3px 3px 3px 3px;
                        color:{color_3};
                        }
                        QgsFieldComboBox:hover
                        {
                        border: 2px solid {color_3};
                        }
                        QgsFieldComboBox QAbstractItemView {

                        background: {color_1};
                        selection-background-color:{color_3};
                        color:{color_3};
                        border: 2px solid {color_3};
                        }
                        QgsFieldComboBox
                        {
                        background-color:{color_1};
                        border: 1px solid {color_1};
                        border-radius: 3px;
                        padding: 3px 3px 3px 3px;
                        color:{color_3};
                        }
                        QgsFieldComboBox:hover
                        {
                        border: 2px solid {color_3};
                        }
                        QgsFieldComboBox QAbstractItemView {

                        background: {color_1};
                        selection-background-color:{color_3};
                        color:{color_3};
                        border: 2px solid {color_3};
                        }
                        QgsFieldExpressionWidget
                        {
                        background-color:{color_1};
                        border: 1px solid {color_1};
                        border-radius: 3px;
                        padding: 3px 3px 3px 3px;
                        color:{color_3};
                        }
                        QgsFieldExpressionWidget:hover
                        {
                        border: 2px solid {color_3};
                        }
                        QgsFieldExpressionWidget QAbstractItemView {

                        background: {color_1};
                        selection-background-color:{color_3};
                        color:{color_3};
                        border: 2px solid {color_3};
                        }
                        QgsCheckableComboBox
                        {
                         background-color:{color_1};
                        border: 1px solid {color_1};
                        border-radius: 3px;
                        padding: 3px 3px 3px 3px;
                        color:{color_3};

                        }

                        QgsCheckableComboBox:hover
                        {

                        border: 2px solid {color_3};

                        }

                        QgsCheckableComboBox QAbstractItemView {

                          background: {color_1};
                          selection-background-color: {color_2};
                            color:{color_3};
                            border: 2px solid {color_3};
                        }
                        QComboBox
                        {
                         background-color:{color_1};
                        border: 1px solid {color_1};
                        border-radius: 3px;
                        padding: 3px 3px 3px 3px;
                        color:{color_3};

                        }

                        QComboBox:hover
                        {

                        border: 2px solid {color_3};

                        }

                        QComboBox QAbstractItemView {

                          background: {color_1};
                          selection-background-color: {color_2};
                          color:{color_3};
                          border: 2px solid {color_3};
                        }
                        """




        checkbox_style = """QCheckBox:hover
                            {
                            background-color: {color};
                            }
                            QCheckBox:pressed
                            {
                            background-color: {color};
                            border: 2px solid black;
                            }
                            QCheckBox:checked
                            {
                            background-color:{color};
                            border: 2px solid black;
                            }
                            QCheckBox::indicator
                            {
                            border: none;
                            background: none;
                            }
                            QCheckBox::indicator:checked
                            {
                            background: none;
                            }"""

        pushbutton_style = """QPushButton
                            {
                            border-radius: 10px;
                            padding: 10px 10px 10px 10px;
                            }
                            QPushButton:hover
                            {
                            background-color: {color};
                            }
                            QPushButton:pressed
                            {
                            background-color: {color};
                            border: 2px solid black;
                            }
                            QPushButton:checked
                            {
                            background-color: {color};
                            border: 2px solid black;
                            }
                            """
        dock_style = ("""QWidget
                        {
                        background: {color};
                        }""")
        
        groupbox_style = """QGroupBox
                            {
                            background-color: {color_1};
                            border-color: rgb(0, 0, 0);
                            border-radius:6px;
                            padding: 10px 10px 10px 10px;
                            color:{color_3}
                            }"""

        expression_style = """
                                background-color: {color_2};
                                color:{color_1};
                                border-radius: 3px;
                                padding: 3px 3px 3px 3px;"""

        combobox_style = combobox_style.replace("{color_1}",COLORS["BACKGROUND"][1]).replace("{color_2}",COLORS["BACKGROUND"][2]).replace("{color_3}",COLORS["FONT"][1])

        checkbox_style = checkbox_style.replace("{color}",COLORS["BACKGROUND"][1])

        pushbutton_style = pushbutton_style.replace("{color}",COLORS["BACKGROUND"][1])

        dock_style = dock_style.replace("{color}",COLORS["BACKGROUND"][2])

        groupbox_style = groupbox_style.replace("{color_1}",COLORS["BACKGROUND"][0]).replace("{color_3}",COLORS["FONT"][1])

        expression_style = expression_style.replace("{color_1}",COLORS["FONT"][1]).replace("{color_2}",COLORS["BACKGROUND"][1])


        # self.toolBox_tabWidgets.setStyleSheet("""background-color: {};
        #                                                 border-color: rgb(0, 0, 0);
        #                                                 border-radius:6px;
        #                                                 padding: 10px 10px 10px 10px;
        #                                                 color:{};""".format(COLORS["BACKGROUND"][0],COLORS["FONT"][0]))



        # selfS.setStyleSheet("""background-color: {};
        #                                                 border-color: rgb(0, 0, 0);
        #                                                 border-radius:6px;
        #                                                 marging: 25px 10px 10px 10px;
        #                                                 color:{};""".format(COLORS["BACKGROUND"][0],COLORS["FONT"][0]))









        """SET STYLES"""
        
        """DOCK"""
        self.dockWidgetContents.setStyleSheet(dock_style)

        self.toolBox_tabTools.setStyleSheet("""background-color: {};
                                                        border-color: rgb(0, 0, 0);
                                                        border-radius:6px;
                                                        padding: 10px 10px 10px 10px;
                                                        color:{};""".format(COLORS["BACKGROUND"][0],COLORS["FONT"][0]))
        
        self.group_exploring.setStyleSheet(groupbox_style)

        self.CONFIGURATION.setStyleSheet("""background-color: {};
                                                        border-color: rgb(0, 0, 0);
                                                        border-radius:6px;
                                                        marging: 25px 10px 10px 10px;
                                                        color:{};""".format(COLORS["BACKGROUND"][0],COLORS["FONT"][0]))



        """ACTION"""
        self.pushButton_action_filter.setStyleSheet(pushbutton_style)
        self.pushButton_action_unfilter.setStyleSheet(pushbutton_style)
        self.pushButton_action_export.setStyleSheet(pushbutton_style)
        self.pushButton_action_help.setStyleSheet(pushbutton_style)

        

        """EXPLORING"""
        self.pushButton_checkable_exploring_selecting.setStyleSheet(pushbutton_style)
        self.pushButton_checkable_exploring_tracking.setStyleSheet(pushbutton_style)
        self.pushButton_exploring_zooming.setStyleSheet(pushbutton_style)
        self.pushButton_checkable_exploring_saving_parameters.setStyleSheet(pushbutton_style)

        """SINGLE SELECTION"""
        #self.mGroupBox_exploring_single_selection.setStyleSheet(groupbox_style)
        self.mFeaturePickerWidget_exploring_single_selection.setStyleSheet(combobox_style)
        self.mFieldExpressionWidget_exploring_single_selection.setStyleSheet(combobox_style)

        """MULTIPLE SELECTION"""
        #self.mGroupBox_exploring_multiple_selection.setStyleSheet(groupbox_style)
        #self.mFeatureListComboBox_exploring_multiple_selection.setStyleSheet(combobox_style)
        self.mFieldExpressionWidget_exploring_multiple_selection.setStyleSheet(combobox_style)

        """CUSTOM SELECTION"""
        #self.mGroupBox_exploring_custom_selection.setStyleSheet(groupbox_style)
        self.mFieldExpressionWidget_exploring_custom_selection.setStyleSheet(combobox_style)


        """FILTERING"""
        self.pushButton_checkable_filtering_auto_current_layer.setStyleSheet(pushbutton_style)
        self.pushButton_checkable_filtering_layers_to_filter.setStyleSheet(pushbutton_style)
        self.pushButton_checkable_filtering_current_layer_add.setStyleSheet(pushbutton_style)
        self.pushButton_checkable_filtering_layers_to_filter_add.setStyleSheet(pushbutton_style)
        self.pushButton_checkable_filtering_geometric_predicates.setStyleSheet(pushbutton_style)
        self.pushButton_checkable_filtering_buffer.setStyleSheet(pushbutton_style)


        self.mMapLayerComboBox_filtering_current_layer.setStyleSheet(combobox_style)
        self.comboBox_filtering_layers_to_filter.setStyleSheet(combobox_style)
        self.comboBox_filtering_current_layer_add.setStyleSheet(combobox_style)
        self.comboBox_filtering_layers_to_filter_add.setStyleSheet(combobox_style)
        self.mComboBox_filtering_geometric_predicates.setStyleSheet(combobox_style)
        #lineedit
        #self.mQgsDoubleSpinBox_filtering_buffer.setStyleSheet()
        

        """EXPORTING"""
        self.pushButton_checkable_exporting_layers.setStyleSheet(pushbutton_style)
        self.pushButton_checkable_exporting_projection.setStyleSheet(pushbutton_style)
        self.pushButton_checkable_exporting_styles.setStyleSheet(pushbutton_style)
        self.pushButton_checkable_exporting_datatype.setStyleSheet(pushbutton_style)
        self.pushButton_checkable_exporting_output_folder.setStyleSheet(pushbutton_style)
        self.pushButton_checkable_exporting_zip.setStyleSheet(pushbutton_style)


        self.comboBox_exporting_layers.setStyleSheet(combobox_style)
        self.mQgsProjectionSelectionWidget_exporting_projection.setStyleSheet(combobox_style)
        self.comboBox_exporting_styles.setStyleSheet(combobox_style)
        self.comboBox_exporting_datatype.setStyleSheet(combobox_style)

        #lineedit
        #self.lineEdit_exporting_output_folder.setStyleSheet()
        #self.lineEdit_exporting_zip.setStyleSheet()


        print("Colors changed!")

    def manage_interactions(self):

        """SET INTERACTIONS"""

        """QGIS"""

        """INIT"""
        self.current_layer = self.iface.activeLayer()
        self.current_layer_changed(self.current_layer)

        """SLOTS"""
        if self.auto_change_current_layer_flag is True:
            self.iface.layerTreeView().currentLayerChanged.connect(self.current_layer_changed)



        """DOCK"""

        """INIT"""
        self.select_tabTools_index(self.toolBox_tabTools.currentIndex())

        """SLOTS"""
        self.toolBox_tabTools.currentChanged.connect(self.select_tabTools_index)



        """ACTION"""

        """SLOTS"""
        self.pushButton_action_filter.clicked.connect(partial(self.launchTaskEvent, 'filter'))
        self.pushButton_action_unfilter.clicked.connect(partial(self.launchTaskEvent, 'unfilter'))
        self.pushButton_action_export.clicked.connect(partial(self.launchTaskEvent, 'export'))


        """EXPLORING"""

        """SLOTS"""
        self.pushButton_checkable_exploring_selecting.clicked.connect(partial(self.exploring_property_changed, 'is_selecting'))
        self.pushButton_checkable_exploring_tracking.clicked.connect(partial(self.exploring_property_changed, 'is_tracking'))
        self.pushButton_checkable_exploring_saving_parameters.clicked.connect(partial(self.exploring_property_changed, 'is_saving'))

        self.pushButton_exploring_zooming.clicked.connect(self.exploring_zooming_clicked)


        """SINGLE SELECTION"""

        """SLOTS"""
        self.mGroupBox_exploring_single_selection.clicked.connect(partial(self.exploring_groupbox_changed, 'single_selection'))

        self.mFeaturePickerWidget_exploring_single_selection.featureChanged.connect(self.exploring_features_changed)
        self.mFieldExpressionWidget_exploring_single_selection.fieldChanged.connect(self.exploring_source_params_changed)

        

        """MULTIPLE SELECTION"""
        self.mGroupBox_exploring_multiple_selection.clicked.connect(partial(self.exploring_groupbox_changed, 'multiple_selection'))

        self.customCheckableComboBox_exploring_multiple_selection.updatingCheckedItemList.connect(self.exploring_features_changed)
        self.mFieldExpressionWidget_exploring_multiple_selection.fieldChanged.connect(self.exploring_source_params_changed)
        

        """CUSTOM SELECTION"""
        self.mGroupBox_exploring_custom_selection.clicked.connect(partial(self.exploring_groupbox_changed, 'custom_selection'))

        self.mFieldExpressionWidget_exploring_custom_selection.fieldChanged.connect(self.exploring_source_params_changed)



        """FILTERING"""

        """INIT"""
        self.mMapLayerComboBox_filtering_current_layer.setLayer(self.current_layer)

        """SLOTS"""
        self.mMapLayerComboBox_filtering_current_layer.layerChanged.connect(self.current_layer_changed)

        self.pushButton_checkable_filtering_geometric_predicates.clicked.connect(self.filtering_geometric_predicates_state_changed)
        self.pushButton_checkable_filtering_buffer.clicked.connect(self.filtering_buffer_state_changed)

        self.pushButton_checkable_filtering_auto_current_layer.clicked.connect(self.filtering_auto_current_layer_changed)


        """EXPORTING"""
        
        """INIT"""
        self.mQgsProjectionSelectionWidget_exporting_projection.setCrs(PROJECT.crs())

        """SLOTS"""
        self.pushButton_checkable_exporting_output_folder.clicked.connect(self.dialog_export_folder)
        self.lineEdit_exporting_output_folder.textEdited.connect(self.reset_export_folder)

        self.pushButton_checkable_exporting_zip.clicked.connect(self.dialog_export_zip)
        self.lineEdit_exporting_zip.textEdited.connect(self.reset_export_zip)




    def dialog_export_folder(self):

        if self.pushButton_checkable_export_folder.isChecked() == True:
            
            folderpath = str(QtWidgets.QFileDialog.getExistingDirectory(self, 'Select a folder where to export your layers', self.current_project_path))

            if folderpath:
                self.lineEdit_export_folder.setText(folderpath)
                print(folderpath)
            else:
                self.pushButton_checkable_export_folder.setChecked(False)
        else:
            self.lineEdit_export_folder.clear()

    def reset_export_folder(self):

        if str(self.lineEdit_export_folder.text()) == '':
            self.lineEdit_export_folder.clear()
            self.pushButton_checkable_export_folder.setChecked(False)


    def dialog_export_zip(self):

        if self.pushButton_checkable_export_zip.isChecked() == True:

            
            filepath = str(QtWidgets.QFileDialog.getSaveFileName(self, 'Save your exported data to a zip file', os.path.join(self.current_project_path, self.output_name) ,'*.zip')[0])

            if filepath:
                self.lineEdit_export_zip.setText(filepath)
                print(filepath)
            else:
                self.pushButton_checkable_export_zip.setChecked(False)
        else:
            self.lineEdit_export_zip.clear()


    def reset_export_zip(self):

        if str(self.lineEdit_export_zip.text()) == '':
            self.lineEdit_export_zip.clear()
            self.pushButton_checkable_export_zip.setChecked(False)


    def select_tabTools_index(self, i):
        """Keep the current tab index updated"""
        self.tabTools_current_index = i
        if self.tabTools_current_index == 1:
            self.pushButton_action_export.setEnabled(True)
        else:
            self.pushButton_action_export.setEnabled(False)

    def filtering_auto_current_layer_changed(self):
        if self.pushButton_checkable_filtering_auto_current_layer.isChecked() is True:
            self.auto_change_current_layer_flag = True
            self.iface.layerTreeView().currentLayerChanged.connect(self.current_layer_changed)
        else:
            self.auto_change_current_layer_flag = False
            self.iface.layerTreeView().currentLayerChanged.disconnect()


    def filtering_geometric_predicates_state_changed(self):
        """Manage the geo filter state checkbox"""
        if self.pushButton_checkable_filtering_geometric_predicates.isChecked() is True:
            self.pushButton_checkable_filtering_buffer.setEnabled(True)

            self.mComboBox_filtering_geometric_predicates.setEnabled(True)
        else:
            self.pushButton_checkable_filtering_buffer.setEnabled(False)
            self.pushButton_checkable_filtering_buffer.setChecked(False)

            self.mQgsDoubleSpinBox_filtering_buffer.setDisabled(True)

            self.mComboBox_filtering_geometric_predicates.setDisabled(True)
            
      
    def filtering_buffer_state_changed(self):
        """Manage the buffer state checkbox"""
        if self.pushButton_checkable_filtering_buffer.isChecked() is True:
            self.mQgsDoubleSpinBox_filtering_buffer.setEnabled(True)
        else:
            self.mQgsDoubleSpinBox_filtering_buffer.setEnabled(False)
            

    def exploring_zooming_clicked(self):

        if self.current_exploring_groupbox == "single_selection":
            input = self.mFeaturePickerWidget_exploring_single_selection.feature()
            features = self.getExploringFeatures(input)

        elif self.current_exploring_groupbox == "multiple_selection":
            input = self.customCheckableComboBox_exploring_multiple_selection.checkedItems()
            features = self.getExploringFeatures(input, True)

        elif self.current_exploring_groupbox == "custom_selection":
            return
        
        if features == False:
            return
        else:
            self.zooming_to_features(features)


    def exploring_features_changed(self, input, identify_by_primary_key_name=False):

        layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
        features = self.getExploringFeatures(input, identify_by_primary_key_name)

        if features == False:
            if layer_props["meta"]["is_selecting"] == True:
                self.current_layer.removeSelection()
            return
        
        else:
            if layer_props["meta"]["is_selecting"] == True:
                self.current_layer.removeSelection()
                self.current_layer.select([feature.id() for feature in features])

            if layer_props["meta"]["is_tracking"] == True:
                self.zooming_to_features(features)     



    def exploring_source_params_changed(self, expression):

        layer_props = self.PROJECT_LAYERS[self.current_layer.id()] 
        flag_value_changed = False

        if self.current_exploring_groupbox == "single_selection":
            
            if expression != self.mFeaturePickerWidget_exploring_single_selection.displayExpression():
                self.mFeaturePickerWidget_exploring_single_selection.setDisplayExpression(expression)

            # if expression != self.PROJECT_LAYERS[self.current_layer.id()]["meta"]["single_selection"]["expression"]:
                self.PROJECT_LAYERS[self.current_layer.id()]["meta"]["single_selection"]["expression"] = expression
                flag_value_changed = True

        elif self.current_exploring_groupbox == "multiple_selection":

            if expression != self.customCheckableComboBox_exploring_multiple_selection.displayExpression() and self.current_layer.id() == self.customCheckableComboBox_exploring_multiple_selection.currentLayer().id():
                self.customCheckableComboBox_exploring_multiple_selection.setDisplayExpression(expression)

            # if expression != self.PROJECT_LAYERS[self.current_layer.id()]["meta"]["multiple_selection"]["expression"]:
                self.PROJECT_LAYERS[self.current_layer.id()]["meta"]["multiple_selection"]["expression"] = expression
                flag_value_changed = True


        elif self.current_exploring_groupbox == "custom_selection":

            # if expression != self.PROJECT_LAYERS[self.current_layer.id()]["meta"]["custom_selection"]["expression"]:
            self.PROJECT_LAYERS[self.current_layer.id()]["meta"]["custom_selection"]["expression"] = expression
            flag_value_changed = True
        
        if flag_value_changed == True:
            self.setProjectLayersEvent(self.PROJECT_LAYERS)



    def exploring_groupbox_init(self):

        if self.mGroupBox_exploring_single_selection.isChecked() is True or self.mGroupBox_exploring_single_selection.isCollapsed() is False:
            self.current_exploring_groupbox = "single_selection"

        elif self.mGroupBox_exploring_multiple_selection.isChecked() is True or self.mGroupBox_exploring_multiple_selection.isCollapsed() is False:
            self.current_exploring_groupbox = "multiple_selection"  

        elif self.mGroupBox_exploring_custom_selection.isChecked() is True or self.mGroupBox_exploring_custom_selection.isCollapsed() is False:
            self.current_exploring_groupbox = "custom_selection"

        self.exploring_groupbox_changed(self.current_exploring_groupbox)




    def exploring_groupbox_changed(self, groupbox):
        
        if groupbox == "single_selection":
  
            if self.mGroupBox_exploring_single_selection.isChecked() is True or self.mGroupBox_exploring_single_selection.isCollapsed() is False:
                self.mGroupBox_exploring_single_selection.setChecked(True)
                self.mGroupBox_exploring_single_selection.setCollapsed(False)

                self.mFeaturePickerWidget_exploring_single_selection.setEnabled(True)
                self.mFieldExpressionWidget_exploring_single_selection.setEnabled(True)

                self.mGroupBox_exploring_multiple_selection.setChecked(False)
                self.mGroupBox_exploring_multiple_selection.setCollapsed(True)

                self.mGroupBox_exploring_custom_selection.setChecked(False)
                self.mGroupBox_exploring_custom_selection.setCollapsed(True)

                self.current_exploring_groupbox = "single_selection"

            # else:
            #     self.mGroupBox_exploring_single_selection.setChecked(False)
            #     self.mGroupBox_exploring_single_selection.setCollapsed(True)

            #     self.current_exploring_groupbox = None


        elif groupbox == "multiple_selection":

            if self.mGroupBox_exploring_multiple_selection.isChecked() is True or self.mGroupBox_exploring_multiple_selection.isCollapsed() is False:
                self.mGroupBox_exploring_multiple_selection.setChecked(True)
                self.mGroupBox_exploring_multiple_selection.setCollapsed(False)

                self.customCheckableComboBox_exploring_multiple_selection.setEnabled(True)
                self.mFieldExpressionWidget_exploring_multiple_selection.setEnabled(True)

                self.mGroupBox_exploring_single_selection.setChecked(False)
                self.mGroupBox_exploring_single_selection.setCollapsed(True)

                self.mGroupBox_exploring_custom_selection.setChecked(False)
                self.mGroupBox_exploring_custom_selection.setCollapsed(True)

                self.current_exploring_groupbox = "multiple_selection"

            # else:
            #     self.mGroupBox_exploring_multiple_selection.setChecked(False)
            #     self.mGroupBox_exploring_multiple_selection.setCollapsed(True)

        elif groupbox == "custom_selection":

            if self.mGroupBox_exploring_custom_selection.isChecked() is True or self.mGroupBox_exploring_custom_selection.isCollapsed() is False:
                self.mGroupBox_exploring_custom_selection.setChecked(True)
                self.mGroupBox_exploring_custom_selection.setCollapsed(False)

                self.mFieldExpressionWidget_exploring_custom_selection.setEnabled(True)

                self.mGroupBox_exploring_multiple_selection.setChecked(False)
                self.mGroupBox_exploring_multiple_selection.setCollapsed(True)

                self.mGroupBox_exploring_single_selection.setChecked(False)
                self.mGroupBox_exploring_single_selection.setCollapsed(True)

                self.current_exploring_groupbox = "custom_selection"

            # else:
            #     self.mGroupBox_exploring_custom_selection.setChecked(False)
            #     self.mGroupBox_exploring_custom_selection.setCollapsed(True)
            



    def exploring_property_changed(self, property):

        layer_props = self.PROJECT_LAYERS[self.current_layer.id()]

        flag_value_changed = False

        if property == "is_selecting":
            if layer_props["meta"]["is_selecting"] is False and self.pushButton_checkable_exploring_selecting.isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["meta"]["is_selecting"] = True
                flag_value_changed = True
            elif layer_props["meta"]["is_selecting"] is True and self.pushButton_checkable_exploring_selecting.isChecked() is False:
                self.PROJECT_LAYERS[self.current_layer.id()]["meta"]["is_selecting"] = False
                flag_value_changed = True

        elif property == "is_tracking":
            if layer_props["meta"]["is_tracking"] is False and self.pushButton_checkable_exploring_tracking.isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["meta"]["is_tracking"] = True
                flag_value_changed = True
            elif layer_props["meta"]["is_tracking"] is True and self.pushButton_checkable_exploring_tracking.isChecked() is False:
                self.PROJECT_LAYERS[self.current_layer.id()]["meta"]["is_tracking"] = False
                flag_value_changed = True

        elif property == "is_saving":
            if layer_props["meta"]["is_saving"] is False and self.pushButton_checkable_exploring_saving_parameters.isChecked() is True:
                self.PROJECT_LAYERS[self.current_layer.id()]["meta"]["is_saving"] = True
                flag_value_changed = True
            elif layer_props["meta"]["is_saving"] is True and self.pushButton_checkable_exploring_saving_parameters.isChecked() is False:
                self.PROJECT_LAYERS[self.current_layer.id()]["meta"]["is_saving"] = False
                flag_value_changed = True


        if flag_value_changed is True:
            self.setProjectLayersEvent(self.PROJECT_LAYERS)


    def current_layer_changed(self, layer):

        self.current_layer = layer
        
        try:
            
            layer_props = self.PROJECT_LAYERS[self.current_layer.id()]

            # if self.mMapLayerComboBox_filtering_current_layer.currentLayer().id() != self.current_layer.id():
            #     self.mMapLayerComboBox_filtering_current_layer.setLayer(self.current_layer)


            """EXPLORING"""
            
            """SINGLE SELECTION"""

            self.mFieldExpressionWidget_exploring_single_selection.setLayer(self.current_layer)
            self.mFieldExpressionWidget_exploring_single_selection.setExpression(layer_props["meta"]["single_selection"]["expression"])

            self.mFeaturePickerWidget_exploring_single_selection.setLayer(self.current_layer)
            self.mFeaturePickerWidget_exploring_single_selection.setDisplayExpression(layer_props["meta"]["single_selection"]["expression"])
            self.mFeaturePickerWidget_exploring_single_selection.setFetchGeometry(True)
            self.mFeaturePickerWidget_exploring_single_selection.setShowBrowserButtons(True)

            """MULTIPLE SELECTION"""
            
            self.mFieldExpressionWidget_exploring_multiple_selection.setLayer(self.current_layer)
            self.mFieldExpressionWidget_exploring_multiple_selection.setExpression(layer_props["meta"]["multiple_selection"]["expression"])

            last_layer = self.customCheckableComboBox_exploring_multiple_selection.currentLayer()
            self.customCheckableComboBox_exploring_multiple_selection.setLayer(self.current_layer)
            self.customCheckableComboBox_exploring_multiple_selection.setIdentifierField(layer_props["infos"]["primary_key_name"])
            self.customCheckableComboBox_exploring_multiple_selection.setDisplayExpression(layer_props["meta"]["multiple_selection"]["expression"])

            """CUSTOM SELECTION"""

            self.mFieldExpressionWidget_exploring_custom_selection.setLayer(self.current_layer)
            self.mFieldExpressionWidget_exploring_custom_selection.setExpression(layer_props["meta"]["custom_selection"]["expression"])


            if layer_props["meta"]["is_selecting"] == True and self.pushButton_checkable_exploring_selecting.isChecked() == False:
                self.pushButton_checkable_exploring_selecting.setChecked(True)
            elif layer_props["meta"]["is_selecting"] == False and self.pushButton_checkable_exploring_selecting.isChecked() == True:
                self.pushButton_checkable_exploring_selecting.setChecked(False)

            if layer_props["meta"]["is_tracking"] == True and self.pushButton_checkable_exploring_tracking.isChecked() == False:
                self.pushButton_checkable_exploring_tracking.setChecked(True)
            elif layer_props["meta"]["is_tracking"] == False and self.pushButton_checkable_exploring_tracking.isChecked() == True:
                self.pushButton_checkable_exploring_tracking.setChecked(False)

            if layer_props["meta"]["is_saving"] == True and self.pushButton_checkable_exploring_saving_parameters.isChecked() == False:
                self.pushButton_checkable_exploring_saving_parameters.setChecked(True)
            elif layer_props["meta"]["is_saving"] == False and self.pushButton_checkable_exploring_saving_parameters.isChecked() == True:
                self.pushButton_checkable_exploring_saving_parameters.setChecked(False)
            
            if self.auto_change_current_layer_flag == True:
                if self.iface.activeLayer().id() != self.current_layer.id():
                    self.iface.layerTreeView().setCurrentLayer(self.current_layer)


        except:
            pass
 

    def zooming_to_features(self, features):
        raw_geometries = [feature.geometry() for feature in features if feature.hasGeometry()]
        geometries = []

        for geometry in raw_geometries:
            if geometry.isEmpty() is False:
                if geometry.isMultipart():
                    geometry.convertToSingleType()
                geometries.append(geometry)

        collected_geometry = QgsGeometry().collectGeometry(geometries)

        box = collected_geometry.boundingBox()
        self.iface.mapCanvas().setExtent(box)
        self.iface.mapCanvas().refresh()


    def getExploringFeatures(self, input, identify_by_primary_key_name=False):

        layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
        features = []

        if isinstance(input, QgsFeature):
            features = [input]
        elif isinstance(input, list):
            if len(input) == 0:
                return False
            
            expr = None

            if identify_by_primary_key_name is True:
                if layer_props["infos"]["primary_key_is_numeric"] is True:
                    input_ids = [str(feat[1]) for feat in input]  
                    expr = QgsExpression(layer_props["infos"]["primary_key_name"] + " in (" + ", ".join(input_ids) + ")") 
                else:
                    input_ids = [str(feat[1]) for feat in input]
                    expr = QgsExpression(layer_props["infos"]["primary_key_name"] + " in (\'" + "\', \'".join(input_ids) + "\')")   

            if expr.isValid():

                features_iterator = self.current_layer.getFeatures(QgsFeatureRequest( expr ))
                done_looping = False
                
                while not done_looping:
                    try:
                        feature = next(features_iterator)
                        features.append(feature)
                    except StopIteration:
                        done_looping = True

        return features



    def get_project_layers_from_app(self, project_layers):
        if isinstance(project_layers, dict):
            self.PROJECT_LAYERS = project_layers


    def setProjectLayersEvent(self, event):
        self.settingProjectLayers.emit(event)
    
    def getProjectLayersEvent(self, event):
        self.gettingProjectLayers.emit()


    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def launchTaskEvent(self, event):
        self.launchingTask.emit(event)



class PopulateListEngineTask(QgsTask):
    """Main QgsTask class which filter and unfilter data"""

    def __init__(self, description, parent, action, silent_flag):

        QgsTask.__init__(self, description, QgsTask.CanCancel)

        self.exception = None
        
        self.action = action

        self.parent = parent

        self.silent_flag = silent_flag
        self.layer = self.parent.layer
        self.identifier_field_name = self.parent.identifier_field_name
        self.is_field_flag = self.parent.is_field_flag


    def run(self):
        """Main function that run the right method from init parameters"""
        try:
            if self.action == 'buildFeaturesList':
                self.buildFeaturesList()
            elif self.action == 'updateFeaturesList':
                self.updateFeaturesList()
            elif self.action == 'loadFeaturesList':
                self.loadFeaturesList()
            elif self.action == 'selectAllFeatures':
                self.selectAllFeatures()
            elif self.action == 'deselectAllFeatures':
                self.deselectAllFeatures()
            elif self.action == 'filterFeatures':
                self.filterFeatures()   
            elif self.action == 'updateFeatures':
                self.updateFeatures()

            return True
        
        except Exception as e:
            self.exception = e
            print(self.exception)
            return False

        
    
    def buildFeaturesList(self):
        
        item_list = []
        total_count = self.layer.featureCount()

        if self.is_field_flag is True:
            for index, feature in enumerate(self.layer.getFeatures()):
                arr = [feature[self.parent.list_widgets[self.layer.id()].getExpression()], feature[self.identifier_field_name]]
                item_list.append(arr)
                self.setProgress((index/total_count)*100)
        else:
            expression = QgsExpression(self.parent.list_widgets[self.layer.id()].getExpression())

            if expression.isValid():
                
                context = QgsExpressionContext()
                scope = QgsExpressionContextScope()
                context.appendScope(scope)


                for index, feature in enumerate(self.layer.getFeatures()):
                    scope.setFeature(feature)
                    result = expression.evaluate(context)
                    if result:
                        arr = [result, feature[self.identifier_field_name]]
                        item_list.append(arr)
                        self.setProgress((index/total_count)*100)

        self.parent.list_widgets[self.layer.id()].setList(item_list)
        self.parent.list_widgets[self.layer.id()].sortList()


    def selectAllFeatures(self):
        total_count = self.parent.list_widgets[self.layer.id()].count()
        for index, it in enumerate(range(self.parent.list_widgets[self.layer.id()].count())):
            item = self.parent.list_widgets[self.layer.id()].item(it)
            if not item.isHidden():
                item.setCheckState(Qt.Checked)
            self.setProgress((index/total_count)*100)
        self.updateFeatures()


    def deselectAllFeatures(self):
        total_count = self.parent.list_widgets[self.layer.id()].count()
        for index, it in enumerate(range(self.parent.list_widgets[self.layer.id()].count())):
            item = self.parent.list_widgets[self.layer.id()].item(it)
            if not item.isHidden():
                item.setCheckState(Qt.Unchecked)
            self.setProgress((index/total_count)*100)
        self.updateFeatures()


    def loadFeaturesList(self, custom_list=None, new_list=True, has_limit=True):
        if custom_list == None:
            list_to_load = self.parent.list_widgets[self.layer.id()].getList()
        else:
            list_to_load = custom_list
        
        if new_list is True:
            self.parent.list_widgets[self.layer.id()].clear()

        if has_limit is True:
            limit = self.parent.list_widgets[self.layer.id()].getLimit()

            total_count = len(list_to_load[:limit])
            for index, it in enumerate(list_to_load[:limit]):
                lwi = QListWidgetItem(str(it[0]))
                lwi.setData(0,it[0])
                lwi.setData(3,it[1])
                lwi.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                lwi.setCheckState(Qt.Unchecked)
                self.parent.list_widgets[self.layer.id()].addItem(lwi)
                self.setProgress((index/total_count)*100)
        
        else:
            total_count = len(list_to_load)
            for index, it in enumerate(list_to_load):
                lwi = QListWidgetItem(str(it[0]))
                lwi.setData(0,it[0])
                lwi.setData(3,it[1])
                lwi.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                lwi.setCheckState(Qt.Unchecked)
                self.parent.list_widgets[self.layer.id()].addItem(lwi)
                self.setProgress((index/total_count)*100)
            
            
    def filterFeatures(self):
        total_count = self.parent.list_widgets[self.layer.id()].count()

        if self.parent.list_widgets[self.layer.id()].getListCount() != total_count:
            features_to_load = [feature for feature in self.parent.list_widgets[self.layer.id()].getList() if self.parent.filter_txt.lower() in str(feature[0]).lower()]
            self.loadFeaturesList(features_to_load, True, False)

        total_count = self.parent.list_widgets[self.layer.id()].count()
        for index, it in enumerate(self.parent.list_widgets[self.layer.id()].count()):
            item = self.parent.list_widgets[self.layer.id()].item(it)
            filter = self.parent.filter_txt.lower() not in item.text().lower()
            self.parent.list_widgets[self.layer.id()].setRowHidden(it, filter)
            self.setProgress((index/total_count)*100)

    
    def updateFeatures(self):
        self.parent.items_le.clear()
        selection_data = []
        total_count = self.parent.list_widgets[self.layer.id()].count()
        for index, it in enumerate(range(self.parent.list_widgets[self.layer.id()].count())):
            item = self.parent.list_widgets[self.layer.id()].item(it)
            if item.checkState() == Qt.Checked:
                selection_data.append([item.data(0), item.data(3)])
            self.setProgress((index/total_count)*100)
        selection_data.sort(key=lambda k: k[0])
        self.parent.items_le.setText(', '.join([data[0] for data in selection_data]))
        self.parent.updatedCheckedItemListEvent(selection_data, True)
        
    
    def cancel(self):
        QgsMessageLog.logMessage(
            '"{name}" was canceled'.format(name=self.description()))
        super().cancel()


    def finished(self, result):
        """This function is called automatically when the task is completed and is
        called from the main thread so it is safe to interact with the GUI etc here"""
        if result is False:
            if self.exception is None:
                iface.messageBar().pushMessage('Task was cancelled')
            else:
                iface.messageBar().pushMessage('Errors occured')
                print(self.exception)











class QgsCustomCheckableListWidget(QWidget):
    '''
    Copy and paste this class into your PyQGIS project/ plugin
    '''
    updatingCheckedItemList = pyqtSignal(list, bool)
    
    def __init__(self, parent=None):
        self.parent = parent
        QDialog.__init__(self)
        self.layout = QVBoxLayout(self)
        self.filter_le = QLineEdit(self)
        self.filter_le.setPlaceholderText('Type to filter...')
        self.items_le = QLineEdit(self)
        self.items_le.setReadOnly(True)

        self.layout.addWidget(self.filter_le)
        self.layout.addWidget(self.items_le)

        self.context_menu = QMenu(self)
        self.action_check_all = QAction('Select All', self)
        self.action_check_all.triggered.connect(self.select_all)
        self.action_uncheck_all = QAction('De-select All', self)
        self.action_uncheck_all.triggered.connect(self.deselect_all)
        self.context_menu.addAction(self.action_check_all)
        self.context_menu.addAction(self.action_uncheck_all)

        self.list_widgets = {}

        self.tasks = {}
        
        self.tasks['buildFeaturesList'] = {}
        self.tasks['updateFeaturesList'] = {}
        self.tasks['loadFeaturesList'] = {}
        self.tasks['selectAllFeatures'] = {}
        self.tasks['deselectAllFeatures'] = {}
        self.tasks['filterFeatures'] = {}
        self.tasks['updateFeatures'] = {}

        self.last_layer = None
        self.layer = None
        self.identifier_field_name = None
        self.expression = None
        self.is_field_flag = None

    def checkedItems(self):
        selection = []
        for i in range(self.list_widgets[self.layer.id()].count()):
            item = self.list_widgets[self.layer.id()].item(i)
            if item.checkState() == Qt.Checked:
                selection.append((item.data(0), item.data(3)))
        selection.sort(key=lambda k: k[0])
        return selection

    def displayExpression(self):
        return self.list_widgets[self.layer.id()].getExpression() 
      
    def currentLayer(self):
        return self.layer 
      

    def setLayer(self, layer):
        self.last_layer = self.layer
        self.layer = layer


    def setIdentifierField(self, field_name):
        self.identifier_field_name = field_name

    def connect_filter_lineEdit(self):
        if self.list_widgets[self.layer.id()].getListCount() > self.list_widgets[self.layer.id()].getLimit():
            try:
                self.filter_le.textChanged.disconnect()
            except:
                pass
            self.filter_le.editingFinished.connect(self.filter_items)
        else:
            try:
                self.filter_le.editingFinished.disconnect()
            except:
                pass
            self.filter_le.textChanged.connect(self.filter_items)

    def setDisplayExpression(self, expression):

        has_to_be_processed = self.manage_list_widgets(expression)

        if has_to_be_processed is False:
            return
        else:
            if QgsExpression(expression).isField():
                working_expression = expression.replace('"', '')
                self.is_field_flag = True
            else:
                working_expression = expression
                self.is_field_flag = False

            self.list_widgets[self.layer.id()].setExpression(working_expression)

            sub_description = 'Building features list'
            sub_action = 'buildFeaturesList'

            self.build_task(sub_description, sub_action)

            description = 'Loading features'
            action = 'loadFeaturesList'
            self.build_task(description, action)

            self.tasks['loadFeaturesList'][self.layer.id()].addSubTask(self.tasks[sub_action][self.layer.id()], [], QgsTask.ParentDependsOnSubTask)

            self.launch_task('loadFeaturesList')
                
        

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress and obj == self.list_widgets[self.layer.id()].viewport():
            if event.button() == Qt.LeftButton:
                clicked_item = self.list_widgets[self.layer.id()].itemAt(event.pos())
                if clicked_item.checkState() == Qt.Checked:
                    clicked_item.setCheckState(Qt.Unchecked)
                else:
                    clicked_item.setCheckState(Qt.Checked)

                description = 'Selecting feature'
                action = 'updateFeatures'
                self.build_task(description, action, True)
                self.launch_task(action)

            elif event.button() == Qt.RightButton:
                self.context_menu.exec(QCursor.pos())
            return True
        return False
            
    def manage_list_widgets(self, expression):
        for key in self.list_widgets.keys():
            self.list_widgets[key].setVisible(False)

        if self.layer.id() in self.list_widgets:
            self.list_widgets[self.layer.id()].setVisible(True)
            print(self.list_widgets[self.layer.id()].getExpression(), expression)
            if self.list_widgets[self.layer.id()].getExpression() == expression:
                return False
        else:
            self.add_list_widget()

        return True

    def add_list_widget(self):
        self.list_widgets[self.layer.id()] = ListWidgetWrapper(self)
        self.list_widgets[self.layer.id()].viewport().installEventFilter(self)
        self.layout.addWidget(self.list_widgets[self.layer.id()])


    def select_all(self):
        description = 'Selecting all features'
        action = 'selectAllFeatures'
        self.build_task(description, action)
        self.launch_task(action)

    def deselect_all(self):
        description = 'Deselecting all features'
        action = 'deselectAllFeatures'
        self.build_task(description, action)
        self.launch_task(action)
        
    def filter_items(self, filter_txt=None):
        if filter_txt == None:
            self.filter_txt = self.filter_le.text()
        else:    
            self.filter_txt = filter_txt
        description = 'Filtering features'
        action = 'filterFeatures'
        self.build_task(description, action)
        self.launch_task(action)
    
    def build_task(self, description, action, silent_flag=False):
        self.tasks[action][self.layer.id()] = PopulateListEngineTask(description, self, action, silent_flag)
        self.tasks[action][self.layer.id()].setDependentLayers([self.layer])

        if silent_flag is False:
            self.tasks[action][self.layer.id()].begun.connect(lambda:  iface.messageBar().pushMessage(self.layer.name() + " : " + description))

    def launch_task(self, action):
        self.tasks[action][self.layer.id()].taskCompleted.connect(self.connect_filter_lineEdit)
        QgsApplication.taskManager().addTask(self.tasks[action][self.layer.id()])
    
    def updatedCheckedItemListEvent(self, data, flag):
        self.updatingCheckedItemList.emit(data, flag)

class ListWidgetWrapper(QListWidget):
  
    def __init__(self, parent=None):

        super(ListWidgetWrapper, self).__init__(parent)

        self.setMinimumHeight(100)
        



        self.expression = ''
        self.list = []
        self.limit = 1000

    def setExpression(self, expression):
        self.expression = expression
    
    def setList(self, list):
        self.list = list
    
    def setLimit(self, limit):
        self.limit = limit
    
    def getExpression(self):
        return self.expression
    
    def getList(self):
        return self.list
    
    def getLimit(self):
        return self.limit

    def getListCount(self):
        return len(self.list) if isinstance(self.list, list) else 0
    
    def sortList(self):
        self.list.sort(key=lambda k: k[0])

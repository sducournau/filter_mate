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
from qgis.PyQt.QtWidgets import QApplication

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'filter_mate_dockwidget_base.ui'))


class FilterMateDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()
    launchingTask = pyqtSignal(str)

    def __init__(self, parent=None):
        """Constructor."""
        super(FilterMateDockWidget, self).__init__(parent)
        

        self.tabTools_current_index = 0
        self.tabWidgets_current_index = 0


        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://doc.qt.io/qt-5/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.manage_ui_icons()
        self.manage_ui_style()
        self.manage_interactions()
        self.manage_output_name()

    def manage_output_name(self):
        self.output_name = 'export'
        self.current_project_title = PROJECT.fileName().split('.')[0]
        self.current_project_path = PROJECT.homePath()
        if self.current_project_title is not None:
            self.output_name = 'export' + '_' + str(self.current_project_title)


    def manage_ui_icons(self):

        """SET PUSHBUTTONS' ICONS"""

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/filter.png"))
        self.pushButton_filter_start.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/filter_erase.png"))
        self.pushButton_filter_end.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/change_1.png"))
        self.checkBox_filter_layer.setIcon(icon)


        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/layers.png"))
        self.checkBox_multi_filter.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/geo_1.png"))
        self.checkBox_filter_geo.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/geo_tampon.png"))
        self.checkBox_tampon.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/export.png"))
        self.pushButton_export.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/add.png"))
        self.checkBox_filter_add.setIcon(icon)


        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/add_multi.png"))
        self.checkBox_add_multi.setIcon(icon)




        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/layers.png"))
        self.checkBox_export_layers.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/datatype.png"))
        self.checkBox_export_datatype.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/styles_1.png"))
        self.checkBox_export_styles.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/folder_white.png"))
        self.checkBox_export_folder.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/zip.png"))
        self.checkBox_export_zip.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/projection_1.png"))
        self.checkBox_export_projection.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/selection_4.png"))
        self.checkBox_filter_by_selection.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/zoom_1.png"))
        self.checkBox_filter_by_selection_auto_change_layer.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/zoom_2.png"))
        self.pushButton.setIcon(icon)

        icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/link.png"))
        self.checkBox_test_2.setIcon(icon)



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

        self.toolBox_tabTools.setStyleSheet("""background-color: {};
                                                        border-color: rgb(0, 0, 0);
                                                        border-radius:6px;
                                                        padding: 10px 10px 10px 10px;
                                                        color:{};""".format(COLORS["BACKGROUND"][0],COLORS["FONT"][0]))

        # self.WIDGETS.setStyleSheet("""background-color: {};
        #                                                 border-color: rgb(0, 0, 0);
        #                                                 border-radius:6px;
        #                                                 marging: 25px 10px 10px 10px;
        #                                                 color:{};""".format(COLORS["BACKGROUND"][0],COLORS["FONT"][0]))






        self.CONFIGURATION.setStyleSheet("""background-color: {};
                                                        border-color: rgb(0, 0, 0);
                                                        border-radius:6px;
                                                        marging: 25px 10px 10px 10px;
                                                        color:{};""".format(COLORS["BACKGROUND"][0],COLORS["FONT"][0]))



        self.group_explorer.setStyleSheet(groupbox_style)

        self.mFieldExpressionWidget.setStyleSheet(combobox_style)
        self.mFieldExpressionWidget_filter_by_selection.setStyleSheet(combobox_style)

        self.checkBox_filter_layer.setStyleSheet(checkbox_style)
        self.checkBox_multi_filter.setStyleSheet(checkbox_style)
        self.checkBox_add_multi.setStyleSheet(checkbox_style)
        self.checkBox_filter_geo.setStyleSheet(checkbox_style)
        self.checkBox_tampon.setStyleSheet(checkbox_style)
        self.checkBox_filter_add.setStyleSheet(checkbox_style)
        

        self.checkBox_export_layers.setStyleSheet(checkbox_style)
        self.checkBox_export_datatype.setStyleSheet(checkbox_style)
        self.checkBox_export_styles.setStyleSheet(checkbox_style)
        self.checkBox_export_folder.setStyleSheet(checkbox_style)
        self.checkBox_export_zip.setStyleSheet(checkbox_style)
        self.checkBox_export_projection.setStyleSheet(checkbox_style)

        self.comboBox_export_layers.setStyleSheet(combobox_style)
        self.mQgsProjectionSelectionWidget_export_crs.setStyleSheet(combobox_style)
        self.comboBox_export_styles.setStyleSheet(combobox_style)
        self.comboBox_export_datatype.setStyleSheet(combobox_style)



        self.mFeaturePickerWidget_filter_by_selection.setStyleSheet(combobox_style)

        self.mComboBox_filter_by_selection.setStyleSheet(combobox_style)
        self.mFieldComboBox_filter_by_selection.setStyleSheet(combobox_style)
        self.mMapLayerComboBox_filter_by_selection.setStyleSheet(combobox_style)


        self.pushButton.setStyleSheet(pushbutton_style)
        self.checkBox_test_2.setStyleSheet(checkbox_style)

        self.checkBox_filter_by_selection.setStyleSheet(checkbox_style)
        self.checkBox_filter_by_selection_auto_change_layer.setStyleSheet(checkbox_style)

        self.pushButton_export.setStyleSheet(pushbutton_style)
        self.pushButton_filter_start.setStyleSheet(pushbutton_style)
        self.pushButton_filter_end.setStyleSheet(pushbutton_style)

        self.dockWidgetContents.setStyleSheet(dock_style)

        self.mComboBox_filter_geo.setStyleSheet(combobox_style)
        self.comboBox_filter_add.setStyleSheet(combobox_style)
      
        self.comboBox_filter_add_multi.setStyleSheet(combobox_style)
        self.comboBox_select_layers.setStyleSheet(combobox_style)

        self.comboBox_select_layers.setStyleSheet(combobox_style)

        print("Colors changed!")

    def manage_interactions(self):


        # self.mFeatureListComboBox.setSourceLayer(PROJECT.mapLayersByName('zone_de_pm')[0])
        # self.mFeatureListComboBox.setIdentifierField('code_id')
        # self.mFeatureListComboBox.setDisplayExpression('''"za_zpm" || ' - ' || "commune"''')
        # self.mFeatureListComboBox.setIdentifierValues(['za_zpm', 'commune'])
        self.current_layer_selected = self.mMapLayerComboBox_filter_by_selection.currentLayer()

        self.mFeaturePickerWidget_filter_by_selection.setLayer(self.current_layer_selected)

    

        self.checkBox_tampon.stateChanged.connect(self.change_state_tampon)
        self.checkBox_filter_geo.stateChanged.connect(self.change_state_geo_filter)




        self.checkBox_export_folder.stateChanged.connect(self.dialog_export_folder)
        self.lineEdit_export_folder.textEdited.connect(self.reset_export_folder)

        self.checkBox_export_zip.stateChanged.connect(self.dialog_export_zip)
        self.lineEdit_export_zip.textEdited.connect(self.reset_export_zip)


        """SET PUSHBUTTONS' INTERACTIONS"""
        self.pushButton_filter_start.clicked.connect(partial(self.launchTaskEvent, 'filter'))
        self.pushButton_filter_end.clicked.connect(partial(self.launchTaskEvent, 'unfilter'))
        self.pushButton_export.clicked.connect(partial(self.launchTaskEvent, 'export'))

        """On tab change choose the right filter logic"""

        # self.select_tabWidgets_index(self.toolBox_tabWidgets.currentIndex())
        # self.toolBox_tabWidgets.currentChanged.connect(self.select_tabWidgets_index)

        self.select_tabTools_index(self.toolBox_tabTools.currentIndex())
        self.toolBox_tabTools.currentChanged.connect(self.select_tabTools_index)

        self.mQgsProjectionSelectionWidget_export_crs.setCrs(PROJECT.crs())
     



    def dialog_export_folder(self):

        if self.checkBox_export_folder.checkState() == 2:
            
            folderpath = str(QtWidgets.QFileDialog.getExistingDirectory(self, 'Select a folder where to export your layers', self.current_project_path))

            if folderpath:
                self.lineEdit_export_folder.setText(folderpath)
                print(folderpath)
            else:
                self.checkBox_export_folder.setCheckState(0)
        else:
            self.lineEdit_export_folder.clear()

    def reset_export_folder(self):

        if str(self.lineEdit_export_folder.text()) == '':
            self.lineEdit_export_folder.clear()
            self.checkBox_export_folder.setCheckState(0)


    def dialog_export_zip(self):

        if self.checkBox_export_zip.checkState() == 2:

            
            filepath = str(QtWidgets.QFileDialog.getSaveFileName(self, 'Save your exported data to a zip file', os.path.join(self.current_project_path, self.output_name) ,'*.zip')[0])

            if filepath:
                self.lineEdit_export_zip.setText(filepath)
                print(filepath)
            else:
                self.checkBox_export_zip.setCheckState(0)
        else:
            self.lineEdit_export_zip.clear()


    def reset_export_zip(self):

        if str(self.lineEdit_export_zip.text()) == '':
            self.lineEdit_export_zip.clear()
            self.checkBox_export_zip.setCheckState(0)


    def select_tabWidgets_index(self, i):
        """Keep the current tab index updated"""
        self.tabWidgets_current_index = i

    def select_tabTools_index(self, i):
        """Keep the current tab index updated"""
        self.tabTools_current_index = i
        if self.tabTools_current_index == 1:
            self.pushButton_export.setEnabled(True)
        else:
            self.pushButton_export.setEnabled(False)

    def change_state_geo_filter(self):
        """Manage the geo filter state checkbox"""
        if self.checkBox_filter_geo.checkState() == 2:
            self.checkBox_tampon.setEnabled(True)

            self.mComboBox_filter_geo.setEnabled(True)
        else:
            self.checkBox_tampon.setEnabled(False)
            self.checkBox_tampon.setChecked(False)

            self.mQgsDoubleSpinBox_tampon.setDisabled(True)

            self.mComboBox_filter_geo.setDisabled(True)
            
      
    def change_state_tampon(self):
        """Manage the buffer state checkbox"""
        if self.checkBox_tampon.checkState() == 2:
            self.mQgsDoubleSpinBox_tampon.setEnabled(True)
        else:
            self.mQgsDoubleSpinBox_tampon.setEnabled(False)

            


    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def launchTaskEvent(self, event):
        self.launchingTask.emit(event)
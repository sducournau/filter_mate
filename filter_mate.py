# -*- coding: utf-8 -*-
"""
/***************************************************************************
 FilterMate
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

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt import QtGui
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *
from qgis.utils import iface
from functools import partial
from qgis.PyQt.QtWidgets import QApplication

# Initialize Qt resources from file resources.py
from .resources import *
import os
# Import the code for the DockWidget
from .filter_mate_dockwidget import FilterMateDockWidget
import os.path
from .utils import *

from qgis.PyQt.QtGui import QIcon

class FilterMate:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """

        # app = QApplication.instance()
        # app.setStyleSheet(".QWidget {color: yellow; background-color: dark;}")
        # You can even read the stylesheet from a file


        # Save reference to the QGIS interface
        self.iface = iface
        self.current_index = 0
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'FilterMate_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&FilterMate')
        # TODO: We are going to let the user set this up in a future iteration

        self.toolbar = self.iface.addToolBar(u'FilterMate')
        self.toolbar.setObjectName(u'FilterMate')

        #print "** INITIALIZING FilterMate"

        self.pluginIsActive = False
        self.dockwidget = None
        self.LAYER_TEMP = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('FilterMate', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action


    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/filter_mate/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'FilterMate'),
            callback=self.run,
            parent=self.iface.mainWindow())

    #--------------------------------------------------------------------------

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""

        #print "** CLOSING FilterMate"

        # disconnects
        self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)

        # remove this statement if dockwidget is to remain
        # for reuse if plugin is reopened
        # Commented next statement since it causes QGIS crashe
        # when closing the docked window:
        # self.dockwidget = None

        self.pluginIsActive = False






    def managerTask(self, task_name):
        """Manage the different tasks"""




        self.task_name = task_name
        t0 = time.time()
        print("FILTRING...")
        if self.task_name == 'start':
            description = 'Filtrer les couches'
            self.task_filter = FilterMate_(description ,self.dockwidget, self.task_name,self.current_index,self.managerWidgets)
            self.task_filter.taskCompleted.connect(lambda: zoom_to_features(self.layer_zoom, t0))
            QgsApplication.taskManager().addTask(self.task_filter)
        elif self.task_name == 'end':
            description = 'Défiltrer les couches'
            self.task_filter = FilterMate_(description ,self.dockwidget, self.task_name,self.current_index,self.managerWidgets)

            QgsApplication.taskManager().addTask(self.task_filter)
        elif self.task_name == 'export':
            description = 'Exporter les couches'
            self.task_filter = FilterMate_(description ,self.dockwidget, self.task_name,self.current_index,self.managerWidgets)

            QgsApplication.taskManager().addTask(self.task_filter)
        elif self.task_name == 'load':
            description = 'Chargement des données'
            self.load_data()

        """Zoom to the filtered features"""
        selected_za_nro_data = self.dockwidget.comboBox_select_za_nro.checkedItems()
        selected_za_zpm_data = self.dockwidget.comboBox_select_za_zpm.checkedItems()
        selected_za_zpa_data = self.dockwidget.comboBox_select_za_zpa.checkedItems()
        selected_commune_data = self.dockwidget.comboBox_select_commune.checkedItems()

        if self.task_name == 'start':
            if len(selected_za_zpa_data) > 0:
                self.layer_zoom = PROJECT.mapLayersByName(LAYERS['ZONE_DE_PA'][0])[0]
            elif len(selected_za_zpm_data) > 0:
                self.layer_zoom = PROJECT.mapLayersByName(LAYERS['ZONE_DE_PM'][0])[0]
            elif len(selected_za_nro_data) > 0:
                self.layer_zoom = PROJECT.mapLayersByName(LAYERS['ZONE_DE_NRO'][0])[0]
            elif len(selected_commune_data) > 0:
                self.layer_zoom = PROJECT.mapLayersByName(LAYERS['CONTOURS_COMMUNES'][0])[0]
            else:
                layer_name = self.dockwidget.comboBox_multi_layers.currentText()
                self.layer_zoom = PROJECT.mapLayersByName(layer_name)[0]





    def current_layer_expression_changed(self):
        """Keep the advanced filter combobox updated on adding or removing layers"""
        try:
            from_layer = PROJECT.mapLayersByName(self.dockwidget.comboBox_multi_layers.currentText())[0]
            subsetString = from_layer.subsetString()
            if subsetString == '':
                self.dockwidget.checkBox_filter_add.setEnabled(False)
                self.dockwidget.checkBox_filter_add.setChecked(False)
            else:
                self.dockwidget.checkBox_filter_add.setEnabled(True)
            self.dockwidget.mFieldExpressionWidget.setLayer(from_layer)

        except:
            print("Error occurred loading layers")



    def select_tab_index(self, i):
        """Keep the current tab index updated"""
        self.current_index = i





    def change_colors(self):
        """Manage the plugin style"""

        combobox_style = """QgsCheckableComboBox
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

                        QComboBox QAbstractItemView {

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

        pushbutton_style = """QPushButton:hover
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

        expression_style = """
                                background-color: {color_2};
                                color:{color_1};
                                border-radius: 3px;
                                padding: 3px 3px 3px 3px;"""

        combobox_style = combobox_style.replace("{color_1}",COLORS["BACKGROUND"][1]).replace("{color_2}",COLORS["BACKGROUND"][2]).replace("{color_3}",COLORS["FONT"][1])

        checkbox_style = checkbox_style.replace("{color}",COLORS["BACKGROUND"][1])

        pushbutton_style = pushbutton_style.replace("{color}",COLORS["BACKGROUND"][1])

        dock_style = dock_style.replace("{color}",COLORS["BACKGROUND"][2])



        expression_style = expression_style.replace("{color_1}",COLORS["FONT"][1]).replace("{color_2}",COLORS["BACKGROUND"][1])


        self.dockwidget.toolBox_filtre.setStyleSheet("""background-color: {};
                                                        border-color: rgb(0, 0, 0);
                                                        border-radius:6px;
                                                        padding: 10px 10px 10px 10px;
                                                        color:{};""".format(COLORS["BACKGROUND"][0],COLORS["FONT"][0]))

        self.dockwidget.toolBox_avance.setStyleSheet("""background-color: {};
                                                        border-color: rgb(0, 0, 0);
                                                        border-radius:6px;
                                                        padding: 10px 10px 10px 10px;
                                                        color:{};""".format(COLORS["BACKGROUND"][0],COLORS["FONT"][0]))

        self.dockwidget.WIDGETS.setStyleSheet("""background-color: {};
                                                        border-color: rgb(0, 0, 0);
                                                        border-radius:6px;
                                                        marging: 25px 10px 10px 10px;
                                                        color:{};""".format(COLORS["BACKGROUND"][0],COLORS["FONT"][0]))






        self.dockwidget.CONFIGURATION.setStyleSheet("""background-color: {};
                                                        border-color: rgb(0, 0, 0);
                                                        border-radius:6px;
                                                        marging: 25px 10px 10px 10px;
                                                        color:{};""".format(COLORS["BACKGROUND"][0],COLORS["FONT"][0]))





        self.dockwidget.mFieldExpressionWidget.setStyleSheet(expression_style)
        self.dockwidget.comboBox_export_type.setStyleSheet(combobox_style)
        self.dockwidget.checkBox_multi_filter.setStyleSheet(checkbox_style)
        self.dockwidget.checkBox_add_multi.setStyleSheet(checkbox_style)
        self.dockwidget.checkBox_filter_geo.setStyleSheet(checkbox_style)
        self.dockwidget.checkBox_tampon.setStyleSheet(checkbox_style)
        self.dockwidget.checkBox_filter_add.setStyleSheet(checkbox_style)
        self.dockwidget.checkBox_filter_layer.setStyleSheet(checkbox_style)

        self.dockwidget.pushButton_export.setStyleSheet(pushbutton_style)
        self.dockwidget.pushButton_filter_start.setStyleSheet(pushbutton_style)
        self.dockwidget.pushButton_filter_end.setStyleSheet(pushbutton_style)

        self.dockwidget.dockWidgetContents.setStyleSheet(dock_style)

        self.dockwidget.comboBox_export_type.setStyleSheet(combobox_style)
        self.dockwidget.mComboBox_filter_geo.setStyleSheet(combobox_style)
        self.dockwidget.comboBox_filter_add.setStyleSheet(combobox_style)
        self.dockwidget.comboBox_multi_layers.setStyleSheet(combobox_style)
        self.dockwidget.comboBox_filter_add_multi.setStyleSheet(combobox_style)
        self.dockwidget.comboBox_select_layers.setStyleSheet(combobox_style)

        self.dockwidget.comboBox_select_layers.setStyleSheet(combobox_style)

        print("Colors changed!")



    def change_state_tampon(self):
        """Manage the buffer state checkbox"""
        if self.dockwidget.checkBox_filter_geo.checkState() == 2:
            self.dockwidget.checkBox_tampon.setEnabled(True)
        else:
            self.dockwidget.checkBox_tampon.setEnabled(False)
            self.dockwidget.checkBox_tampon.setChecked(False)

    def resources_path(self, *args):
            """Get the path to our resources folder.

            :param args List of path elements e.g. ['img', 'logos', 'image.png']
            :type args: str

            :return: Absolute path to the resources folder.
            :rtype: str
            """
            path = str(self.plugin_dir) + str(os.sep()) + 'images'

            for item in args:
                path = path + str(os.sep()) + item



            return path


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        #print "** UNLOAD FilterMate"

        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Filtrage des couches'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    #--------------------------------------------------------------------------
    def reload_config(self):
        """Create qtreeview model configuration from json file"""
        self.edit_config_json()
        global CONFIG_SCOPE, CONFIG_DATA
        if CONFIG_SCOPE:

            self.managerWidgets.manage_widgets(CONFIG_DATA['WIDGETS'])



                #item = self.dockwidget.WIDGETS.layout().itemAtPosition(i,1)
                #self.dockwidget.WIDGETS.layout().removeItem(item)
                #item = self.dockwidget.WIDGETS.layout().itemAtPosition(i,0)
                #self.dockwidget.WIDGETS.layout().removeItem(item)



            self.change_colors()


            CONFIG_SCOPE = False

    def init_basic_filters(self):
        """Init the basic filters"""
        if LAYERS['ZONE_DE_NRO'][2] == 'True':
            self.dockwidget.comboBox_select_za_nro.setEnabled(True)
            self.dockwidget.comboBox_select_za_nro.setDefaultText(LAYERS['ZONE_DE_NRO'][0])
            self.populate.populate_za_nro()
        else:
            self.dockwidget.comboBox_select_za_nro.setEnabled(False)

        if LAYERS['ZONE_DE_PM'][2] == 'True':
            self.dockwidget.comboBox_select_za_zpm.setEnabled(True)
            self.dockwidget.comboBox_select_za_zpm.setDefaultText(LAYERS['ZONE_DE_PM'][0])
            self.populate.populate_za_zpm()
        else:
            self.dockwidget.comboBox_select_za_zpm.setEnabled(False)

        if LAYERS['ZONE_DE_PA'][2] == 'True':
            self.dockwidget.comboBox_select_za_zpa.setEnabled(True)
            self.dockwidget.comboBox_select_za_zpa.setDefaultText(LAYERS['ZONE_DE_PA'][0])
            self.populate.populate_za_zpa()
        else:
            self.dockwidget.comboBox_select_za_zpa.setEnabled(False)

        if LAYERS['CONTOURS_COMMUNES'][2] == 'True':
            self.dockwidget.comboBox_select_commune.setEnabled(True)
            self.dockwidget.comboBox_select_commune.setDefaultText(LAYERS['CONTOURS_COMMUNES'][0])
            self.populate.populate_commune()
        else:
            self.dockwidget.comboBox_select_commune.setEnabled(False)

    def edit_config_json(self):
        """Write qtreeview model configuration to json file"""
        global LAYERS,COLORS, CONFIG_DATA, DIR_PROFILE
        CONFIG_DATA = self.managerWidgets.model.serialize()
        LAYERS = CONFIG_DATA['LAYERS']
        COLORS = CONFIG_DATA['COLORS']
        print('reload config')
        with open(DIR_PLUGIN + '/config/config.json', 'w') as outfile:
            json.dump(CONFIG_DATA, outfile)

    def qtree_signal(self):
        """Signal to overload configuration qtreeview model to keep configuration file up to date"""
        global CONFIG_SCOPE
        CONFIG_SCOPE = True


    def run(self):
        """Run method that loads and starts the plugin"""

        if not self.pluginIsActive:
            self.pluginIsActive = True

            #print "** STARTING FilterMate"



            # dockwidget may not exist if:
            #    first run of plugin
            #    removed on close (see self.onClosePlugin method)
            if self.dockwidget == None:
                # Create the dockwidget (after translation) and keep reference
                self.dockwidget = FilterMateDockWidget()


                """INIT"""


                """Load the style"""
                self.change_colors()


                """Controller for dealing with filter widgets and the configuration model"""
                self.managerWidgets = ManagerWidgets(self.dockwidget)


                """Init the filter widgets"""
                self.managerWidgets.manage_widgets(CONFIG_DATA['WIDGETS'])


                """Overload configuration qtreeview model to keep configuration file up to date"""
                self.managerWidgets.model.dataChanged.connect(self.qtree_signal)
                self.managerWidgets.model.rowsInserted.connect(self.qtree_signal)
                self.managerWidgets.model.rowsRemoved.connect(self.qtree_signal)


                self.managerWidgets.view.onLeaveEvent.connect(self.reload_config)
                #self.managerWidgets.view.onAddWidget.connect(lambda: self.reload_config('add'))
                #self.managerWidgets.view.onRemoveWidget.connect(lambda: self.reload_config('remove'))


                """Controller for populating and keep updated comboboxes"""
                self.populate = populateData(self.dockwidget)


                """Init the basic filters"""
                self.init_basic_filters()
                if LAYERS['ZONE_DE_PM'][2] == 'True':
                    self.dockwidget.comboBox_select_za_nro.currentIndexChanged.connect(self.populate.populate_za_zpm)
                if LAYERS['ZONE_DE_PA'][2] == 'True':
                    self.dockwidget.comboBox_select_za_nro.currentIndexChanged.connect(self.populate.populate_za_zpa)
                    self.dockwidget.comboBox_select_za_zpm.currentIndexChanged.connect(self.populate.populate_za_zpa)
                if LAYERS['CONTOURS_COMMUNES'][2] == 'True':
                    self.dockwidget.comboBox_select_za_nro.currentIndexChanged.connect(self.populate.populate_commune)

                """Init the advanced filters"""
                self.populate.populate_layers()
                self.populate.populate_predicat()

                self.dockwidget.mQgsProjectionSelectionWidget.setCrs(PROJECT.crs())



                """Keep the advanced filter combobox updated on adding or removing layers"""
                PROJECT.layersAdded.connect(self.populate.populate_layers)
                PROJECT.layersRemoved.connect(self.populate.populate_layers)
                self.current_layer_expression_changed()





                """SET PUSHBUTTONS' ICONS"""
                icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/layer.png"))
                self.dockwidget.checkBox_filter_layer.setIcon(icon)

                icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/filter.png"))
                self.dockwidget.pushButton_filter_start.setIcon(icon)

                icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/filter_erase.png"))
                self.dockwidget.pushButton_filter_end.setIcon(icon)

                icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/geo.png"))
                self.dockwidget.checkBox_filter_geo.setIcon(icon)

                icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/geo_tampon.png"))
                self.dockwidget.checkBox_tampon.setIcon(icon)

                icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/export.png"))
                self.dockwidget.pushButton_export.setIcon(icon)

                icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/add.png"))
                self.dockwidget.checkBox_filter_add.setIcon(icon)


                icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/layers.png"))
                self.dockwidget.checkBox_multi_filter.setIcon(icon)


                icon = QtGui.QIcon(os.path.join(DIR_PLUGIN,  "images/add_multi.png"))
                self.dockwidget.checkBox_add_multi.setIcon(icon)


                """SET PUSHBUTTONS' INTERACTIONS"""
                self.dockwidget.checkBox_filter_geo.stateChanged.connect(self.change_state_tampon)
                self.dockwidget.pushButton_filter_start.clicked.connect(partial(self.managerTask,'start'))
                self.dockwidget.pushButton_filter_end.clicked.connect(partial(self.managerTask,'end'))
                self.dockwidget.pushButton_export.clicked.connect(partial(self.managerTask,'export'))
                self.dockwidget.comboBox_multi_layers.currentTextChanged.connect(self.current_layer_expression_changed)

                """On tab change choose the right filter logic"""
                self.select_tab_index(self.dockwidget.toolBox_filtre.currentIndex())
                self.dockwidget.toolBox_filtre.currentChanged.connect(self.select_tab_index)

            # connect to provide cleanup on closing of dockwidget
            self.dockwidget.closingPlugin.connect(self.onClosePlugin)

            # show the dockwidget
            # TODO: fix to allow choice of dock location
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
            self.dockwidget.show()

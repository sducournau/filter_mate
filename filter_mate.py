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

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QApplication, QMenu, QMessageBox
from qgis.utils import iface
from qgis.core import QgsMessageLog, Qgis
from functools import partial
import shutil
import json

# Initialize Qt resources from file resources.py
from .resources import *  # Qt resources must be imported with wildcard
import os
import os.path
from .filter_mate_app import FilterMateApp
from .config.config import ENV_VARS, init_env_vars

class FilterMate:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """

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
        self.app = False


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
        
        # Action principale pour ouvrir FilterMate
        self.add_action(
            icon_path,
            text=self.tr(u'FilterMate'),
            callback=self.run,
            parent=self.iface.mainWindow(),
            status_tip=self.tr(u'Ouvrir le panneau FilterMate'))
        
        # Action pour réinitialiser la configuration et la base de données
        reset_icon_path = ':/plugins/filter_mate/icons/reset_properties.png'
        self.add_action(
            reset_icon_path,
            text=self.tr(u'Réinitialiser config et base de données'),
            callback=self.reset_configuration,
            parent=self.iface.mainWindow(),
            add_to_toolbar=False,
            status_tip=self.tr(u'Réinitialiser la configuration par défaut et supprimer la base de données SQLite'))

    #--------------------------------------------------------------------------

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""

        #print "** CLOSING FilterMate"

        # disconnects
        self.app.dockwidget.closingPlugin.disconnect(self.onClosePlugin)

        # remove this statement if dockwidget is to remain
        # for reuse if plugin is reopened
        # Commented next statement since it causes QGIS crashe
        # when closing the docked window:
        # self.dockwidget = None
        #self.app = None

        self.pluginIsActive = False


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
        
        # Nettoyer les ressources de l'application FilterMate
        if self.app:
            self.app.cleanup()

        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Filtrage des couches'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    #--------------------------------------------------------------------------
    
    # def reload_config(self):
    #     """Create qtreeview model configuration from json file"""
    #     self.edit_config_json()
    #     global CONFIG_SCOPE, CONFIG_DATA
    #     if CONFIG_SCOPE:

    #         self.managerWidgets.manage_widgets(CONFIG_DATA['WIDGETS'])



    #             #item = self.dockwidget.WIDGETS.layout().itemAtPosition(i,1)
    #             #self.dockwidget.WIDGETS.layout().removeItem(item)
    #             #item = self.dockwidget.WIDGETS.layout().itemAtPosition(i,0)
    #             #self.dockwidget.WIDGETS.layout().removeItem(item)



    #         CONFIG_SCOPE = False



    # def edit_config_json(self):
    #     """Write qtreeview model configuration to json file"""
    #     global LAYERS,COLORS, CONFIG_DATA, DIR_PROFILE
    #     CONFIG_DATA = self.managerWidgets.model.serialize()
    #     LAYERS = CONFIG_DATA['LAYERS']
    #     COLORS = CONFIG_DATA['COLORS']
    #     print('reload config')
    #     with open(DIR_PLUGIN + '/config/config.json', 'w') as outfile:
    #         json.dump(CONFIG_DATA, outfile)

    # def qtree_signal(self):
    #     """Signal to overload configuration qtreeview model to keep configuration file up to date"""
    #     global CONFIG_SCOPE
    #     CONFIG_SCOPE = True

    def reset_configuration(self):
        """Reset the configuration to default values and optionally delete the SQLite database.
        
        This method:
        1. Copies config.default.json to config.json
        2. Optionally deletes the SQLite database file
        3. Prompts user to restart QGIS for changes to take effect
        """
        from qgis.PyQt.QtWidgets import QMessageBox
        import shutil
        
        # Ask for confirmation
        reply = QMessageBox.question(
            self.iface.mainWindow(),
            self.tr('Réinitialiser la configuration'),
            self.tr('Êtes-vous sûr de vouloir réinitialiser la configuration par défaut ?\n\n'
                   'Cette action va :\n'
                   '- Restaurer les paramètres par défaut\n'
                   '- Supprimer la base de données des couches\n\n'
                   'QGIS devra être redémarré pour appliquer les changements.'),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            config_dir = os.path.join(self.plugin_dir, 'config')
            config_file = os.path.join(config_dir, 'config.json')
            default_config_file = os.path.join(config_dir, 'config.default.json')
            
            # Copy default config to config.json
            if os.path.exists(default_config_file):
                shutil.copy2(default_config_file, config_file)
                self.iface.messageBar().pushSuccess(
                    "FilterMate",
                    self.tr("Configuration réinitialisée avec succès.")
                )
            else:
                self.iface.messageBar().pushWarning(
                    "FilterMate",
                    self.tr("Fichier de configuration par défaut introuvable.")
                )
                return
            
            # Try to delete SQLite database
            from config.config import ENV_VARS, init_env_vars
            
            # Re-initialize to get current paths
            try:
                init_env_vars()
                plugin_config_dir = ENV_VARS.get("PLUGIN_CONFIG_DIRECTORY", "")
                
                if plugin_config_dir and os.path.isdir(plugin_config_dir):
                    # Look for SQLite files
                    for filename in os.listdir(plugin_config_dir):
                        if filename.endswith('.db') or filename.endswith('.sqlite'):
                            db_path = os.path.join(plugin_config_dir, filename)
                            try:
                                os.remove(db_path)
                                self.iface.messageBar().pushInfo(
                                    "FilterMate",
                                    self.tr(f"Base de données supprimée : {filename}")
                                )
                            except OSError as e:
                                self.iface.messageBar().pushWarning(
                                    "FilterMate",
                                    self.tr(f"Impossible de supprimer {filename}: {e}")
                                )
            except Exception as e:
                # Non-critical error, config was already reset
                pass
            
            # Prompt to restart QGIS
            QMessageBox.information(
                self.iface.mainWindow(),
                self.tr('Redémarrage requis'),
                self.tr('La configuration a été réinitialisée.\n\n'
                       'Veuillez redémarrer QGIS pour appliquer les changements.')
            )
            
        except Exception as e:
            self.iface.messageBar().pushCritical(
                "FilterMate",
                self.tr(f"Erreur lors de la réinitialisation : {str(e)}")
            )


    def run(self):
        """Run method that loads and starts the plugin"""

        if not self.pluginIsActive:
            self.pluginIsActive = True

            #print "** STARTING FilterMate"

            try:
                # dockwidget may not exist if:
                #    first run of plugin
                #    removed on close (see self.onClosePlugin method)
                if not self.app:
                    # Create app WITHOUT calling run() automatically
                    self.app = FilterMateApp(self.plugin_dir)
                    # NOW call run() after QGIS is stable and user clicked the button
                    self.app.run()
                    self.app.dockwidget.closingPlugin.connect(self.onClosePlugin)
                else:
                    # App already exists, just show the dockwidget
                    self.app.run()
                    self.app.dockwidget.closingPlugin.connect(self.onClosePlugin)
                    self.app.dockwidget.show()
            except Exception as e:
                iface.messageBar().pushCritical(
                    "FilterMate",
                    f"Error loading plugin: {str(e)}. Check QGIS Python console for details."
                )
                import traceback
                print(f"FilterMate Error: {traceback.format_exc()}")
                self.pluginIsActive = False
            




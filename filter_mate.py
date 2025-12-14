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
from .modules.logging_config import get_logger

logger = get_logger(__name__)

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

        # initialize locale - Support for EN, FR, PT, ES
        # Check if a forced language is set in config.json
        forced_locale = self._get_config_language()
        
        if forced_locale and forced_locale != 'auto':
            # Use forced language from config
            locale = forced_locale
            logger.info(f"FilterMate: Using forced language from config: '{locale}'")
        else:
            # Use QGIS locale (default behavior)
            locale_setting = QSettings().value('locale/userLocale')
            locale = locale_setting[0:2] if locale_setting else 'en'
        
        # Supported languages
        supported_languages = ['en', 'fr', 'pt', 'es', 'it', 'de', 'nl']
        if locale not in supported_languages:
            logger.info(f"FilterMate: Language '{locale}' not supported, falling back to English")
            locale = 'en'
        
        # Try to load the translation for the current locale
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'FilterMate_{}.qm'.format(locale))
        
        # Fallback to English if the locale is not available
        if not os.path.exists(locale_path):
            locale_path = os.path.join(
                self.plugin_dir,
                'i18n',
                'FilterMate_en.qm')
        
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            if self.translator.load(locale_path):
                QCoreApplication.installTranslator(self.translator)
                logger.info(f"FilterMate: Loaded translation for locale '{locale}'")
            else:
                logger.warning(f"FilterMate: Failed to load translation from {locale_path}")

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&FilterMate')
        # TODO: We are going to let the user set this up in a future iteration

        self.toolbar = self.iface.addToolBar(u'FilterMate')
        self.toolbar.setObjectName(u'FilterMate')

        #print "** INITIALIZING FilterMate"

        self.pluginIsActive = False
        self.app = False
        self._auto_activation_signals_connected = False
        self._project_read_connection = None
        self._new_project_connection = None

    def _get_config_language(self):
        """Get the language setting from config.json.
        
        Returns:
            str: Language code ('auto', 'en', 'fr', 'pt', 'es') or None if not set
        """
        try:
            config_path = os.path.join(self.plugin_dir, 'config', 'config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    language = config.get('APP', {}).get('DOCKWIDGET', {}).get('LANGUAGE', {}).get('value', 'auto')
                    return language
        except Exception as e:
            logger.warning(f"FilterMate: Could not read language from config: {e}")
        return 'auto'

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
            self.iface.addPluginToVectorMenu(
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
        reset_icon_path = ':/plugins/filter_mate/icons/parameters.png'
        self.add_action(
            reset_icon_path,
            text=self.tr(u'Réinitialiser config et base de données'),
            callback=self.reset_configuration,
            parent=self.iface.mainWindow(),
            add_to_toolbar=False,
            status_tip=self.tr(u'Réinitialiser la configuration par défaut et supprimer la base de données SQLite'))
        
        # Auto-activation disabled - user must manually click the toolbar button to open the plugin
        # To re-enable auto-activation when layers are added or project is loaded, uncomment the line below:
        # self._connect_auto_activation_signals()

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
    
    def _connect_auto_activation_signals(self):
        """Connect signals to auto-activate plugin when layers are added or project is loaded."""
        if not self._auto_activation_signals_connected:
            from qgis.core import QgsProject
            from qgis.PyQt.QtCore import QTimer
            from qgis.utils import iface as qgis_iface
            
            project = QgsProject.instance()
            layer_store = project.layerStore()
            
            # Auto-activate when layers are added
            layer_store.layersAdded.connect(self._auto_activate_plugin)
            
            # Store lambda references for proper disconnection
            self._project_read_connection = lambda: QTimer.singleShot(100, self._auto_activate_plugin)
            self._new_project_connection = lambda: QTimer.singleShot(100, self._auto_activate_plugin)
            
            # Auto-activate when a project is opened
            self.iface.projectRead.connect(self._project_read_connection)
            # Auto-activate when a new project is created with layers
            self.iface.newProjectCreated.connect(self._new_project_connection)
            
            self._auto_activation_signals_connected = True
            logger.info("FilterMate: Auto-activation signals connected")
            # Message bar notification removed - too verbose for UX
    
    def _auto_activate_plugin(self, layers=None):
        """Auto-activate plugin if not already active.
        
        When called with the plugin inactive:
            - Checks for vector layers in the project
            - If found, activates the plugin by calling run()
            
        When called with the plugin already active but dockwidget hidden:
            - Shows the dockwidget and processes new layers
            
        When called with the plugin already active and dockwidget visible:
            - Triggers project reinitialization via FilterMateApp
              to handle project switch (clear old data, load new layers)
        
        Args:
            layers: Optional list of layers that were just added (from layersAdded signal)
        """
        from qgis.core import QgsProject, QgsVectorLayer
        from qgis.PyQt.QtCore import QTimer
        from qgis.utils import iface as qgis_iface
        
        # If plugin is already active, handle project change
        if self.pluginIsActive:
            if self.app and hasattr(self.app, 'dockwidget') and self.app.dockwidget:
                # CRITICAL: Skip if app is already initializing a project 
                # This prevents multiple calls from projectRead + layersAdded signals
                if hasattr(self.app, '_initializing_project') and self.app._initializing_project:
                    logger.debug("FilterMate: Skipping _auto_activate_plugin - already initializing project")
                    return
                if hasattr(self.app, '_loading_new_project') and self.app._loading_new_project:
                    logger.debug("FilterMate: Skipping _auto_activate_plugin - loading new project")
                    return
                    
                # CRITICAL: When a new project is loaded while plugin is active,
                # we need to reinitialize the app with the new project data.
                # Use QTimer to defer and avoid blocking during project load.
                logger.info("FilterMate: Project changed while plugin active - deferring reinitialization")
                QTimer.singleShot(200, lambda: self._handle_project_change())
                return
            return
        
        # Plugin not active - check if there are vector layers to activate for
        project = QgsProject.instance()
        vector_layers = [layer for layer in project.mapLayers().values() 
                        if isinstance(layer, QgsVectorLayer)]
        
        if not vector_layers:
            logger.debug("FilterMate: No vector layers found - plugin will not auto-activate")
            return  # No vector layers to process
        
        # Plugin not active and we have vector layers - activate it
        # Use QTimer to ensure QGIS is in a stable state before activation
        logger.info(f"FilterMate: Auto-activating plugin ({len(vector_layers)} vector layer(s) detected)")
        # Message bar notification removed - too verbose for UX
        
        # Defer activation to next event loop iteration for stability
        QTimer.singleShot(50, self.run)

    def _handle_project_change(self):
        """Handle project change when plugin is already active.
        
        Reinitializes FilterMateApp with new project data without recreating
        the dockwidget. This is called when projectRead signal is emitted
        while the plugin is already active.
        """
        from qgis.core import QgsProject, QgsVectorLayer
        
        if not self.app:
            return
        
        # CRITICAL: Check if app is already initializing a project
        if hasattr(self.app, '_initializing_project') and self.app._initializing_project:
            logger.debug("FilterMate: Skipping _handle_project_change - already initializing")
            return
        
        # CRITICAL: Also check if loading is in progress
        if hasattr(self.app, '_loading_new_project') and self.app._loading_new_project:
            logger.debug("FilterMate: Skipping _handle_project_change - loading new project")
            return
        
        project = QgsProject.instance()
        if not project:
            return
        
        # Check if there are vector layers in the new project
        vector_layers = [layer for layer in project.mapLayers().values() 
                        if isinstance(layer, QgsVectorLayer)]
        
        if not vector_layers:
            logger.info("FilterMate: New project has no vector layers")
            # Clear old data and disable UI
            if hasattr(self.app, 'PROJECT_LAYERS'):
                self.app.PROJECT_LAYERS = {}
            # Only access dockwidget if it exists and has widgets_initialized
            if (self.app.dockwidget and 
                hasattr(self.app.dockwidget, 'widgets_initialized') and 
                self.app.dockwidget.widgets_initialized):
                self.app.dockwidget.set_widgets_enabled_state(False)
            return
        
        logger.info(f"FilterMate: Reinitializing for new project with {len(vector_layers)} vector layers")
        
        # Reinitialize the app for the new project
        try:
            # Call the existing project initialization handler
            self.app._handle_project_initialization('project_read')
        except Exception as e:
            logger.error(f"FilterMate: Error during project reinitialization: {e}")


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        #print "** UNLOAD FilterMate"
        
        # Disconnect auto-activation signals
        if self._auto_activation_signals_connected:
            from qgis.core import QgsProject
            
            try:
                project = QgsProject.instance()
                layer_store = project.layerStore()
                
                layer_store.layersAdded.disconnect(self._auto_activate_plugin)
                
                if self._project_read_connection:
                    self.iface.projectRead.disconnect(self._project_read_connection)
                if self._new_project_connection:
                    self.iface.newProjectCreated.disconnect(self._new_project_connection)
                
                logger.info("FilterMate: Auto-activation signals disconnected")
            except Exception as e:
                logger.warning(f"FilterMate: Error disconnecting auto-activation signals: {e}")
        
        # Nettoyer les ressources de l'application FilterMate
        if self.app:
            self.app.cleanup()

        for action in self.actions:
            self.iface.removePluginVectorMenu(
                self.menu,
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
            from .config.config import ENV_VARS, init_env_vars
            
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
                    # App already exists, call run() which will show the dockwidget
                    # and refresh layers if needed
                    self.app.run()
                    # Reconnect closingPlugin signal only if not already connected
                    # Use try/except to safely disconnect then reconnect
                    try:
                        self.app.dockwidget.closingPlugin.disconnect(self.onClosePlugin)
                    except TypeError:
                        pass  # Not connected, ignore
                    self.app.dockwidget.closingPlugin.connect(self.onClosePlugin)
            except Exception as e:
                iface.messageBar().pushCritical(
                    "FilterMate",
                    f"Error loading plugin: {str(e)}. Check QGIS Python console for details."
                )
                import traceback
                logger.error(f"Error loading plugin: {traceback.format_exc()}")
                self.pluginIsActive = False
            




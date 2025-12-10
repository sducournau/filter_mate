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

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QTimer
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QApplication, QMenu, QMessageBox
from qgis.utils import iface, reloadPlugin
from qgis.core import QgsMessageLog, Qgis
from functools import partial

# Initialize Qt resources from file resources.py
from .resources import *
import os
import os.path
from .filter_mate_app import *
from .config.config import reset_config_to_default, reload_config

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
        
        # Action principale dans la toolbar (lance le plugin)
        self.add_action(
            icon_path,
            text=self.tr(u'FilterMate'),
            callback=self.run,
            add_to_menu=False,  # On gère le menu manuellement
            parent=self.iface.mainWindow())
        
        # Créer un sous-menu FilterMate
        self.submenu = QMenu(self.tr(u'&FilterMate'), self.iface.mainWindow())
        self.submenu.setIcon(QIcon(icon_path))
        
        # Action 1: Lancer FilterMate
        self.action_run = QAction(
            QIcon(icon_path),
            self.tr(u'Ouvrir FilterMate'),
            self.iface.mainWindow()
        )
        self.action_run.triggered.connect(self.run)
        self.submenu.addAction(self.action_run)
        self.actions.append(self.action_run)
        
        # Séparateur
        self.submenu.addSeparator()
        
        # Action 2: Réinitialiser la configuration
        reset_icon_path = os.path.join(self.plugin_dir, 'icons', 'parameters.png')
        self.action_reset_config = QAction(
            QIcon(reset_icon_path),
            self.tr(u'Réinitialiser la configuration'),
            self.iface.mainWindow()
        )
        self.action_reset_config.triggered.connect(self.reset_configuration)
        self.submenu.addAction(self.action_reset_config)
        self.actions.append(self.action_reset_config)
        
        # Action 3: Supprimer la base SQLite
        delete_icon_path = os.path.join(self.plugin_dir, 'icons', 'reset.png')
        self.action_delete_sqlite = QAction(
            QIcon(delete_icon_path),
            self.tr(u'Supprimer la base SQLite'),
            self.iface.mainWindow()
        )
        self.action_delete_sqlite.triggered.connect(self.delete_sqlite_database)
        self.submenu.addAction(self.action_delete_sqlite)
        self.actions.append(self.action_delete_sqlite)
        
        # Ajouter le sous-menu au menu Plugins
        self.iface.pluginMenu().addMenu(self.submenu)

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


    def reset_configuration(self):
        """Reset configuration to default values with user confirmation."""
        
        # Boîte de dialogue de confirmation
        reply = QMessageBox.question(
            self.iface.mainWindow(),
            'FilterMate - Réinitialisation',
            'Voulez-vous réinitialiser la configuration de FilterMate aux valeurs par défaut ?\n\n'
            'Cette action va :\n'
            '• Réinitialiser tous les paramètres\n'
            '• Créer une sauvegarde de la configuration actuelle\n'
            '• Préserver le chemin de la base de données SQLite\n\n'
            'Le plugin devra être rechargé après la réinitialisation.',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # Fermer le plugin s'il est ouvert
                if self.pluginIsActive and self.app:
                    self.app.dockwidget.close()
                    self.pluginIsActive = False
                
                # Réinitialiser la configuration
                success = reset_config_to_default(
                    backup=True,
                    preserve_app_settings=True
                )
                
                if success:
                    # Recharger la configuration
                    reload_config()
                    
                    # Message de succès
                    iface.messageBar().pushSuccess(
                        "FilterMate",
                        "Configuration réinitialisée avec succès. Recréation des fichiers..."
                    )
                    
                    QgsMessageLog.logMessage(
                        "Configuration reset completed successfully. Recreating necessary files...",
                        "FilterMate",
                        Qgis.Success
                    )
                    
                    # Recréer les fichiers nécessaires avec valeurs par défaut
                    self._recreate_default_files()
                    
                    # Recharger le plugin automatiquement après un court délai
                    QTimer.singleShot(1000, lambda: self._reload_plugin_safely())
                else:
                    raise Exception("reset_config_to_default returned False")
                    
            except Exception as e:
                error_msg = f"Erreur lors de la réinitialisation : {str(e)}"
                QMessageBox.critical(
                    self.iface.mainWindow(),
                    'FilterMate - Erreur',
                    error_msg,
                    QMessageBox.Ok
                )
                
                iface.messageBar().pushCritical(
                    "FilterMate",
                    error_msg
                )
                
                QgsMessageLog.logMessage(
                    f"Configuration reset failed: {str(e)}",
                    "FilterMate",
                    Qgis.Critical
                )
                
                import traceback
                QgsMessageLog.logMessage(
                    traceback.format_exc(),
                    "FilterMate",
                    Qgis.Critical
                )


    def delete_sqlite_database(self):
        """Delete the SQLite database after user confirmation."""
        from .config.config import ENV_VARS
        
        try:
            # Get database path from config
            config_data = ENV_VARS.get('CONFIG_DATA', {})
            sqlite_path = config_data.get('APP', {}).get('OPTIONS', {}).get('APP_SQLITE_PATH', None)
            
            QgsMessageLog.logMessage(
                f"Delete SQLite DB - sqlite_path from config: {sqlite_path}",
                "FilterMate",
                Qgis.Info
            )
            
            if not sqlite_path:
                QMessageBox.warning(
                    self.iface.mainWindow(),
                    'FilterMate - Base SQLite',
                    'Impossible de trouver le chemin de la base SQLite dans la configuration.',
                    QMessageBox.Ok
                )
                return
            
            # Find all .db and .sqlite files in the directory
            db_files = []
            if os.path.exists(sqlite_path):
                all_files = os.listdir(sqlite_path)
                QgsMessageLog.logMessage(
                    f"Delete SQLite DB - Files in directory: {all_files}",
                    "FilterMate",
                    Qgis.Info
                )
                for file in all_files:
                    if file.endswith('.db') or file.endswith('.sqlite'):
                        db_files.append(os.path.join(sqlite_path, file))
            else:
                QgsMessageLog.logMessage(
                    f"Delete SQLite DB - Directory does not exist: {sqlite_path}",
                    "FilterMate",
                    Qgis.Warning
                )
            
            QgsMessageLog.logMessage(
                f"Delete SQLite DB - Found {len(db_files)} database file(s): {db_files}",
                "FilterMate",
                Qgis.Info
            )
            
            if not db_files:
                # Get list of all files in directory for debug
                all_files_info = []
                if os.path.exists(sqlite_path):
                    all_files_info = [f for f in os.listdir(sqlite_path) if os.path.isfile(os.path.join(sqlite_path, f))]
                
                message = f'Aucune base de données SQLite (.db ou .sqlite) trouvée dans :\n{sqlite_path}'
                if all_files_info:
                    message += f'\n\nFichiers présents dans le répertoire :\n' + '\n'.join(all_files_info[:10])
                    if len(all_files_info) > 10:
                        message += f'\n... et {len(all_files_info) - 10} autre(s) fichier(s)'
                
                QMessageBox.information(
                    self.iface.mainWindow(),
                    'FilterMate - Base SQLite',
                    message,
                    QMessageBox.Ok
                )
                return
            
            # Confirmation dialog
            db_list = '\n'.join([os.path.basename(f) for f in db_files])
            reply = QMessageBox.question(
                self.iface.mainWindow(),
                'FilterMate - Supprimer la base SQLite',
                f'Voulez-vous supprimer la(les) base(s) de données SQLite ?\n\n'
                f'Fichiers trouvés :\n{db_list}\n\n'
                f'Chemin : {sqlite_path}\n\n'
                f'⚠️ ATTENTION : Cette action est irréversible !\n'
                f'Toutes les données (historique, favoris, etc.) seront perdues.\n\n'
                f'Le plugin devra être redémarré après la suppression.',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Close plugin if active
                if self.pluginIsActive and self.app:
                    self.app.dockwidget.close()
                    self.pluginIsActive = False
                
                # Delete database files
                deleted_files = []
                failed_files = []
                
                for db_file in db_files:
                    try:
                        os.remove(db_file)
                        deleted_files.append(os.path.basename(db_file))
                        QgsMessageLog.logMessage(
                            f"Deleted SQLite database: {db_file}",
                            "FilterMate",
                            Qgis.Info
                        )
                    except Exception as e:
                        failed_files.append(f"{os.path.basename(db_file)}: {str(e)}")
                        QgsMessageLog.logMessage(
                            f"Failed to delete {db_file}: {str(e)}",
                            "FilterMate",
                            Qgis.Warning
                        )
                
                # Show results
                if deleted_files and not failed_files:
                    deleted_list = '\n'.join(deleted_files)
                    iface.messageBar().pushSuccess(
                        "FilterMate",
                        f"Base SQLite supprimée avec succès ({len(deleted_files)} fichier(s)). Recréation des fichiers..."
                    )
                    QgsMessageLog.logMessage(
                        f"SQLite database(s) deleted successfully: {deleted_list}. Recreating files...",
                        "FilterMate",
                        Qgis.Success
                    )
                    
                    # Recréer les fichiers nécessaires avec valeurs par défaut
                    self._recreate_default_files()
                    
                    # Recharger le plugin automatiquement après un court délai
                    QTimer.singleShot(1000, lambda: self._reload_plugin_safely())
                    
                elif deleted_files and failed_files:
                    deleted_list = '\n'.join(deleted_files)
                    failed_list = '\n'.join(failed_files)
                    QMessageBox.warning(
                        self.iface.mainWindow(),
                        'FilterMate - Suppression partielle',
                        f'Fichiers supprimés :\n{deleted_list}\n\n'
                        f'Échecs :\n{failed_list}\n\n'
                        f'Le plugin sera rechargé.',
                        QMessageBox.Ok
                    )
                    iface.messageBar().pushWarning(
                        "FilterMate",
                        "Base SQLite partiellement supprimée. Recréation des fichiers..."
                    )
                    
                    # Recréer les fichiers même en cas de suppression partielle
                    self._recreate_default_files()
                    
                    # Recharger même en cas de suppression partielle
                    QTimer.singleShot(1000, lambda: self._reload_plugin_safely())
                else:
                    failed_list = '\n'.join(failed_files)
                    QMessageBox.critical(
                        self.iface.mainWindow(),
                        'FilterMate - Erreur',
                        f'Impossible de supprimer les fichiers :\n{failed_list}',
                        QMessageBox.Ok
                    )
                    iface.messageBar().pushCritical(
                        "FilterMate",
                        "Échec de la suppression de la base SQLite"
                    )
        
        except Exception as e:
            error_msg = f"Erreur lors de la suppression : {str(e)}"
            QMessageBox.critical(
                self.iface.mainWindow(),
                'FilterMate - Erreur',
                error_msg,
                QMessageBox.Ok
            )
            
            iface.messageBar().pushCritical(
                "FilterMate",
                error_msg
            )
            
            QgsMessageLog.logMessage(
                f"SQLite deletion failed: {str(e)}",
                "FilterMate",
                Qgis.Critical
            )
            
            import traceback
            QgsMessageLog.logMessage(
                traceback.format_exc(),
                "FilterMate",
                Qgis.Critical
            )


    def _recreate_default_files(self):
        """
        Recreate necessary files with default values.
        
        This method is called after configuration reset or database deletion
        to ensure all required files exist before reloading the plugin.
        
        Files created:
        - config.json in PLUGIN_CONFIG_DIRECTORY (if missing)
        - filterMate_db.sqlite will be created automatically on plugin run
        """
        from .config.config import ENV_VARS, get_config_path
        
        try:
            # Get the plugin config directory
            config_data = ENV_VARS.get('CONFIG_DATA', {})
            plugin_config_dir = config_data.get('APP', {}).get('OPTIONS', {}).get('APP_SQLITE_PATH', None)
            
            if not plugin_config_dir:
                QgsMessageLog.logMessage(
                    "Cannot recreate files: APP_SQLITE_PATH not found in configuration",
                    "FilterMate",
                    Qgis.Warning
                )
                return
            
            # Ensure the directory exists
            if not os.path.exists(plugin_config_dir):
                try:
                    os.makedirs(plugin_config_dir, exist_ok=True)
                    QgsMessageLog.logMessage(
                        f"Created plugin config directory: {plugin_config_dir}",
                        "FilterMate",
                        Qgis.Info
                    )
                except OSError as error:
                    QgsMessageLog.logMessage(
                        f"Failed to create directory {plugin_config_dir}: {error}",
                        "FilterMate",
                        Qgis.Critical
                    )
                    return
            
            # Recreate config.json if it doesn't exist
            config_path = get_config_path()
            if not os.path.exists(config_path):
                try:
                    import json
                    with open(config_path, 'w') as f:
                        f.write(json.dumps(config_data, indent=4))
                    QgsMessageLog.logMessage(
                        f"Created config.json at {config_path}",
                        "FilterMate",
                        Qgis.Info
                    )
                except Exception as e:
                    QgsMessageLog.logMessage(
                        f"Failed to create config.json: {e}",
                        "FilterMate",
                        Qgis.Warning
                    )
            
            # Note: filterMate_db.sqlite will be automatically created by init_filterMate_db()
            # when the plugin runs, so we don't need to create it here
            
            QgsMessageLog.logMessage(
                "Default files recreation completed",
                "FilterMate",
                Qgis.Success
            )
            
        except Exception as e:
            error_msg = f"Error recreating default files: {str(e)}"
            QgsMessageLog.logMessage(
                error_msg,
                "FilterMate",
                Qgis.Critical
            )
            
            import traceback
            QgsMessageLog.logMessage(
                traceback.format_exc(),
                "FilterMate",
                Qgis.Critical
            )


    def _reload_plugin_safely(self):
        """
        Safely reload the FilterMate plugin.
        
        This method is called after configuration reset or database deletion
        to automatically reload the plugin with fresh settings.
        """
        try:
            QgsMessageLog.logMessage(
                "Attempting to reload FilterMate plugin...",
                "FilterMate",
                Qgis.Info
            )
            
            # Recharger le plugin
            reloadPlugin('filter_mate')
            
            QgsMessageLog.logMessage(
                "FilterMate plugin reloaded successfully",
                "FilterMate",
                Qgis.Success
            )
            
            iface.messageBar().pushSuccess(
                "FilterMate",
                "Plugin rechargé avec succès"
            )
            
        except Exception as e:
            error_msg = f"Erreur lors du rechargement du plugin : {str(e)}"
            QgsMessageLog.logMessage(
                error_msg,
                "FilterMate",
                Qgis.Critical
            )
            
            iface.messageBar().pushWarning(
                "FilterMate",
                "Veuillez recharger manuellement le plugin"
            )
            
            import traceback
            QgsMessageLog.logMessage(
                traceback.format_exc(),
                "FilterMate",
                Qgis.Critical
            )


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

        # Supprimer le sous-menu
        if hasattr(self, 'submenu'):
            self.iface.pluginMenu().removeAction(self.submenu.menuAction())
            self.submenu.deleteLater()
        
        # Supprimer les actions de la toolbar
        for action in self.actions:
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


    def run(self):
        """Run method that loads and starts the plugin"""

        if not self.pluginIsActive:
            self.pluginIsActive = True

            #print "** STARTING FilterMate"

            try:
                from .modules.signal_utils import safe_connect
                
                # dockwidget may not exist if:
                #    first run of plugin
                #    removed on close (see self.onClosePlugin method)
                if not self.app:
                    # Create app WITHOUT calling run() automatically
                    self.app = FilterMateApp(self.plugin_dir)
                    # NOW call run() after QGIS is stable and user clicked the button
                    self.app.run()
                    safe_connect(self.app.dockwidget.closingPlugin, self.onClosePlugin)
                else:
                    # App already exists, just show the dockwidget
                    self.app.run()
                    safe_connect(self.app.dockwidget.closingPlugin, self.onClosePlugin)
                    self.app.dockwidget.show()
            except Exception as e:
                iface.messageBar().pushCritical(
                    "FilterMate",
                    f"Error loading plugin: {str(e)}. Check QGIS Python console for details."
                )
                import traceback
                print(f"FilterMate Error: {traceback.format_exc()}")
                self.pluginIsActive = False
            




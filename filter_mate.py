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
from qgis.PyQt.QtWidgets import QAction, QMessageBox
import weakref

# Initialize Qt resources from file resources.py
from .resources import *  # Qt resources must be imported with wildcard
import os
import os.path
from .filter_mate_app import FilterMateApp
from .config.config import reload_config
from .infrastructure.logging import get_logger

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

        # initialize locale
        # Try to load config to check for forced language setting
        config_language = None
        try:
            import json
            config_path = os.path.join(self.plugin_dir, 'config', 'config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    # Support both old format (APP.DOCKWIDGET.LANGUAGE) and new format (app.ui.language)
                    config_language = (
                        config_data.get('app', {}).get('ui', {}).get('language', {}).get('value') or
                        config_data.get('APP', {}).get('DOCKWIDGET', {}).get('LANGUAGE', {}).get('value') or
                        'auto'
                    )
        except Exception as e:
            logger.warning(f"Could not load language from config: {e}")
        
        # Determine locale: use config if not 'auto', otherwise use QGIS setting
        if config_language and config_language != 'auto':
            locale = config_language
        else:
            # Get QGIS locale setting
            locale_setting = QSettings().value('locale/userLocale')
            if locale_setting:
                # Handle both 'fr' and 'fr_FR' formats
                locale = locale_setting.split('_')[0] if '_' in locale_setting else locale_setting[0:2]
            else:
                locale = 'en'
        
        logger.debug(f"Language detection: config_language={config_language}, locale_setting={QSettings().value('locale/userLocale')}, final locale={locale}")
        
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'FilterMate_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)
            logger.info(f"Loaded translation: {locale}")
        else:
            logger.warning(f"Translation file not found: {locale_path}")

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&FilterMate')
        # TODO: We are going to let the user set this up in a future iteration

        self.toolbar = self.iface.addToolBar(u'FilterMate')
        self.toolbar.setObjectName(u'FilterMate')

        #print "** INITIALIZING FilterMate"

        self.pluginIsActive = False
        self.app = None
        self._auto_activation_signals_connected = False
        self._project_read_connection = None
        self._new_project_connection = None


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
        
        try:
            # Install message log filter to suppress known QGIS warnings about missing form dependencies
            logger.debug("FilterMate.initGui: Starting _install_message_filter")
            self._install_message_filter()
            
            # Force reload configuration from disk to get latest user changes
            logger.debug("FilterMate.initGui: Starting reload_config")
            reload_config()
            
            # Auto-migrate configuration if needed
            logger.debug("FilterMate.initGui: Starting _auto_migrate_config")
            self._auto_migrate_config()
            
            # Check and warn about invalid geometry filtering settings
            logger.debug("FilterMate.initGui: Starting _check_geometry_validation_settings")
            self._check_geometry_validation_settings()

            logger.debug("FilterMate.initGui: Creating actions")
            icon_path = ':/plugins/filter_mate/icon.png'
            
            # Main action to open FilterMate
            self.add_action(
                icon_path,
                text=self.tr(u'FilterMate'),
                callback=self.run,
                parent=self.iface.mainWindow(),
                status_tip=self.tr(u'Open FilterMate panel'))
            
            # Action to reset configuration and database
            reset_icon_path = ':/plugins/filter_mate/icons/parameters.png'
            self.add_action(
                reset_icon_path,
                text=self.tr(u'Reset configuration and database'),
                callback=self.reset_configuration,
                parent=self.iface.mainWindow(),
                add_to_toolbar=False,
                status_tip=self.tr(u'Reset the default configuration and delete the SQLite database'))
            
            # Connect signals to handle project changes and automatically reload layers
            # Note: layersAdded signal is NOT connected to avoid freeze issues
            logger.debug("FilterMate.initGui: Connecting auto-activation signals")
            self._connect_auto_activation_signals()
            logger.debug("FilterMate.initGui: Completed successfully")
            
        except Exception as e:
            import traceback
            error_msg = f"Error in initGui: {str(e)}"
            traceback_msg = traceback.format_exc()
            logger.error(error_msg)
            logger.error(f"Traceback: {traceback_msg}")
            self.iface.messageBar().pushCritical(
                "FilterMate",
                f"Initialization error: {str(e)}"
            )
            # Re-raise to prevent partial initialization
            raise

    #--------------------------------------------------------------------------

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""

        #print "** CLOSING FilterMate"

        # disconnects
        if self.app and self.app.dockwidget:
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
            path = str(self.plugin_dir) + os.sep + 'images'

            for item in args:
                path = path + os.sep + item



            return path
    
    def _confirm_config_reset(self, reason: str, version: str) -> bool:
        """
        Ask user for confirmation before resetting configuration.
        
        Args:
            reason: Reason for reset ('obsolete', 'corrupted')
            version: Detected version (may be None)
        
        Returns:
            True if user confirms reset, False otherwise
        """
        if reason == "obsolete":
            title = self.tr("Obsolete configuration detected")
            version_str = f"v{version}" if version else self.tr("unknown version")
            message = self.tr(
                "An obsolete configuration ({}) has been detected.\n\n"
                "Do you want to reset to default settings?\n\n"
                "• Yes: Reset (a backup will be created)\n"
                "• No: Keep current configuration (may cause issues)"
            ).format(version_str)
        elif reason == "corrupted":
            title = self.tr("Corrupted configuration detected")
            message = self.tr(
                "The configuration file is corrupted and cannot be read.\n\n"
                "Do you want to reset to default settings?\n\n"
                "• Yes: Reset (a backup will be created if possible)\n"
                "• No: Cancel (the plugin may not work correctly)"
            )
        else:
            title = self.tr("Configuration reset")
            message = self.tr(
                "The configuration needs to be reset.\n\n"
                "Do you want to continue?"
            )
        
        reply = QMessageBox.question(
            self.iface.mainWindow(),
            title,
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        return reply == QMessageBox.Yes
    
    def _auto_migrate_config(self):
        """Auto-migrate configuration to latest version if needed.
        
        If an obsolete or corrupted configuration is detected, asks the user
        for confirmation before resetting to default values.
        """
        try:
            from .infrastructure.config.config_migration import ConfigMigration
            
            migrator = ConfigMigration()
            
            # Pass the confirmation callback for reset operations
            result = migrator.auto_migrate_if_needed(
                confirm_reset_callback=self._confirm_config_reset
            )
            
            # Defensive: ensure result is a tuple with 2 elements
            if result is None:
                logger.warning("auto_migrate_if_needed returned None, using defaults")
                performed, warnings = False, []
            elif not isinstance(result, tuple) or len(result) != 2:
                logger.warning(f"auto_migrate_if_needed returned unexpected result: {result}")
                performed, warnings = False, []
            else:
                performed, warnings = result
            
            # Ensure warnings is a list (defensive programming)
            if warnings is None:
                warnings = []
            
            # Check if user declined reset
            if any("user declined" in str(w).lower() for w in warnings):
                logger.info("User declined configuration reset")
                self.iface.messageBar().pushWarning(
                    "FilterMate",
                    self.tr("Configuration not reset. Some features may not work correctly.")
                )
                return
            
            if performed:
                logger.info("Configuration migrated to latest version")
                
                # Determine the type of action performed
                if any("missing" in str(w).lower() for w in warnings):
                    msg = self.tr("Configuration created with default values")
                    msg_type = "info"
                elif any("corrupted" in str(w).lower() or "failed to load" in str(w).lower() for w in warnings):
                    msg = self.tr("Corrupted configuration reset. Default settings have been restored.")
                    msg_type = "warning"
                elif any("obsolete" in str(w).lower() for w in warnings):
                    msg = self.tr("Obsolete configuration reset. Default settings have been restored.")
                    msg_type = "warning"
                elif any(w.startswith("config_updated:") for w in warnings):
                    # v2.7.6: New settings sections were added
                    added_sections = []
                    for w in warnings:
                        if w.startswith("config_updated:"):
                            added_sections = w.replace("config_updated:", "").split(",")
                            break
                    
                    # Build user-friendly message
                    section_names = {
                        "GEOMETRY_SIMPLIFICATION": self.tr("Geometry Simplification"),
                        "OPTIMIZATION_THRESHOLDS": self.tr("Optimization Thresholds")
                    }
                    friendly_names = [section_names.get(s, s) for s in added_sections]
                    sections_str = ", ".join(friendly_names)
                    
                    msg = self.tr("Configuration updated: new settings available ({sections}). Access via Options menu.").format(sections=sections_str)
                    msg_type = "info"
                else:
                    msg = self.tr("Configuration updated to latest version")
                    msg_type = "success"
                
                # Display appropriate message
                if msg_type == "success":
                    self.iface.messageBar().pushSuccess("FilterMate", msg)
                elif msg_type == "warning":
                    self.iface.messageBar().pushWarning("FilterMate", msg)
                else:
                    self.iface.messageBar().pushInfo("FilterMate", msg)
            
            if warnings:
                for warning in warnings:
                    logger.warning(f"Config migration: {warning}")
        
        except Exception as e:
            import traceback
            logger.error(f"Error during config migration: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.iface.messageBar().pushCritical(
                "FilterMate",
                self.tr("Error during configuration migration: {}").format(str(e))
            )
            # Don't block plugin initialization if migration fails
    
    def _install_message_filter(self):
        """Check for layers with missing ValueRelation dependencies and optionally clear warnings.
        
        QGIS emits individual warnings for each missing layer form dependency.
        This method detects affected layers, clears the message bar after a delay,
        and shows a single consolidated informational message instead.
        
        The check is triggered:
        1. At plugin initialization (for already loaded projects)
        2. When a project is read/loaded (via readProject signal)
        """
        self._form_dependency_warning_shown = False
        self._missing_dependency_layers = set()
        
        try:
            from qgis.core import QgsProject
            from qgis.PyQt.QtCore import QTimer
            
            def check_and_clear_warnings():
                """Check all layers for missing ValueRelation dependencies and clear message bar."""
                if self._form_dependency_warning_shown:
                    return
                
                try:
                    from .infrastructure.field_utils import get_value_relation_info
                    
                    project = QgsProject.instance()
                    
                    for layer_id, layer in project.mapLayers().items():
                        if not hasattr(layer, 'fields'):
                            continue
                        
                        for field in layer.fields():
                            vr_info = get_value_relation_info(layer, field.name(), check_layer_availability=False)
                            if vr_info and not vr_info.get('layer_available', True):
                                ref_name = vr_info.get('layer_name', 'unknown')
                                self._missing_dependency_layers.add(ref_name)
                    
                    if self._missing_dependency_layers and not self._form_dependency_warning_shown:
                        self._form_dependency_warning_shown = True
                        
                        # Clear the message bar to remove QGIS's individual warnings
                        try:
                            self.iface.messageBar().clearWidgets()
                        except Exception:
                            pass
                        
                        # Show a single consolidated info message
                        count = len(self._missing_dependency_layers)
                        layers_list = ', '.join(list(self._missing_dependency_layers)[:3])
                        if count > 3:
                            layers_list += f" (+{count - 3} more)"
                        
                        self.iface.messageBar().pushInfo(
                            "FilterMate",
                            self.tr(f"{count} referenced layer(s) not loaded ({layers_list}). Using fallback display.")
                        )
                        
                        logger.info(
                            f"FilterMate: {count} referenced layer(s) not loaded. "
                            f"ValueRelation fallback active: {', '.join(self._missing_dependency_layers)}"
                        )
                
                except Exception as e:
                    logger.debug(f"FilterMate: Dependency check error (non-critical): {e}")
            
            def on_project_read(*args):
                """Handler for project read signal - reset state and schedule check."""
                # Reset state for new project
                self._form_dependency_warning_shown = False
                self._missing_dependency_layers = set()
                # Schedule check after QGIS warnings have appeared (project load is async)
                QTimer.singleShot(2000, check_and_clear_warnings)
            
            # Connect to project read signal for future project loads
            # Store reference to avoid garbage collection and allow disconnection
            self._on_project_read_handler = on_project_read
            QgsProject.instance().readProject.connect(on_project_read)
            
            # Also check now for already loaded project (e.g., plugin activated after project load)
            QTimer.singleShot(1500, check_and_clear_warnings)
            
        except Exception as e:
            logger.debug(f"FilterMate: Message filter setup note: {e}")
    
    def _check_geometry_validation_settings(self):
        """Check QGIS geometry validation settings and warn user if not disabled.
        
        FilterMate works best when QGIS's invalid geometry filtering is disabled
        (set to "Off"). When enabled, QGIS may filter out features with invalid
        geometries before FilterMate can process them, leading to missing features
        in exports and filters.
        
        This method checks the current setting and offers to disable it if needed,
        with an explanation of why this is recommended.
        """
        try:
            from qgis.core import QgsSettings
            
            # Get current geometry validation setting
            # Values: 0 = Off, 1 = QGIS validation, 2 = GEOS validation
            settings = QgsSettings()
            current_value = settings.value("qgis/digitizing/validate_geometries", 0, type=int)
            
            if current_value != 0:
                # Setting is not "Off" - need to warn user
                validation_modes = {
                    1: "QGIS",
                    2: "GEOS"
                }
                current_mode = validation_modes.get(current_value, str(current_value))
                
                title = self.tr("Geometry validation setting")
                
                message = self.tr(
                    "The QGIS setting 'Invalid features filtering' is currently "
                    "set to '{mode}'.\n\n"
                    "FilterMate recommends disabling this setting (value 'Off') "
                    "for the following reasons:\n\n"
                    "• Features with invalid geometries could be "
                    "silently excluded from exports and filters\n"
                    "• FilterMate handles geometry validation internally "
                    "with automatic repair options\n"
                    "• Some legitimate data may have geometries considered "
                    "as 'invalid' according to strict OGC rules\n\n"
                    "Do you want to disable this setting now?\n\n"
                    "• Yes: Disable filtering (recommended for FilterMate)\n"
                    "• No: Keep current setting"
                ).format(mode=current_mode)
                
                reply = QMessageBox.question(
                    self.iface.mainWindow(),
                    title,
                    message,
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                
                if reply == QMessageBox.Yes:
                    # Disable geometry validation
                    settings.setValue("qgis/digitizing/validate_geometries", 0)
                    logger.info("Geometry validation disabled by user via FilterMate startup check")
                    self.iface.messageBar().pushSuccess(
                        "FilterMate",
                        self.tr("Invalid geometry filtering disabled successfully.")
                    )
                else:
                    # User declined - just log and show info
                    logger.info(f"User declined to disable geometry validation (current: {current_mode})")
                    self.iface.messageBar().pushWarning(
                        "FilterMate",
                        self.tr("Invalid geometry filtering not modified. "
                               "Some features may be excluded from exports.")
                    )
            else:
                logger.debug("Geometry validation already disabled (Off) - no action needed")
                
        except Exception as e:
            logger.warning(f"Error checking geometry validation settings: {e}")
            # Don't block plugin initialization if check fails
    
    def _connect_auto_activation_signals(self):
        """Connect signals to handle project changes and reload layers.
        
        Connects projectRead, newProjectCreated, cleared, and layersAdded signals to automatically
        activate the plugin when layers are available. The layersAdded signal is now
        connected with proper guards to avoid freeze issues when the plugin is already active.
        
        The cleared signal is connected to handle project close/clear events, which ensures
        proper cleanup of plugin state when user creates a new project or closes current one.
        
        This behavior can be disabled by setting APP.AUTO_ACTIVATE.value to false in the configuration.
        """
        # Check if auto-activation is enabled in configuration
        from .config.config import ENV_VARS
        config_data = ENV_VARS.get('CONFIG_DATA', {})
        # Support both uppercase (config.default.json) and lowercase (migrated config.json) keys
        app_config = config_data.get('APP', config_data.get('app', {}))
        auto_activate_config = app_config.get('AUTO_ACTIVATE', app_config.get('auto_activate', {}))
        auto_activate_enabled = auto_activate_config.get('value', False)  # Default to False to prevent auto-open
        
        if not auto_activate_enabled:
            logger.info("FilterMate: Auto-activation disabled in configuration")
            # CRITICAL: If signals were previously connected, disconnect them
            self._disconnect_auto_activation_signals()
            return
        
        if not self._auto_activation_signals_connected:
            from qgis.core import QgsProject
            from qgis.PyQt.QtCore import QTimer
            
            # Store weakref and safe callbacks for proper disconnection
            # STABILITY FIX: Use weakref to prevent access violations when timer fires after object destruction
            weak_self = weakref.ref(self)
            
            def safe_auto_activate():
                strong_self = weak_self()
                if strong_self is not None:
                    strong_self._auto_activate_plugin()
            
            def safe_project_cleared():
                strong_self = weak_self()
                if strong_self is not None:
                    strong_self._handle_project_cleared()
            
            def safe_layers_added(layers):
                strong_self = weak_self()
                if strong_self is not None:
                    strong_self._auto_activate_for_new_layers(layers)
            
            # _auto_activate_plugin handles both inactive (activates) and active (reinitializes) states
            self._project_read_connection = lambda: QTimer.singleShot(100, safe_auto_activate)
            self._new_project_connection = lambda: QTimer.singleShot(100, safe_auto_activate)
            
            # NEW: Connect to cleared signal for proper cleanup on project close/new
            # This ensures plugin state is properly reset when project is cleared
            self._project_cleared_connection = safe_project_cleared
            
            # NEW: Connect layersAdded to handle the case where user loads a layer 
            # into an empty project (no projectRead signal in that case)
            # The guard in _auto_activate_for_new_layers ensures this only triggers
            # when plugin is NOT active, avoiding freeze issues
            self._layers_added_connection = safe_layers_added
            
            # Auto-reload when a project is opened
            self.iface.projectRead.connect(self._project_read_connection)
            # Auto-reload when a new project is created
            self.iface.newProjectCreated.connect(self._new_project_connection)
            # Auto-activate when layers are added to an empty project
            QgsProject.instance().layersAdded.connect(self._layers_added_connection)
            # NEW: Handle project cleared/closed
            QgsProject.instance().cleared.connect(self._project_cleared_connection)
            
            self._auto_activation_signals_connected = True
            logger.info("FilterMate: Auto-activation signals connected (projectRead, newProjectCreated, layersAdded, cleared)")

    def _disconnect_auto_activation_signals(self):
        """Disconnect auto-activation signals if they were connected.
        
        Called when AUTO_ACTIVATE is disabled or when unloading the plugin.
        """
        if self._auto_activation_signals_connected:
            try:
                from qgis.core import QgsProject
                
                if self._project_read_connection:
                    self.iface.projectRead.disconnect(self._project_read_connection)
                    self._project_read_connection = None
                if self._new_project_connection:
                    self.iface.newProjectCreated.disconnect(self._new_project_connection)
                    self._new_project_connection = None
                if hasattr(self, '_layers_added_connection') and self._layers_added_connection:
                    QgsProject.instance().layersAdded.disconnect(self._layers_added_connection)
                    self._layers_added_connection = None
                # NEW: Disconnect cleared signal
                if hasattr(self, '_project_cleared_connection') and self._project_cleared_connection:
                    try:
                        QgsProject.instance().cleared.disconnect(self._project_cleared_connection)
                    except (TypeError, RuntimeError):
                        pass  # Signal may already be disconnected
                    self._project_cleared_connection = None
                
                self._auto_activation_signals_connected = False
                logger.info("FilterMate: Auto-activation signals disconnected")
            except Exception as e:
                logger.warning(f"FilterMate: Error disconnecting auto-activation signals: {e}")

    def _handle_project_cleared(self):
        """Handle project cleared signal.
        
        Called when the current project is cleared (new project created, project closed).
        This ensures proper cleanup of plugin state to prevent stale references.
        """
        logger.info("FilterMate: Project cleared signal received - cleaning up plugin state")
        
        if not self.app:
            return
        
        try:
            # Reset all protection flags
            if hasattr(self.app, '_set_loading_flag'):
                self.app._set_loading_flag(False)
            if hasattr(self.app, '_set_initializing_flag'):
                self.app._set_initializing_flag(False)
            
            # Cancel pending tasks
            if hasattr(self.app, '_safe_cancel_all_tasks'):
                self.app._safe_cancel_all_tasks()
            
            # Clear the add_layers queue
            if hasattr(self.app, '_add_layers_queue'):
                self.app._add_layers_queue.clear()
                self.app._pending_add_layers_tasks = 0
            
            # Clear PROJECT_LAYERS
            if hasattr(self.app, 'PROJECT_LAYERS'):
                self.app.PROJECT_LAYERS = {}
            
            # Reset dockwidget state
            if self.app.dockwidget:
                self.app.dockwidget.current_layer = None
                self.app.dockwidget.has_loaded_layers = False
                self.app.dockwidget.PROJECT_LAYERS = {}
                self.app.dockwidget._plugin_busy = False
                self.app.dockwidget._updating_layers = False
                
                # Clear combobox safely
                try:
                    if hasattr(self.app.dockwidget, 'comboBox_filtering_current_layer'):
                        self.app.dockwidget.comboBox_filtering_current_layer.setLayer(None)
                        self.app.dockwidget.comboBox_filtering_current_layer.clear()
                except Exception as e:
                    logger.debug(f"Error clearing layer combobox on project cleared: {e}")
                
                # CRITICAL FIX: Clear QgsFeaturePickerWidget to prevent access violation
                # The widget has an internal timer that triggers scheduledReload which
                # creates QgsVectorLayerFeatureSource - if the layer is invalid/destroyed,
                # this causes a Windows fatal exception (access violation).
                # See stack trace: QgsFeaturePickerModelBase::scheduledReload -> QgsVectorLayerFeatureSource
                try:
                    if hasattr(self.app.dockwidget, 'mFeaturePickerWidget_exploring_single_selection'):
                        self.app.dockwidget.mFeaturePickerWidget_exploring_single_selection.setLayer(None)
                except Exception as e:
                    logger.debug(f"Error clearing FeaturePickerWidget on project cleared: {e}")
                
                # Update indicator to show waiting state
                if hasattr(self.app.dockwidget, 'backend_indicator_label') and self.app.dockwidget.backend_indicator_label:
                    self.app.dockwidget.backend_indicator_label.setText("...")
                    self.app.dockwidget.backend_indicator_label.setStyleSheet("""
                        QLabel#label_backend_indicator {
                            color: #7f8c8d;
                            font-size: 9pt;
                            font-weight: 600;
                            padding: 3px 10px;
                            border-radius: 12px;
                            border: none;
                            background-color: #ecf0f1;
                        }
                    """)
                
                # Disable UI while waiting for new layers
                if hasattr(self.app.dockwidget, 'set_widgets_enabled_state'):
                    self.app.dockwidget.set_widgets_enabled_state(False)
                    
        except Exception as e:
            logger.warning(f"FilterMate: Error during project cleared cleanup: {e}")

    def _auto_activate_for_new_layers(self, layers):
        """Handle layersAdded signal specifically for auto-activation.
        
        This method is called when layers are added to the project. It only
        activates the plugin if it's not already active, avoiding the freeze
        issues that occurred when processing layersAdded during active state.
        
        Args:
            layers: List of QgsMapLayer that were just added
        """
        # CRITICAL: Check if auto-activation is enabled
        from .config.config import ENV_VARS
        config_data = ENV_VARS.get('CONFIG_DATA', {})
        # Support both uppercase (config.default.json) and lowercase (migrated config.json) keys
        app_config = config_data.get('APP', config_data.get('app', {}))
        auto_activate_config = app_config.get('AUTO_ACTIVATE', app_config.get('auto_activate', {}))
        auto_activate_enabled = auto_activate_config.get('value', False)  # Default to False to prevent auto-open
        
        if not auto_activate_enabled:
            logger.debug("FilterMate: Auto-activation disabled, skipping layersAdded auto-activation")
            return
        
        from qgis.core import QgsVectorLayer
        from qgis.PyQt.QtCore import QTimer
        
        # CRITICAL: Only handle this signal when plugin is NOT active
        # When plugin is active, project changes are handled by projectRead/newProjectCreated
        # This avoids the freeze issues documented in known_issues_bugs memory
        if self.pluginIsActive:
            logger.debug("FilterMate: Plugin already active, skipping layersAdded auto-activation")
            return
        
        # Check if any of the added layers are vector layers
        vector_layers = [layer for layer in layers if isinstance(layer, QgsVectorLayer)]
        
        if not vector_layers:
            logger.debug("FilterMate: No vector layers in added layers, skipping auto-activation")
            return
        
        # Plugin not active and vector layers were added - activate it
        # Use QTimer to ensure QGIS is in a stable state before activation
        logger.info(f"FilterMate: Auto-activating plugin via layersAdded ({len(vector_layers)} vector layer(s))")
        
        # STABILITY: Increased delay to 400ms for better stability
        # Especially important for PostgreSQL layers which need time to initialize connections
        # and for projects with multiple layers being added simultaneously
        # STABILITY FIX: Use weakref to prevent access violations when timer fires after object destruction
        weak_self = weakref.ref(self)
        def safe_run_from_layers_added():
            strong_self = weak_self()
            if strong_self is not None:
                strong_self.run()
        QTimer.singleShot(400, safe_run_from_layers_added)
    
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
        # CRITICAL: Check if auto-activation is enabled
        from .config.config import ENV_VARS
        config_data = ENV_VARS.get('CONFIG_DATA', {})
        # Support both uppercase (config.default.json) and lowercase (migrated config.json) keys
        app_config = config_data.get('APP', config_data.get('app', {}))
        auto_activate_config = app_config.get('AUTO_ACTIVATE', app_config.get('auto_activate', {}))
        auto_activate_enabled = auto_activate_config.get('value', False)  # Default to False to prevent auto-open
        
        if not auto_activate_enabled:
            logger.debug("FilterMate: Auto-activation disabled, skipping auto-activation")
            return
        
        from qgis.core import QgsProject, QgsVectorLayer
        from qgis.PyQt.QtCore import QTimer
        
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
                # STABILITY FIX: Use weakref to prevent access violations
                weak_self = weakref.ref(self)
                def safe_handle_project_change():
                    strong_self = weak_self()
                    if strong_self is not None:
                        strong_self._handle_project_change()
                QTimer.singleShot(200, safe_handle_project_change)
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
        # STABILITY FIX: Use weakref to prevent access violations
        weak_self = weakref.ref(self)
        def safe_run_from_auto_activate():
            strong_self = weak_self()
            if strong_self is not None:
                strong_self.run()
        QTimer.singleShot(50, safe_run_from_auto_activate)

    def _handle_project_change(self):
        """Handle project change when plugin is already active.
        
        Reinitializes FilterMateApp with new project data without recreating
        the dockwidget. This is called when projectRead signal is emitted
        while the plugin is already active.
        
        STABILITY IMPROVEMENT: This method now performs a more thorough cleanup
        before reinitializing to prevent stale state issues.
        """
        from qgis.core import QgsProject, QgsVectorLayer
        from qgis.PyQt.QtCore import QTimer
        
        if not self.app:
            return
        
        logger.info("FilterMate: _handle_project_change triggered - starting project reinitialization")
        
        # STABILITY FIX: Check and reset stale flags before processing
        if hasattr(self.app, '_check_and_reset_stale_flags'):
            self.app._check_and_reset_stale_flags()
        
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
        
        # STABILITY IMPROVEMENT: Force cleanup of old project state BEFORE reinitializing
        # This prevents stale data from the previous project lingering
        try:
            logger.info("FilterMate: Forcing cleanup of previous project state")
            
            # 1. Cancel any pending tasks
            if hasattr(self.app, '_safe_cancel_all_tasks'):
                self.app._safe_cancel_all_tasks()
            
            # 2. Clear the add_layers queue to prevent stale operations
            if hasattr(self.app, '_add_layers_queue'):
                self.app._add_layers_queue.clear()
                self.app._pending_add_layers_tasks = 0
            
            # 3. Reset all state flags using the proper methods
            if hasattr(self.app, '_set_loading_flag'):
                self.app._set_loading_flag(False)
            if hasattr(self.app, '_set_initializing_flag'):
                self.app._set_initializing_flag(False)
            
            # 4. Clear PROJECT_LAYERS immediately to prevent stale references
            if hasattr(self.app, 'PROJECT_LAYERS'):
                self.app.PROJECT_LAYERS = {}
            
            # 5. Clear the combobox to prevent access violations
            if (self.app.dockwidget and 
                hasattr(self.app.dockwidget, 'comboBox_filtering_current_layer')):
                try:
                    self.app.dockwidget.comboBox_filtering_current_layer.setLayer(None)
                    self.app.dockwidget.comboBox_filtering_current_layer.clear()
                except Exception as e:
                    logger.debug(f"Error clearing layer combobox: {e}")
            
            # 5b. CRITICAL: Clear QgsFeaturePickerWidget to prevent access violation
            # The widget has an internal timer that triggers scheduledReload which
            # creates QgsVectorLayerFeatureSource - if the layer is invalid/destroyed,
            # this causes a Windows fatal exception (access violation).
            if (self.app.dockwidget and 
                hasattr(self.app.dockwidget, 'mFeaturePickerWidget_exploring_single_selection')):
                try:
                    self.app.dockwidget.mFeaturePickerWidget_exploring_single_selection.setLayer(None)
                except Exception as e:
                    logger.debug(f"Error clearing FeaturePickerWidget: {e}")
            
            # 6. Reset dockwidget layer references
            if self.app.dockwidget:
                self.app.dockwidget.current_layer = None
                self.app.dockwidget.has_loaded_layers = False
                self.app.dockwidget.PROJECT_LAYERS = {}
                self.app.dockwidget._plugin_busy = False
                self.app.dockwidget._updating_layers = False
                
        except Exception as e:
            logger.warning(f"FilterMate: Error during pre-change cleanup: {e}")
        
        # Check if there are vector layers in the new project
        vector_layers = [layer for layer in project.mapLayers().values() 
                        if isinstance(layer, QgsVectorLayer)]
        
        if not vector_layers:
            logger.info("FilterMate: New project has no vector layers")
            # Only access dockwidget if it exists and has widgets_initialized
            if (self.app.dockwidget and 
                hasattr(self.app.dockwidget, 'widgets_initialized') and 
                self.app.dockwidget.widgets_initialized):
                self.app.dockwidget.set_widgets_enabled_state(False)
            return
        
        logger.info(f"FilterMate: Reinitializing for new project with {len(vector_layers)} vector layers")
        
        # STABILITY IMPROVEMENT: Use a longer delay for project reinitialization
        # This gives QGIS time to fully load the project and all layers
        # especially important for PostgreSQL layers
        # STABILITY FIX: Use weakref to prevent access violations when timer fires after object destruction
        weak_self = weakref.ref(self)
        
        def perform_reinitialization():
            strong_self = weak_self()
            if strong_self is None or strong_self.app is None:
                logger.debug("FilterMate: Skipping reinitialization - plugin was unloaded")
                return
            try:
                # Call the existing project initialization handler
                strong_self.app._handle_project_initialization('project_read')
            except Exception as e:
                logger.error(f"FilterMate: Error during project reinitialization: {e}")
                # STABILITY FIX: Reset flags on error to prevent deadlock
                if hasattr(strong_self.app, '_set_loading_flag'):
                    strong_self.app._set_loading_flag(False)
                if hasattr(strong_self.app, '_set_initializing_flag'):
                    strong_self.app._set_initializing_flag(False)
        
        # STABILITY IMPROVEMENT: Increased delay from immediate to 300ms
        # This ensures all QGIS signals have been processed before we reinitialize
        QTimer.singleShot(300, perform_reinitialization)


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        #print "** UNLOAD FilterMate"
        
        # Disconnect project change signals using dedicated method
        self._disconnect_auto_activation_signals()
        
        # Disconnect project read signal for form dependency warnings
        try:
            from qgis.core import QgsProject
            if hasattr(self, '_on_project_read_handler') and self._on_project_read_handler:
                QgsProject.instance().readProject.disconnect(self._on_project_read_handler)
                self._on_project_read_handler = None
                logger.debug("FilterMate: readProject signal disconnected")
        except Exception as e:
            logger.debug(f"FilterMate: Error disconnecting readProject signal: {e}")
        
        # PERFORMANCE v2.4.0: Clean up PostgreSQL connection pools
        try:
            from .infrastructure.database.connection_pool import cleanup_pools
            cleanup_pools()
            logger.debug("FilterMate: PostgreSQL connection pools cleaned up")
        except ImportError:
            pass  # Connection pool module not available
        except Exception as e:
            logger.debug(f"FilterMate: Error cleaning up connection pools: {e}")
        
        # CRITICAL: Clear QgsMapLayerComboBox before cleanup to prevent access violations
        if self.app and self.app.dockwidget:
            try:
                if hasattr(self.app.dockwidget, 'comboBox_filtering_current_layer'):
                    self.app.dockwidget.comboBox_filtering_current_layer.setLayer(None)
                    self.app.dockwidget.comboBox_filtering_current_layer.clear()
                    logger.debug("FilterMate: Layer combo box cleared during unload")
            except Exception as e:
                logger.debug(f"FilterMate: Error clearing layer combo during unload: {e}")
            
            # CRITICAL: Clear QgsFeaturePickerWidget to prevent access violation
            # The widget has an internal timer that triggers scheduledReload
            try:
                if hasattr(self.app.dockwidget, 'mFeaturePickerWidget_exploring_single_selection'):
                    self.app.dockwidget.mFeaturePickerWidget_exploring_single_selection.setLayer(None)
                    logger.debug("FilterMate: FeaturePickerWidget cleared during unload")
            except Exception as e:
                logger.debug(f"FilterMate: Error clearing FeaturePickerWidget during unload: {e}")
        
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
            self.tr('Reset Configuration'),
            self.tr('Are you sure you want to reset to the default configuration?\n\n'
                   'This will:\n'
                   '- Restore default settings\n'
                   '- Delete the layer database\n\n'
                   'QGIS must be restarted to apply the changes.'),
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
                    self.tr("Configuration reset successfully.")
                )
            else:
                self.iface.messageBar().pushWarning(
                    "FilterMate",
                    self.tr("Default configuration file not found.")
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
                                    self.tr(f"Database deleted: {filename}")
                                )
                            except OSError as e:
                                self.iface.messageBar().pushWarning(
                                    "FilterMate",
                                    self.tr(f"Unable to delete {filename}: {e}")
                                )
            except Exception as e:
                # Non-critical error, config was already reset
                pass
            
            # Prompt to restart QGIS
            QMessageBox.information(
                self.iface.mainWindow(),
                self.tr('Restart required'),
                self.tr('The configuration has been reset.\n\n'
                       'Please restart QGIS to apply the changes.')
            )
            
        except Exception as e:
            self.iface.messageBar().pushCritical(
                "FilterMate",
                self.tr(f"Error during reset: {str(e)}")
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
                    if self.app.dockwidget:
                        self.app.dockwidget.closingPlugin.connect(self.onClosePlugin)
                else:
                    # App already exists, call run() which will show the dockwidget
                    # and refresh layers if needed
                    self.app.run()
                    # Reconnect closingPlugin signal only if not already connected
                    # Use try/except to safely disconnect then reconnect
                    if self.app.dockwidget:
                        try:
                            self.app.dockwidget.closingPlugin.disconnect(self.onClosePlugin)
                        except TypeError:
                            pass  # Not connected, ignore
                        self.app.dockwidget.closingPlugin.connect(self.onClosePlugin)
            except Exception as e:
                self.iface.messageBar().pushCritical(
                    "FilterMate",
                    f"Error loading plugin: {str(e)}. Check QGIS Python console for details."
                )
                import traceback
                logger.error(f"Error loading plugin: {traceback.format_exc()}")
                self.pluginIsActive = False
            




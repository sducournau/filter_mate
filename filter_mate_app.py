from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import QgsCheckableComboBox, QgsFeatureListComboBox, QgsFieldExpressionWidget
from qgis.utils import *
from qgis import processing
from osgeo import ogr

from collections import OrderedDict
from operator import getitem
import zipfile
import os.path
from pathlib import Path
from shutil import copyfile
import re
import logging
from .config.config import *
from functools import partial
import json
from .modules.customExceptions import *
from .modules.appTasks import *
from .modules.appUtils import POSTGRESQL_AVAILABLE
from .modules.feedback_utils import (
    show_backend_info, show_progress_message, show_success_with_backend,
    show_performance_warning, show_error_with_context
)
from .modules.filter_history import HistoryManager
from .modules.ui_config import UIConfig, DisplayProfile
from .resources import *
import uuid

# Get FilterMate logger
logger = logging.getLogger('FilterMate')


# Import the code for the DockWidget
from .filter_mate_dockwidget import FilterMateDockWidget

MESSAGE_TASKS_CATEGORIES = {
                            'filter':'FilterLayers',
                            'undo':'FilterLayers',
                            'redo':'FilterLayers',
                            'reset':'FilterLayers',
                            'export':'ExportLayers',
                            'add_layers':'ManageLayers',
                            'remove_layers':'ManageLayers',
                            'remove_all_layers':'ManageLayers',
                            'new_project':'ManageLayers',
                            'project_read':'ManageLayers'
                            }

class FilterMateApp:

    PROJECT_LAYERS = {} 

    def cleanup(self):
        """
        Clean up plugin resources on unload or reload.
        
        Safely removes widgets, clears data structures, and prevents memory leaks.
        Called when plugin is disabled or QGIS is closing.
        
        Cleanup steps:
        1. Clear list_widgets from multiple selection widget
        2. Reset async tasks
        3. Clear PROJECT_LAYERS dictionary
        4. Clear datasource connections
        
        Notes:
            - Uses try/except to handle already-deleted widgets
            - Safe to call multiple times
            - Prevents KeyError on plugin reload
        """
        if self.dockwidget is not None:
            # Nettoyer tous les widgets list_widgets pour éviter les KeyError
            if hasattr(self.dockwidget, 'widgets'):
                try:
                    multiple_selection_widget = self.dockwidget.widgets.get("EXPLORING", {}).get("MULTIPLE_SELECTION_FEATURES", {}).get("WIDGET")
                    if multiple_selection_widget and hasattr(multiple_selection_widget, 'list_widgets'):
                        # Nettoyer tous les list_widgets
                        multiple_selection_widget.list_widgets.clear()
                        # Réinitialiser les tasks
                        if hasattr(multiple_selection_widget, 'tasks'):
                            multiple_selection_widget.tasks.clear()
                except (KeyError, AttributeError, RuntimeError) as e:
                    # Les widgets peuvent déjà être supprimés
                    pass
            
            # Nettoyer PROJECT_LAYERS
            if hasattr(self.dockwidget, 'PROJECT_LAYERS'):
                self.dockwidget.PROJECT_LAYERS.clear()
        
        # Réinitialiser les structures de données de l'app
        self.PROJECT_LAYERS.clear()
        self.project_datasources.clear()

    def __init__(self, plugin_dir):
        """
        Initialize FilterMate application controller.
        
        Sets up the main application state, task registry, and environment variables.
        Does not create UI - that happens in run() when plugin is activated.
        
        Args:
            plugin_dir (str): Absolute path to plugin directory
            
        Attributes:
            PROJECT_LAYERS (dict): Registry of all managed layers with metadata
            appTasks (dict): Active QgsTask instances for async operations
            tasks_descriptions (dict): Human-readable task names for UI
            project_datasources (dict): Data source connection information
            db_file_path (str): Path to Spatialite database for project
            
        Notes:
            - Initializes environment variables via init_env_vars()
            - Sets up QGIS project and layer store references
            - Prepares task manager for PostgreSQL/Spatialite operations
        """
        self.iface = iface
        
        self.dockwidget = None
        self.flags = {}


        self.plugin_dir = plugin_dir
        self.appTasks = {"filter":None,"undo":None,"redo":None,"reset":None,"export":None,"add_layers":None,"remove_layers":None,"remove_all_layers":None,"new_project":None,"project_read":None}
        self.tasks_descriptions = {
                                    'filter':'Filtering data',
                                    'undo':'Undoing filter',
                                    'redo':'Redoing filter',
                                    'reset':'Reseting data',
                                    'export':'Exporting data',
                                    'add_layers':'Adding layers',
                                    'remove_layers':'Removing layers',
                                    'remove_all_layers':'Removing all layers',
                                    'new_project':'New project',
                                    'project_read':'Existing project loaded'
                                    }
        
        # Initialize filter history manager for undo/redo functionality
        self.history_manager = HistoryManager(max_size=100)
        logger.info("FilterMate: HistoryManager initialized for undo/redo functionality")
        
        init_env_vars()
        
        global ENV_VARS

        self.CONFIG_DATA = ENV_VARS["CONFIG_DATA"]
        self.PROJECT = ENV_VARS["PROJECT"]

        self.MapLayerStore = self.PROJECT.layerStore()
        self.db_name = 'filterMate_db.sqlite'
        self.db_file_path = os.path.normpath(ENV_VARS["PLUGIN_CONFIG_DIRECTORY"] + os.sep + self.db_name)
        self.project_file_name = os.path.basename(self.PROJECT.absoluteFilePath())
        self.project_file_path = self.PROJECT.absolutePath()
        self.project_uuid = ''

        self.project_datasources = {}
        self.app_postgresql_temp_schema_setted = False
        self._signals_connected = False
        # Note: Do NOT call self.run() here - it will be called from filter_mate.py
        # when the user actually activates the plugin to avoid QGIS initialization race conditions


    def run(self):
        """
        Initialize and display the FilterMate dockwidget.
        
        Creates the dockwidget if it doesn't exist, initializes the database,
        connects signals for layer management, and displays the UI.
        Also processes any existing layers in the project on first run.
        
        This method should only be called once when the plugin is activated.
        """
        if self.dockwidget == None:

            
        
            global ENV_VARS

            self.CONFIG_DATA = ENV_VARS["CONFIG_DATA"]
            self.PROJECT = ENV_VARS["PROJECT"]

            QgsExpressionContextUtils.setProjectVariable(self.PROJECT, 'filterMate_db_project_uuid', '')    

            init_layers = list(self.PROJECT.mapLayers().values())

            self.init_filterMate_db()
            
            # Initialize UI profile based on screen resolution
            try:
                from qgis.PyQt.QtWidgets import QApplication
                screen = QApplication.primaryScreen()
                if screen:
                    screen_geometry = screen.geometry()
                    screen_width = screen_geometry.width()
                    screen_height = screen_geometry.height()
                    
                    # Use compact mode for resolutions < 1920x1080
                    if screen_width < 1920 or screen_height < 1080:
                        UIConfig.set_profile(DisplayProfile.COMPACT)
                        logger.info(f"FilterMate: Using COMPACT profile for resolution {screen_width}x{screen_height}")
                    else:
                        UIConfig.set_profile(DisplayProfile.NORMAL)
                        logger.info(f"FilterMate: Using NORMAL profile for resolution {screen_width}x{screen_height}")
                else:
                    # Fallback to normal if screen detection fails
                    UIConfig.set_profile(DisplayProfile.NORMAL)
                    logger.warning("FilterMate: Could not detect screen, using NORMAL profile")
            except Exception as e:
                logger.error(f"FilterMate: Error detecting screen resolution: {e}")
                UIConfig.set_profile(DisplayProfile.NORMAL)
            
            self.dockwidget = FilterMateDockWidget(self.PROJECT_LAYERS, self.plugin_dir, self.CONFIG_DATA, self.PROJECT)

            # show the dockwidget
            # TODO: fix to allow choice of dock location
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
            self.dockwidget.show()
            
            # Process existing layers AFTER dockwidget is shown and fully initialized
            # Use QTimer to ensure widgets_initialized is True and event loop has processed show()
            if init_layers != None and len(init_layers) > 0:
                from qgis.PyQt.QtCore import QTimer
                # Increased delay to 500ms to ensure complete initialization
                QTimer.singleShot(500, lambda: self.manage_task('add_layers', init_layers))


        """Keep the advanced filter combobox updated on adding or removing layers"""
        # Use QTimer.singleShot to defer project signal handling until QGIS is in stable state
        # This prevents access violations during project transitions
        # Only connect signals once to avoid multiple connections on plugin reload
        if not self._signals_connected:
            from qgis.PyQt.QtCore import QTimer
            self.iface.projectRead.connect(lambda: QTimer.singleShot(50, lambda: self.manage_task('project_read')))
            self.iface.newProjectCreated.connect(lambda: QTimer.singleShot(50, lambda: self.manage_task('new_project')))
            # Use layersAdded (batch) instead of layerWasAdded (per layer) to avoid duplicate calls
            self.MapLayerStore.layersAdded.connect(lambda layers: self.manage_task('add_layers', layers))
            self.MapLayerStore.layersWillBeRemoved.connect(lambda layers: self.manage_task('remove_layers', layers))
            self.MapLayerStore.allLayersRemoved.connect(lambda: self.manage_task('remove_all_layers'))
            self._signals_connected = True
        
        self.dockwidget.launchingTask.connect(lambda x: self.manage_task(x))

        self.dockwidget.resettingLayerVariableOnError.connect(lambda layer, properties: self.remove_variables_from_layer(layer, properties))
        self.dockwidget.settingLayerVariable.connect(lambda layer, properties: self.save_variables_from_layer(layer, properties))
        self.dockwidget.resettingLayerVariable.connect(lambda layer, properties: self.remove_variables_from_layer(layer, properties))

        self.dockwidget.settingProjectVariables.connect(self.save_project_variables)
        self.PROJECT.fileNameChanged.connect(lambda: self.save_project_variables())
        

    def get_spatialite_connection(self):
        """
        Get a Spatialite connection with proper error handling.
        
        Returns:
            Connection object or None if connection fails
        """
        if not os.path.exists(self.db_file_path):
            error_msg = f"Database file does not exist: {self.db_file_path}"
            logger.error(error_msg)
            iface.messageBar().pushCritical("FilterMate", error_msg)
            return None
            
        try:
            conn = spatialite_connect(self.db_file_path)
            return conn
        except Exception as error:
            error_msg = f"Failed to connect to database {self.db_file_path}: {error}"
            logger.error(error_msg)
            iface.messageBar().pushCritical("FilterMate", error_msg)
            return None

        
        """Overload configuration qtreeview model to keep configuration file up to date"""
        # 
        # self.managerWidgets.model.rowsInserted.connect(self.qtree_signal)
        # self.managerWidgets.model.rowsRemoved.connect(self.qtree_signal)


    def manage_task(self, task_name, data=None):
        """
        Orchestrate execution of FilterMate tasks.
        
        Central dispatcher for all plugin operations including filtering, layer management,
        and project operations. Creates appropriate task objects and manages their execution
        through QGIS task manager.
        
        Args:
            task_name (str): Name of task to execute. Must be one of:
                - 'filter': Apply filters to layers
                - 'undo': Remove filters from layers (go back in history)
                - 'redo': Restore filters from layers (go forward in history)
                - 'reset': Reset layer state
                - 'add_layers': Process newly added layers
                - 'remove_layers': Clean up removed layers
                - 'remove_all_layers': Clear all layer data
                - 'project_read': Handle project load
                - 'new_project': Initialize new project
            data: Task-specific data (layers list, parameters, etc.)
                
        Raises:
            AssertionError: If task_name is not recognized
            
        Notes:
            - Cancels conflicting active tasks before starting new ones
            - Shows progress messages in QGIS message bar
            - Automatically connects task completion signals
        """

        assert task_name in list(self.tasks_descriptions.keys())
        
        # Guard: Ensure dockwidget is fully initialized before processing tasks
        # Exception: remove_all_layers, project_read, new_project can run without full initialization
        if task_name not in ('remove_all_layers', 'project_read', 'new_project'):
            if self.dockwidget is None or not hasattr(self.dockwidget, 'widgets_initialized') or not self.dockwidget.widgets_initialized:
                logger.warning(f"Task '{task_name}' called before dockwidget initialization, deferring by 300ms...")
                from qgis.PyQt.QtCore import QTimer
                QTimer.singleShot(300, lambda: self.manage_task(task_name, data))
                return

        if self.dockwidget != None:
            self.PROJECT_LAYERS = self.dockwidget.PROJECT_LAYERS
            self.CONFIG_DATA = self.dockwidget.CONFIG_DATA

        if task_name == 'remove_all_layers':
           self._safe_cancel_all_tasks()
           self.dockwidget.disconnect_widgets_signals()
           self.dockwidget.reset_multiple_checkable_combobox()
           self.layer_management_engine_task_completed({}, task_name)
           return
        
        if task_name in ('project_read', 'new_project'):
            # Verify project is valid before processing
            from qgis.core import QgsProject
            project = QgsProject.instance()
            if not project:
                logger.warning(f"Project not available for {task_name}, skipping")
                return
            
            self.app_postgresql_temp_schema_setted = False
            self._safe_cancel_all_tasks()
            init_env_vars()

            global ENV_VARS
            self.PROJECT = ENV_VARS["PROJECT"]
            
            # Verify project is still valid after init
            if not self.PROJECT:
                logger.warning(f"Project became invalid during {task_name}, skipping")
                return
                
            self.MapLayerStore = self.PROJECT.layerStore()
            init_layers = list(self.PROJECT.mapLayers().values())
            self.init_filterMate_db()
            if len(init_layers) > 0:
                self.manage_task('add_layers', init_layers)
            else:
                self.dockwidget.disconnect_widgets_signals()
                self.dockwidget.reset_multiple_checkable_combobox()
                self.layer_management_engine_task_completed({}, 'remove_all_layers')
            return

        task_parameters = self.get_task_parameters(task_name, data)

        if task_name in [name for name in self.tasks_descriptions.keys() if "layer" not in name]:

            if self.dockwidget == None or self.dockwidget.current_layer == None:
                return
            else:
                current_layer = self.dockwidget.current_layer 


                
            layers = []
            self.appTasks[task_name] = FilterEngineTask(self.tasks_descriptions[task_name], task_name, task_parameters)
            layers_props = [layer_infos for layer_infos in task_parameters["task"]["layers"]]
            layers_ids = [layer_props["layer_id"] for layer_props in layers_props]
            for layer_props in layers_props:
                temp_layers = self.PROJECT.mapLayersByName(layer_props["layer_name"])
                for temp_layer in temp_layers:
                    if temp_layer.id() in layers_ids:
                        layers.append(temp_layer)
            
            # Show informational message with backend awareness
            layer_count = len(layers) + 1  # +1 for current layer
            provider_type = task_parameters["infos"].get("layer_provider_type", "unknown")
            
            if task_name == 'filter':
                show_backend_info(iface, provider_type, layer_count, operation='filter')
            elif task_name == 'undo':
                show_backend_info(iface, provider_type, layer_count, operation='undo')
            elif task_name == 'redo':
                show_backend_info(iface, provider_type, layer_count, operation='redo')
            elif task_name == 'reset':
                show_backend_info(iface, provider_type, layer_count, operation='reset')

            self.appTasks[task_name].setDependentLayers(layers + [current_layer])
            self.appTasks[task_name].taskCompleted.connect(lambda task_name=task_name, current_layer=current_layer, task_parameters=task_parameters: self.filter_engine_task_completed(task_name, current_layer, task_parameters))
            
        else:
            self.appTasks[task_name] = LayersManagementEngineTask(self.tasks_descriptions[task_name], task_name, task_parameters)

            if task_name == "add_layers":
                self.appTasks[task_name].setDependentLayers([layer for layer in task_parameters["task"]["layers"]])
                self.appTasks[task_name].begun.connect(self.dockwidget.disconnect_widgets_signals)
            elif task_name == "remove_layers":
                self.appTasks[task_name].begun.connect(self.on_remove_layer_task_begun)
            
            # self.appTasks[task_name].taskCompleted.connect(lambda state='connect': self.dockwidget_change_widgets_signal(state))

            self.appTasks[task_name].resultingLayers.connect(lambda result_project_layers, task_name=task_name: self.layer_management_engine_task_completed(result_project_layers, task_name))
            self.appTasks[task_name].savingLayerVariable.connect(lambda layer, variable_key, value_typped, type_returned: self.saving_layer_variable(layer, variable_key, value_typped, type_returned))
            self.appTasks[task_name].removingLayerVariable.connect(lambda layer, variable_key: self.removing_layer_variable(layer, variable_key))

        try:
            active_tasks = QgsApplication.taskManager().activeTasks()
            if len(active_tasks) > 0:
                for active_task in active_tasks:
                    key_active_task = [k for k, v in self.tasks_descriptions.items() if v == active_task.description()][0]
                    if key_active_task in ('filter','reset','undo','redo'):
                        active_task.cancel()
        except (IndexError, KeyError, AttributeError) as e:
            # Ignore errors in task cancellation - task may have completed already
            pass
        QgsApplication.taskManager().addTask(self.appTasks[task_name])

    def _safe_cancel_all_tasks(self):
        """Safely cancel all tasks in the task manager to avoid access violations.
        
        Note: We cancel tasks individually instead of using cancelAll() to avoid
        Windows access violations that occur when cancelAll() is called from Qt signals
        during project transitions.
        """
        try:
            task_manager = QgsApplication.taskManager()
            if not task_manager:
                return
            
            # Get list of task IDs first (avoid iterating while modifying)
            task_ids = []
            for task_id in range(task_manager.count()):
                task = task_manager.task(task_id)
                if task:
                    task_ids.append(task.taskId())
            
            # Cancel each task individually
            for task_id in task_ids:
                task = task_manager.task(task_id)
                if task and task.canCancel():
                    task.cancel()
                    
        except Exception as e:
            logger.warning(f"Could not cancel tasks: {e}")

    def on_remove_layer_task_begun(self):
        self.dockwidget.disconnect_widgets_signals()
        self.dockwidget.reset_multiple_checkable_combobox()
    

    def get_task_parameters(self, task_name, data=None):
        """
        Build parameter dictionary for task execution.
        
        Constructs the complete parameter set needed by FilterEngineTask or
        LayersManagementEngineTask, including layer properties, configuration,
        and backend-specific settings.
        
        Args:
            task_name (str): Name of the task requiring parameters
            data: Task-specific input data (typically layers or properties)
            
        Returns:
            dict: Complete task parameter dictionary with structure:
                {
                    'plugin_dir': str,
                    'config_data': dict,
                    'project': QgsProject,
                    'project_layers': dict,
                    'task': dict  # Task-specific parameters
                }
                
        Notes:
            - For filtering tasks: includes current layer and layers to filter
            - For layer management: includes layers being added/removed
            - Automatically detects PostgreSQL availability
        """

        

        if task_name in [name for name in self.tasks_descriptions.keys() if "layer" not in name]:

            if self.dockwidget == None or self.dockwidget.current_layer == None:
                return
            else:
                current_layer = self.dockwidget.current_layer 

            if current_layer.id() in self.PROJECT_LAYERS.keys():
                task_parameters = self.PROJECT_LAYERS[current_layer.id()]

            if current_layer.subsetString() != '':
                self.PROJECT_LAYERS[current_layer.id()]["infos"]["is_already_subset"] = True
            else:
                self.PROJECT_LAYERS[current_layer.id()]["infos"]["is_already_subset"] = False

            features, expression = self.dockwidget.get_current_features()

            if task_name in ('filter','undo','reset','redo'):
                layers_to_filter = []
                for key in self.PROJECT_LAYERS[current_layer.id()]["filtering"]["layers_to_filter"]:
                    if key in self.PROJECT_LAYERS:
                        layer_info = self.PROJECT_LAYERS[key]["infos"].copy()
                        
                        # Validate required keys exist for geometric filtering
                        required_keys = [
                            'layer_name', 'layer_id', 'layer_provider_type',
                            'primary_key_name', 'layer_geometry_field', 'layer_schema'
                        ]
                        
                        missing_keys = [k for k in required_keys if k not in layer_info or layer_info[k] is None]
                        if missing_keys:
                            logger.warning(f"Layer {key} missing required keys: {missing_keys}")
                            # Try to fill in missing keys if possible
                            layer_obj = [l for l in self.PROJECT.mapLayers().values() if l.id() == key]
                            if layer_obj:
                                layer = layer_obj[0]
                                if 'layer_name' not in layer_info or layer_info['layer_name'] is None:
                                    layer_info['layer_name'] = layer.name()
                                if 'layer_id' not in layer_info or layer_info['layer_id'] is None:
                                    layer_info['layer_id'] = layer.id()
                                # Log what couldn't be filled
                                still_missing = [k for k in required_keys if k not in layer_info or layer_info[k] is None]
                                if still_missing:
                                    logger.error(f"Cannot filter layer {key}: still missing {still_missing}")
                                    continue
                        
                        layers_to_filter.append(layer_info)


                if task_name == 'filter':

                    task_parameters["task"] = {"features": features, "expression": expression, "options": self.dockwidget.project_props["OPTIONS"],
                                                "layers": layers_to_filter,
                                                "db_file_path": self.db_file_path, "project_uuid": self.project_uuid }
                    
                    # Initialize history with current state if this is the first filter
                    history = self.history_manager.get_or_create_history(current_layer.id())
                    if len(history._states) == 0:
                        # Push initial unfiltered state for source layer
                        current_filter = current_layer.subsetString()
                        current_count = current_layer.featureCount()
                        history.push_state(
                            expression=current_filter,
                            feature_count=current_count,
                            description="Initial state (before first filter)",
                            metadata={"operation": "initial", "backend": task_parameters["infos"].get("layer_provider_type", "unknown")}
                        )
                        logger.info(f"FilterMate: Initialized history with current state for source layer {current_layer.id()}")
                    
                    # Initialize history for associated layers if this is their first filter
                    for layer_info in layers_to_filter:
                        layer_id = layer_info.get("layer_id")
                        if layer_id and layer_id in self.PROJECT_LAYERS:
                            assoc_layers = [l for l in self.PROJECT.mapLayers().values() if l.id() == layer_id]
                            if len(assoc_layers) == 1:
                                assoc_layer = assoc_layers[0]
                                assoc_history = self.history_manager.get_or_create_history(assoc_layer.id())
                                if len(assoc_history._states) == 0:
                                    # Push initial unfiltered state for associated layer
                                    assoc_filter = assoc_layer.subsetString()
                                    assoc_count = assoc_layer.featureCount()
                                    assoc_history.push_state(
                                        expression=assoc_filter,
                                        feature_count=assoc_count,
                                        description="Initial state (before first filter)",
                                        metadata={"operation": "initial", "backend": layer_info.get("layer_provider_type", "unknown")}
                                    )
                                    logger.info(f"FilterMate: Initialized history for associated layer {assoc_layer.name()}")
                    
                    return task_parameters

                elif task_name == 'undo':

                    task_parameters["task"] = {"features": features, "expression": expression, "options": self.dockwidget.project_props["OPTIONS"],
                                                "layers": layers_to_filter,
                                                "db_file_path": self.db_file_path, "project_uuid": self.project_uuid,
                                                "history_manager": self.history_manager }  # Pass history manager for undo
                    return task_parameters
                
                elif task_name == 'redo':

                    task_parameters["task"] = {"features": features, "expression": expression, "options": self.dockwidget.project_props["OPTIONS"],
                                                "layers": layers_to_filter,
                                                "db_file_path": self.db_file_path, "project_uuid": self.project_uuid,
                                                "history_manager": self.history_manager }  # Pass history manager for redo
                    return task_parameters
                
                elif task_name == 'reset':

                    task_parameters["task"] = {"features": features, "expression": expression, "options": self.dockwidget.project_props["OPTIONS"],
                                                "layers": layers_to_filter,
                                                "db_file_path": self.db_file_path, "project_uuid": self.project_uuid }
                    return task_parameters

            elif task_name == 'export':
                layers_to_export = []
                for key in self.dockwidget.project_props["EXPORTING"]["LAYERS_TO_EXPORT"]:
                    if key in self.PROJECT_LAYERS:
                        layers_to_export.append(self.PROJECT_LAYERS[key]["infos"])
                task_parameters["task"] = self.dockwidget.project_props
                task_parameters["task"]["layers"] = layers_to_export
                                            
                return task_parameters
            
        else:
            if data != None:
                reset_all_layers_variables_flag = False
                task_parameters = {}

                if task_name == 'add_layers':

                    new_layers = []

                    if isinstance(data, list):
                        layers = data
                    else:
                        layers = [data]

                    if self.CONFIG_DATA["APP"]["OPTIONS"]["FRESH_RELOAD_FLAG"] is True and self.dockwidget.has_loaded_layers is False:
                        reset_all_layers_variables_flag = True

                    # for layer in layers:
                    #     layer_total_features_count = None
                    #     layer_features_source = 0

                    #     subset_string_init = layer.subsetString()
                    #     if subset_string_init != '':
                    #         layer.setSubsetString('')

                    #     data_provider_layer = layer.dataProvider()
                    #     if data_provider_layer:
                    #         layer_total_features_count = data_provider_layer.featureCount()
                    #         layer_features_source = data_provider_layer.featureSource()

                    #     if subset_string_init != '':
                    #         layer.setSubsetString(subset_string_init)
                        
                    #     new_layers.append((layer, layer_features_source, layer_total_features_count))

                    task_parameters["task"] = {"layers": layers, "project_layers": self.PROJECT_LAYERS, "reset_all_layers_variables_flag":reset_all_layers_variables_flag,
                                               "config_data": self.CONFIG_DATA, "db_file_path": self.db_file_path, "project_uuid": self.project_uuid }
                    return task_parameters

                elif task_name == 'remove_layers':
                    if isinstance(data, list):
                        layers = data
                    else:
                        layers = [data]

                    if self.CONFIG_DATA["APP"]["OPTIONS"]["FRESH_RELOAD_FLAG"] is True and self.dockwidget.has_loaded_layers is False:
                        reset_all_layers_variables_flag = True

                    task_parameters["task"] = {"layers": layers, "project_layers": self.PROJECT_LAYERS, "reset_all_layers_variables_flag": reset_all_layers_variables_flag,
                                               "config_data": self.CONFIG_DATA, "db_file_path": self.db_file_path, "project_uuid": self.project_uuid }
                    return task_parameters


    def filter_engine_task_completed(self, task_name, source_layer, task_parameters):
        """
        Handle completion of filtering operations.
        
        Called when FilterEngineTask completes successfully. Applies results to layers,
        updates UI, saves layer variables, and shows success messages.
        
        Args:
            task_name (str): Name of completed task ('filter', 'undo', 'redo', 'reset')
            source_layer (QgsVectorLayer): Primary layer that was filtered
            task_parameters (dict): Original task parameters including results
            
        Notes:
            - Applies subset filters to all affected layers
            - Updates layer variables in Spatialite database
            - Refreshes dockwidget UI state
            - Shows success message with feature counts
            - Handles both single and multi-layer filtering
        """

        if task_name in ('filter','undo','reset','redo'):



            # if source_layer.subsetString() != '':
            #     self.PROJECT_LAYERS[source_layer.id()]["infos"]["is_already_subset"] = True
            # else:
            #     self.PROJECT_LAYERS[source_layer.id()]["infos"]["is_already_subset"] = False
            # self.save_variables_from_layer(source_layer,[("infos","is_already_subset")])

            
            # source_layer.reload()
            source_layer.updateExtents()
            source_layer.triggerRepaint()
            
            # if task_parameters["filtering"]["has_layers_to_filter"] == True:
            #     for layer_props in task_parameters["task"]["layers"]:
            #         if layer_props["layer_id"] in self.PROJECT_LAYERS:
            #             layers = [layer for layer in self.PROJECT.mapLayersByName(layer_props["layer_name"]) if layer.id() == layer_props["layer_id"]]
            #             if len(layers) == 1:
            #                 layer = layers[0]

            #                 # if layer.subsetString() != '':
            #                 #     self.PROJECT_LAYERS[layer.id()]["infos"]["is_already_subset"] = True
            #                 # else:
            #                 #     self.PROJECT_LAYERS[layer.id()]["infos"]["is_already_subset"] = False
            #                 # self.save_variables_from_layer(layer,[("infos","is_already_subset")])

            #                 layer.reload()
            #                 layer.updateExtents()
            #                 layer.triggerRepaint()
                        

            self.iface.mapCanvas().refreshAllLayers()
            self.iface.mapCanvas().refresh()
            
            # Show success message with backend and feature count
            feature_count = source_layer.featureCount()
            provider_type = task_parameters["infos"].get("layer_provider_type", "unknown")
            layer_count = len(task_parameters.get("task", {}).get("layers", [])) + 1
            
            # Push filter state to history for undo/redo (except for undo/redo which use history.undo()/history.redo())
            if task_name == 'filter':
                # Save source layer state to history
                history = self.history_manager.get_or_create_history(source_layer.id())
                filter_expression = source_layer.subsetString()
                description = f"Filter: {filter_expression[:60]}..." if len(filter_expression) > 60 else f"Filter: {filter_expression}"
                history.push_state(
                    expression=filter_expression,
                    feature_count=feature_count,
                    description=description,
                    metadata={"backend": provider_type, "operation": "filter", "layer_count": layer_count}
                )
                logger.info(f"FilterMate: Pushed filter state to history for source layer (position {history._current_index + 1}/{len(history._states)})")
                
                # Save associated layers state to history
                for layer_props in task_parameters.get("task", {}).get("layers", []):
                    if layer_props["layer_id"] in self.PROJECT_LAYERS:
                        layers = [layer for layer in self.PROJECT.mapLayersByName(layer_props["layer_name"]) 
                                 if layer.id() == layer_props["layer_id"]]
                        if len(layers) == 1:
                            assoc_layer = layers[0]
                            assoc_history = self.history_manager.get_or_create_history(assoc_layer.id())
                            assoc_filter = assoc_layer.subsetString()
                            assoc_count = assoc_layer.featureCount()
                            assoc_desc = f"Filter: {assoc_filter[:60]}..." if len(assoc_filter) > 60 else f"Filter: {assoc_filter}"
                            assoc_history.push_state(
                                expression=assoc_filter,
                                feature_count=assoc_count,
                                description=assoc_desc,
                                metadata={"backend": layer_props.get("layer_provider_type", "unknown"), "operation": "filter"}
                            )
                            logger.info(f"FilterMate: Pushed filter state to history for layer {assoc_layer.name()}")
                
                show_success_with_backend(iface, provider_type, 'filter', layer_count)
                iface.messageBar().pushInfo(
                    "FilterMate",
                    f"{feature_count:,} features visible in main layer"
                )
            elif task_name == 'undo':
                show_success_with_backend(iface, provider_type, 'undo', layer_count)
            elif task_name == 'redo':
                show_success_with_backend(iface, provider_type, 'redo', layer_count)
                iface.messageBar().pushInfo(
                    "FilterMate",
                    f"{feature_count:,} features visible in main layer (restored from history)"
                )
            elif task_name == 'reset':
                # Clear history on reset for source layer
                history = self.history_manager.get_history(source_layer.id())
                if history:
                    history.clear()
                    logger.info(f"FilterMate: Cleared filter history for source layer {source_layer.id()}")
                
                # Clear history for associated layers
                for layer_props in task_parameters.get("task", {}).get("layers", []):
                    if layer_props["layer_id"] in self.PROJECT_LAYERS:
                        layers = [layer for layer in self.PROJECT.mapLayersByName(layer_props["layer_name"]) 
                                 if layer.id() == layer_props["layer_id"]]
                        if len(layers) == 1:
                            assoc_layer = layers[0]
                            assoc_history = self.history_manager.get_history(assoc_layer.id())
                            if assoc_history:
                                assoc_history.clear()
                                logger.info(f"FilterMate: Cleared filter history for layer {assoc_layer.name()}")
                
                show_success_with_backend(iface, provider_type, 'reset', layer_count)
                iface.messageBar().pushInfo(
                    "FilterMate",
                    f"{feature_count:,} features visible in main layer"
                )

        extent = source_layer.extent()
        self.iface.mapCanvas().zoomToFeatureExtent(extent)  

        self.dockwidget.PROJECT_LAYERS = self.PROJECT_LAYERS


    def apply_subset_filter(self, task_name, layer):
        """
        Apply or remove subset filter expression on a layer.
        
        Uses FilterHistory module for proper undo/redo functionality.
        
        Args:
            task_name (str): Type of operation ('filter', 'undo', 'redo', 'reset')
            layer (QgsVectorLayer): Layer to apply filter to
            
        Notes:
            - For 'undo': Uses history.undo() to return to previous state
            - For 'reset': Clears subset string and history
            - For 'filter': Applies expression from Spatialite database
            - Changes trigger layer refresh automatically
        """
        if task_name == 'undo':
            # Use history manager for proper undo
            history = self.history_manager.get_history(layer.id())
            
            if history and history.can_undo():
                previous_state = history.undo()
                if previous_state:
                    layer.setSubsetString(previous_state.expression)
                    logger.info(f"FilterMate: Undo applied - restored filter: {previous_state.description}")
                    
                    if layer.subsetString() != '':
                        self.PROJECT_LAYERS[layer.id()]["infos"]["is_already_subset"] = True
                    else:
                        self.PROJECT_LAYERS[layer.id()]["infos"]["is_already_subset"] = False
                    return
            else:
                # No history available - clear filter
                logger.info(f"FilterMate: No undo history available, clearing filter")
                layer.setSubsetString('')
                self.PROJECT_LAYERS[layer.id()]["infos"]["is_already_subset"] = False
                return
        
        if task_name == 'redo':
            # Use history manager for proper redo
            history = self.history_manager.get_history(layer.id())
            
            if history and history.can_redo():
                next_state = history.redo()
                if next_state:
                    layer.setSubsetString(next_state.expression)
                    logger.info(f"FilterMate: Redo applied - restored filter: {next_state.description}")
                    
                    if layer.subsetString() != '':
                        self.PROJECT_LAYERS[layer.id()]["infos"]["is_already_subset"] = True
                    else:
                        self.PROJECT_LAYERS[layer.id()]["infos"]["is_already_subset"] = False
                    return
            else:
                # No redo available
                logger.info(f"FilterMate: No redo history available")
                return
        
        # For 'filter' and 'reset' operations, use database history
        conn = self.get_spatialite_connection()
        if conn is None:
            return
        
        with conn:
            cur = conn.cursor()

            last_subset_string = ''

            # Use parameterized query to prevent SQL injection
            cur.execute(
                """SELECT * FROM fm_subset_history 
                   WHERE fk_project = ? AND layer_id = ? 
                   ORDER BY seq_order DESC LIMIT 1""",
                (str(self.project_uuid), layer.id())
            )

            results = cur.fetchall()

            if len(results) == 1:
                result = results[0]
                last_subset_string = result[6].replace("\'\'", "\'")

            if task_name == 'filter':
                layer.setSubsetString(last_subset_string)

                if layer.subsetString() != '':
                    self.PROJECT_LAYERS[layer.id()]["infos"]["is_already_subset"] = True
                else:
                    self.PROJECT_LAYERS[layer.id()]["infos"]["is_already_subset"] = False

            elif task_name == 'reset':
                layer.setSubsetString('')
                self.PROJECT_LAYERS[layer.id()]["infos"]["is_already_subset"] = False


        # layer_props = self.PROJECT_LAYERS[layer.id()]
        # schema = layer_props["infos"]["layer_schema"]
        # table = layer_props["infos"]["layer_name"]
        # geometry_field = layer_props["infos"]["geometry_field"]
        # primary_key_name = layer_props["infos"]["primary_key_name"]


        # source_uri = QgsDataSourceUri(layer.source())
        # authcfg_id = source_uri.param('authcfg')
        # host = source_uri.host()
        # port = source_uri.port()
        # dbname = source_uri.database()
        # username = source_uri.username()
        # password = source_uri.password()
        # ssl_mode = source_uri.sslMode()

        # if authcfg_id != "":
        #     authConfig = QgsAuthMethodConfig()
        #     if authcfg_id in QgsApplication.authManager().configIds():
        #         QgsApplication.authManager().loadAuthenticationConfig(authcfg_id, authConfig, True)
        #         username = authConfig.config("username")
        #         password = authConfig.config("password")

        # if password != None and len(password) > 0:
        #     if ssl_mode != None:
        #         connexion = psycopg2.connect(user=username, password=password, host=host, port=port, database=dbname, sslmode=source_uri.encodeSslMode(ssl_mode))
        #     else:
        #         connexion = psycopg2.connect(user=username, password=password, host=host, port=port, database=dbname)
        # else:
        #     return False
        
        # sql_statement =  'CLUSTER "{schema}"."{table}" USING {schema}_{table}_{geometry_field}_idx;'.format(schema=schema,
        #                                                                                                     table=table,
        #                                                                                                     geometry_field=geometry_field)

        # sql_statement = sql_statement + 'ANALYZE "{schema}"."{table}";'.format(schema=schema,
        #                                                                         table=table)
        
        # with connexion.cursor() as cursor:
        #     cursor.execute(sql_statement)


    def save_variables_from_layer(self, layer, layer_properties=None):
        """
        Save layer filtering properties to both QGIS variables and Spatialite database.
        
        Stores layer properties in two locations:
        1. QGIS layer variables (for runtime access)
        2. Spatialite database (for persistence across sessions)
        
        Args:
            layer (QgsVectorLayer): Layer to save properties for
            layer_properties (list): List of tuples (key_group, key, value, type)
                Example: [('filtering', 'layer_filter_expression', 'population > 1000', 'str')]
                If None or empty, saves all properties
                
        Notes:
            - Uses parameterized SQL queries to prevent injection
            - Converts string values to proper types before storing
            - Creates filterMate_{key_group}_{key} variable names
            - Stores in fm_project_layers_properties table
            - Uses context manager for automatic connection cleanup
        """

        if layer_properties is None:
            layer_properties = []
        
        layer_all_properties_flag = False

        assert isinstance(layer, QgsVectorLayer)

        if len(layer_properties) == 0:
            layer_all_properties_flag = True

        if layer.id() in self.PROJECT_LAYERS.keys():
            conn = self.get_spatialite_connection()
            if conn is None:
                return
            
            with conn:
                cur = conn.cursor()

                if layer_all_properties_flag is True:
                    for key_group in ("infos", "exploring", "filtering"):
                        for key, value in self.PROJECT_LAYERS[layer.id()][key_group].items():
                            value_typped, type_returned = self.return_typped_value(value, 'save')
                            if type_returned in (list, dict):
                                value_typped = json.dumps(value_typped)
                            variable_key = "filterMate_{key_group}_{key}".format(key_group=key_group, key=key)
                            QgsExpressionContextUtils.setLayerVariable(layer, key_group + '_' +  key, value_typped)
                            # Use parameterized query
                            cur.execute(
                                """INSERT INTO fm_project_layers_properties 
                                   VALUES(?, datetime(), ?, ?, ?, ?, ?)""",
                                (str(uuid.uuid4()), str(self.project_uuid), layer.id(), 
                                 key_group, key, str(value_typped))
                            )

                else:
                    for layer_property in layer_properties:
                        if layer_property[0] in ("infos", "exploring", "filtering"):
                            if layer_property[0] in self.PROJECT_LAYERS[layer.id()] and layer_property[1] in self.PROJECT_LAYERS[layer.id()][layer_property[0]]:
                                value = self.PROJECT_LAYERS[layer.id()][layer_property[0]][layer_property[1]]
                                value_typped, type_returned = self.return_typped_value(value, 'save')
                                if type_returned in (list, dict):
                                    value_typped = json.dumps(value_typped)
                                variable_key = "filterMate_{key_group}_{key}".format(key_group=layer_property[0], key=layer_property[1])
                                QgsExpressionContextUtils.setLayerVariable(layer, variable_key, value_typped)
                                # Use parameterized query
                                cur.execute(
                                    """INSERT INTO fm_project_layers_properties 
                                       VALUES(?, datetime(), ?, ?, ?, ?, ?)""",
                                    (str(uuid.uuid4()), str(self.project_uuid), layer.id(),
                                     layer_property[0], layer_property[1], str(value_typped))
                                )

    def remove_variables_from_layer(self, layer, layer_properties=None):
        """
        Remove layer filtering properties from QGIS variables and Spatialite database.
        
        Clears stored properties from both runtime variables and persistent storage.
        Used when resetting filters or cleaning up removed layers.
        
        Args:
            layer (QgsVectorLayer): Layer to remove properties from
            layer_properties (list): List of tuples (key_group, key, value, type)
                If None or empty, removes ALL filterMate variables for the layer
                
        Notes:
            - Sets QGIS variables to empty string (effectively removes them)
            - Deletes corresponding rows from Spatialite database
            - Uses parameterized queries for SQL injection protection
            - Handles both selective and bulk removal
            - Uses context manager for safe database operations
        """
        
        if layer_properties is None:
            layer_properties = []
        
        layer_all_properties_flag = False

        assert isinstance(layer, QgsVectorLayer)

        if len(layer_properties) == 0:
            layer_all_properties_flag = True

        if layer.id() in self.PROJECT_LAYERS.keys():
            conn = self.get_spatialite_connection()
            if conn is None:
                return
            
            with conn:
                cur = conn.cursor()

                if layer_all_properties_flag is True:
                    # Use parameterized query
                    cur.execute(
                        """DELETE FROM fm_project_layers_properties 
                           WHERE fk_project = ? and layer_id = ?""",
                        (str(self.project_uuid), layer.id())
                    )
                    QgsExpressionContextUtils.setLayerVariables(layer, {})

                else:
                    for layer_property in layer_properties:
                        if layer_property[0] in ("infos", "exploring", "filtering"):
                            if layer_property[0] in self.PROJECT_LAYERS[layer.id()] and layer_property[1] in self.PROJECT_LAYERS[layer.id()][layer_property[0]]:
                                # Use parameterized query
                                cur.execute(
                                    """DELETE FROM fm_project_layers_properties  
                                       WHERE fk_project = ? and layer_id = ? 
                                       and meta_type = ? and meta_key = ?""",
                                    (str(self.project_uuid), layer.id(), 
                                     layer_property[0], layer_property[1])
                                )
                                variable_key = "filterMate_{key_group}_{key}".format(key_group=layer_property[0], key=layer_property[1])
                                QgsExpressionContextUtils.setLayerVariable(layer, variable_key, '')

      

    def create_spatial_index_for_layer(self, layer):    

        alg_params_createspatialindex = {
            "INPUT": layer
        }
        processing.run('qgis:createspatialindex', alg_params_createspatialindex)
    

    def init_filterMate_db(self):
        """
        Initialize FilterMate Spatialite database with required schema.
        
        Creates database file and tables if they don't exist. Sets up schema for
        storing project configurations, layer properties, and datasource information.
        
        Tables created:
        - fm_projects: Project metadata and UUIDs
        - fm_project_layers_properties: Layer filtering/export settings
        - fm_project_datasources: Data source connection info
        
        Notes:
            - Database location: <project_dir>/.filterMate/<project_name>.db
            - Enables Spatialite extension for spatial operations
            - Idempotent: safe to call multiple times
            - Sets up project UUID in QGIS variables
            - Creates directory structure if missing
        """

        if self.PROJECT != None and len(list(self.PROJECT.mapLayers().values())) > 0:

            self.project_file_name = os.path.basename(self.PROJECT.absoluteFilePath())
            self.project_file_path = self.PROJECT.absolutePath()
            
            # Ensure database directory exists
            db_dir = os.path.dirname(self.db_file_path)
            if not os.path.exists(db_dir):
                try:
                    os.makedirs(db_dir, exist_ok=True)
                    logger.info(f"Created database directory: {db_dir}")
                except OSError as error:
                    error_msg = f"Could not create database directory {db_dir}: {error}"
                    logger.error(error_msg)
                    iface.messageBar().pushCritical("FilterMate", error_msg)
                    return

            logger.debug(f"Database file path: {self.db_file_path}")

            if self.CONFIG_DATA["APP"]["OPTIONS"]["FRESH_RELOAD_FLAG"] is True:
                try: 
                    os.remove(self.db_file_path)
                    self.CONFIG_DATA["APP"]["OPTIONS"]["FRESH_RELOAD_FLAG"] = False
                    with open(ENV_VARS["DIR_CONFIG"] +  os.sep + 'config.json', 'w') as outfile:
                        outfile.write(json.dumps(self.CONFIG_DATA, indent=4))  
                except OSError as error: 
                    logger.error(f"Failed to remove database file: {error}")
            
            project_settings = self.CONFIG_DATA["CURRENT_PROJECT"]
            logger.debug(f"Project settings: {project_settings}")

            if not os.path.exists(self.db_file_path):
                memory_uri = 'NoGeometry?field=plugin_name:string(255,0)&field=_created_at:date(0,0)&field=_updated_at:date(0,0)&field=_version:string(255,0)'
                layer_name = 'filterMate_db'
                layer = QgsVectorLayer(memory_uri, layer_name, "memory")

                crs = QgsCoordinateReferenceSystem("epsg:4326")
                
                try:
                    QgsVectorFileWriter.writeAsVectorFormat(layer, self.db_file_path, "utf-8", crs, driverName="SQLite", datasourceOptions=["SPATIALITE=YES","SQLITE_MAX_LENGTH=100000000",])
                except Exception as error:
                    error_msg = f"Failed to create database file {self.db_file_path}: {error}"
                    logger.error(error_msg)
                    iface.messageBar().pushCritical("FilterMate", error_msg)
                    return
            
            try:
                conn = self.get_spatialite_connection()
                if conn is None:
                    error_msg = "Cannot initialize FilterMate database: connection failed"
                    logger.error(error_msg)
                    iface.messageBar().pushCritical("FilterMate", error_msg, duration=10)
                    return
            except Exception as e:
                error_msg = f"Critical error connecting to database: {str(e)}"
                logger.error(error_msg)
                iface.messageBar().pushCritical("FilterMate", error_msg, duration=10)
                return

            try:
                with conn:
                    cur = conn.cursor()
                    cur.execute("""PRAGMA foreign_keys = ON;""")
                    
                    # Check if database is already initialized
                    cur.execute("""SELECT count(*) FROM sqlite_master WHERE type='table' AND name='fm_projects';""")
                    tables_exist = cur.fetchone()[0] > 0
                    
                    if not tables_exist:
                        # Initialize database only if tables don't exist
                        cur.execute("""INSERT INTO filterMate_db VALUES(1, '{plugin_name}', datetime(), datetime(), '{version}');""".format(
                                                                                                                                        plugin_name='FilterMate',
                                                                                                                                        version='1.6'
                                                                                                                                        )
                        )

                        cur.execute("""CREATE TABLE fm_projects (
                                        project_id VARYING CHARACTER(255) NOT NULL PRIMARY KEY,
                                        _created_at DATETIME NOT NULL,
                                        _updated_at DATETIME NOT NULL,
                                        project_name VARYING CHARACTER(255) NOT NULL,
                                        project_path VARYING CHARACTER(255) NOT NULL,
                                        project_settings TEXT NOT NULL);
                                        """)

                        cur.execute("""CREATE TABLE fm_subset_history (
                                        id VARYING CHARACTER(255) NOT NULL PRIMARY KEY,
                                        _updated_at DATETIME NOT NULL,
                                        fk_project VARYING CHARACTER(255) NOT NULL,
                                        layer_id VARYING CHARACTER(255) NOT NULL,
                                        layer_source_id VARYING CHARACTER(255) NOT NULL,
                                        seq_order INTEGER NOT NULL,
                                        subset_string TEXT NOT NULL,
                                        FOREIGN KEY (fk_project)  
                                        REFERENCES fm_projects(project_id));
                                        """)
                        
                        cur.execute("""CREATE TABLE fm_project_layers_properties (
                                        id VARYING CHARACTER(255) NOT NULL PRIMARY KEY,
                                        _updated_at DATETIME NOT NULL,
                                        fk_project VARYING CHARACTER(255) NOT NULL,
                                        layer_id VARYING CHARACTER(255) NOT NULL,
                                        meta_type VARYING CHARACTER(255) NOT NULL,
                                        meta_key VARYING CHARACTER(255) NOT NULL,
                                        meta_value TEXT NOT NULL,
                                        FOREIGN KEY (fk_project)  
                                        REFERENCES fm_projects(project_id),
                                        CONSTRAINT property_unicity
                                        UNIQUE(fk_project, layer_id, meta_type, meta_key) ON CONFLICT REPLACE);
                                        """)
                        
                        self.project_uuid = uuid.uuid4()
                    
                        cur.execute("""INSERT INTO fm_projects VALUES('{project_id}', datetime(), datetime(), '{project_name}', '{project_path}', '{project_settings}');""".format(
                                                                                                                                                                            project_id=self.project_uuid,
                                                                                                                                                                            project_name=self.project_file_name,
                                                                                                                                                                            project_path=self.project_file_path,
                                                                                                                                                                            project_settings=json.dumps(project_settings).replace("\'","\'\'")
                                                                                                                                                                            )
                        )

                        conn.commit()
                        
                        # Set the project UUID for newly initialized database
                        QgsExpressionContextUtils.setProjectVariable(self.PROJECT, 'filterMate_db_project_uuid', self.project_uuid)
                    else:
                        # Database already initialized, check if this project exists
                        cur.execute("""SELECT * FROM fm_projects WHERE project_name = '{project_name}' AND project_path = '{project_path}' LIMIT 1;""".format(
                                                                                                                                                        project_name=self.project_file_name,
                                                                                                                                                        project_path=self.project_file_path
                                                                                                                                                        )
                        )

                        results = cur.fetchall()

                        if len(results) == 1:
                            result = results[0]
                            project_settings = result[-1].replace("\'\'", "\'")
                            self.project_uuid = result[0]
                            self.CONFIG_DATA["CURRENT_PROJECT"] = json.loads(project_settings)
                            QgsExpressionContextUtils.setProjectVariable(self.PROJECT, 'filterMate_db_project_uuid', self.project_uuid)

                            # cur.execute("""UPDATE fm_projects 
                            #                 SET _updated_at = datetime(),
                            #                     project_settings = '{project_settings}' 
                            #                 WHERE project_id = '{project_id}'""".format(
                            #                                                             project_settings=project_settings,
                            #                                                             project_id=project_id
                            #                                                             )
                            # )

                        else:
                            self.project_uuid = uuid.uuid4()
                            cur.execute("""INSERT INTO fm_projects VALUES('{project_id}', datetime(), datetime(), '{project_name}', '{project_path}', '{project_settings}');""".format(
                                                                                                                                                                                project_id=self.project_uuid,
                                                                                                                                                                                project_name=self.project_file_name,
                                                                                                                                                                                project_path=self.project_file_path,
                                                                                                                                                                                project_settings=json.dumps(project_settings).replace("\'","\'\'")
                                                                                                                                                                                )
                            )
                            QgsExpressionContextUtils.setProjectVariable(self.PROJECT, 'filterMate_db_project_uuid', self.project_uuid)

                        conn.commit()

            except Exception as e:
                error_msg = f"Error during database initialization: {str(e)}"
                logger.error(error_msg)
                iface.messageBar().pushCritical("FilterMate", error_msg, duration=10)
                return
            finally:
                if conn:
                    try:
                        cur.close()
                        conn.close()
                    except Exception:
                        pass

            # if "FILTER" in self.CONFIG_DATA["CURRENT_PROJECT"] and "app_postgresql_temp_schema" in self.CONFIG_DATA["CURRENT_PROJECT"]["FILTER"]:
            #     self.app_postgresql_temp_schema = self.CONFIG_DATA["CURRENT_PROJECT"]["FILTER"]["app_postgresql_temp_schema"]
            # else:
            #     self.CONFIG_DATA["CURRENT_PROJECT"]["FILTER"]["app_postgresql_temp_schema"] = 'filterMate_temp'
            #     self.app_postgresql_temp_schema = self.CONFIG_DATA["CURRENT_PROJECT"]["FILTER"]["app_postgresql_temp_schema"]



    def add_project_datasource(self, layer):

        connexion, source_uri = get_datasource_connexion_from_layer(layer)

        sql_statement = 'CREATE SCHEMA IF NOT EXISTS {app_temp_schema} AUTHORIZATION postgres;'.format(app_temp_schema=self.app_postgresql_temp_schema)

        logger.debug(f"SQL statement: {sql_statement}")


        with connexion.cursor() as cursor:
            cursor.execute(sql_statement)



            
    def save_project_variables(self, name=None):
        
        global ENV_VARS

        if self.dockwidget != None:
            self.CONFIG_DATA = self.dockwidget.CONFIG_DATA
            conn = None
            cur = None
            try:
                conn = self.get_spatialite_connection()
                if conn is None:
                    return
                cur = conn.cursor()

                if name != None:
                    self.project_file_name = name
                    self.project_file_path = self.PROJECT.absolutePath()    

                project_settings = self.CONFIG_DATA["CURRENT_PROJECT"]    

                # Use parameterized query
                cur.execute(
                    """UPDATE fm_projects SET 
                       _updated_at = datetime(),
                       project_name = ?,
                       project_path = ?,
                       project_settings = ?
                       WHERE project_id = ?""",
                    (self.project_file_name, self.project_file_path, 
                     json.dumps(project_settings), str(self.project_uuid))
                )
                conn.commit()
            finally:
                if cur:
                    cur.close()
                if conn:
                    conn.close()

            with open(ENV_VARS["DIR_CONFIG"] +  os.sep + 'config.json', 'w') as outfile:
                outfile.write(json.dumps(self.CONFIG_DATA, indent=4))


    def layer_management_engine_task_completed(self, result_project_layers, task_name):
        """
        Handle completion of layer management tasks.
        
        Called when LayersManagementEngineTask completes. Updates internal layer registry,
        refreshes UI, and handles layer addition/removal cleanup.
        
        Args:
            result_project_layers (dict): Updated PROJECT_LAYERS dictionary with all layer metadata
            task_name (str): Type of task completed ('add_layers', 'remove_layers', etc.)
            
        Notes:
            - Updates dockwidget's PROJECT_LAYERS reference
            - Calls get_project_layers_from_app() to refresh UI
            - Handles special cases for layer removal and project reset
            - Updates layer comboboxes and enables/disables controls
            - Reconnects widget signals after changes
        """

        init_env_vars()

        global ENV_VARS

        # CRITICAL: Validate and update PROJECT_LAYERS before UI refresh
        # This ensures layer IDs are synchronized before dockwidget accesses them
        if result_project_layers is None:
            logger.error("layer_management_engine_task_completed received None for result_project_layers")
            return
        
        self.PROJECT_LAYERS = result_project_layers
        self.PROJECT = ENV_VARS["PROJECT"]
        
        logger.debug(f"Updated PROJECT_LAYERS with {len(self.PROJECT_LAYERS)} layers after {task_name}")
        
        ENV_VARS["PATH_ABSOLUTE_PROJECT"] = os.path.normpath(self.PROJECT.readPath("./"))
        if ENV_VARS["PATH_ABSOLUTE_PROJECT"] =='./':
            if ENV_VARS["PLATFORM"].startswith('win'):
                ENV_VARS["PATH_ABSOLUTE_PROJECT"] =  os.path.normpath(os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop'))
            else:
                ENV_VARS["PATH_ABSOLUTE_PROJECT"] =  os.path.normpath(os.environ['HOME'])

        if self.dockwidget != None:

            conn = self.get_spatialite_connection()
            if conn is None:
                # Even if DB connection fails, we must update the UI
                self.dockwidget.get_project_layers_from_app(self.PROJECT_LAYERS, self.PROJECT)
                return
            cur = conn.cursor()

            if task_name in ("add_layers","remove_layers","remove_all_layers"):
                if task_name == 'add_layers':
                    for layer_key in self.PROJECT_LAYERS.keys():
                        if layer_key not in self.dockwidget.PROJECT_LAYERS.keys():
                            try:
                                self.dockwidget.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].remove_list_widget(layer_key)
                            except (KeyError, AttributeError, RuntimeError) as e:
                                # Widget may not exist or already removed
                                pass

                        # CRITICAL: Verify layer structure before accessing nested properties
                        if "infos" not in self.PROJECT_LAYERS[layer_key]:
                            logger.warning(f"Layer {layer_key} missing required 'infos' in PROJECT_LAYERS")
                            continue
                        
                        layer_info = self.PROJECT_LAYERS[layer_key]["infos"]
                        required_keys = ["layer_provider_type", "layer_name", "layer_id"]
                        missing_keys = [k for k in required_keys if k not in layer_info or layer_info[k] is None]
                        
                        if missing_keys:
                            logger.warning(f"Layer {layer_key} missing required keys in infos: {missing_keys}")
                            continue
                            
                        layer_source_type = layer_info["layer_provider_type"]                    
                        if layer_source_type not in self.project_datasources:
                            self.project_datasources[layer_source_type] = {}

                    
                        layer_props = self.PROJECT_LAYERS[layer_key]
                        layer = None
                        layers = [layer for layer in self.PROJECT.mapLayersByName(layer_info["layer_name"]) if layer.id() == layer_info["layer_id"]]
                        if len(layers) == 1:
                            layer = layers[0]
                        
                        # Skip if layer not found
                        if layer is None:
                            continue
                        
                        source_uri, authcfg_id = get_data_source_uri(layer)

                        if authcfg_id != None:
                            if authcfg_id not in self.project_datasources[layer_source_type].keys():
                                connexion, source_uri = get_datasource_connexion_from_layer(layer)
                                self.project_datasources[layer_source_type][authcfg_id] = connexion
                        
                        else:
                            uri = source_uri.uri().strip()
                            relative_path = uri.split('|')[0] if len(uri.split('|')) == 2 else uri
                            layer_name = uri.split('|')[1] if len(uri.split('|')) == 2 else None
                            absolute_path = os.path.join(os.path.normpath(ENV_VARS["PATH_ABSOLUTE_PROJECT"]), os.path.normpath(relative_path))
                            if absolute_path not in self.project_datasources[layer_source_type].keys():
                                self.project_datasources[layer_source_type][absolute_path] = []
                            
                            if uri not in self.project_datasources[layer_source_type][absolute_path]:
                                self.project_datasources[layer_source_type][absolute_path].append(absolute_path + ('|' + layer_name if layer_name is not None else ''))
                            

                else:
                                       
                    for layer_key in self.dockwidget.PROJECT_LAYERS.keys():
                        if layer_key not in self.PROJECT_LAYERS.keys():
                            cur.execute("""DELETE FROM fm_project_layers_properties 
                                            WHERE fk_project = '{project_id}' and layer_id = '{layer_id}';""".format(
                                                                                                                project_id=self.project_uuid,
                                                                                                                layer_id=layer_key
                                                                                                                )
                            )
                            conn.commit()
                            try:
                                self.dockwidget.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].remove_list_widget(layer_key)
                            except (KeyError, AttributeError, RuntimeError) as e:
                                # Widget may not exist or already removed
                                pass
                        else:
                            # CRITICAL: Only process layers that still exist in PROJECT_LAYERS
                            # Verify layer structure before accessing nested properties
                            if "infos" not in self.PROJECT_LAYERS[layer_key]:
                                logger.warning(f"Layer {layer_key} missing required 'infos' in PROJECT_LAYERS")
                                continue
                            
                            layer_info = self.PROJECT_LAYERS[layer_key]["infos"]
                            required_keys = ["layer_provider_type", "layer_name", "layer_id"]
                            missing_keys = [k for k in required_keys if k not in layer_info or layer_info[k] is None]
                            
                            if missing_keys:
                                logger.warning(f"Layer {layer_key} missing required keys in infos: {missing_keys}")
                                continue

                            layer_source_type = layer_info["layer_provider_type"]                    
                            if layer_source_type not in self.project_datasources:
                                self.project_datasources[layer_source_type] = {}

                        
                            layer_props = self.PROJECT_LAYERS[layer_key]
                            layer = None
                            layers = [layer for layer in self.PROJECT.mapLayersByName(layer_info["layer_name"]) if layer.id() == layer_info["layer_id"]]
                            if len(layers) == 1:
                                layer = layers[0]
                            
                            # Skip if layer not found
                            if layer is None:
                                continue
                        
                            source_uri, authcfg_id = get_data_source_uri(layer)

                            if authcfg_id != None:

                                if authcfg_id not in self.project_datasources[layer_source_type].keys():
                                    connexion, source_uri = get_datasource_connexion_from_layer(layer)
                                    self.project_datasources[layer_source_type][authcfg_id] = connexion
                                
                            
                            else:

                                uri = source_uri.uri().strip()
                                relative_path = uri.split('|')[0] if len(uri.split('|')) == 2 else uri
                                absolute_path = os.path.normpath(os.path.join(ENV_VARS["PATH_ABSOLUTE_PROJECT"], relative_path))
                                if absolute_path in self.project_datasources[layer_source_type].keys():
                                    self.project_datasources[layer_source_type][absolute_path].remove(uri)
                                if uri in self.project_datasources[layer_source_type][absolute_path]:
                                    self.project_datasources[layer_source_type][absolute_path].remove(uri)
                
                
                self.save_project_variables()                    
                self.dockwidget.get_project_layers_from_app(self.PROJECT_LAYERS, self.PROJECT)

            self.MapLayerStore = self.PROJECT.layerStore()
            self.update_datasource()
            logger.debug(f"Project datasources: {self.project_datasources}")
            cur.close()
            conn.close()
            
    def update_datasource(self):
        # POSTGRESQL_AVAILABLE est maintenant importé au niveau du module
        ogr_driver_list = [ogr.GetDriver(i).GetDescription() for i in range(ogr.GetDriverCount())]
        ogr_driver_list.sort()
        logger.debug(f"OGR drivers available: {ogr_driver_list}")

        # Vérifier si PostgreSQL est disponible et s'il y a des connexions PostgreSQL
        if 'postgresql' in self.project_datasources and POSTGRESQL_AVAILABLE:
            list(self.project_datasources['postgresql'].keys())
            if len(self.project_datasources['postgresql']) >= 1:
                postgresql_connexions = list(self.project_datasources['postgresql'].keys())
                if self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"] == "":
                    self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"] = self.project_datasources['postgresql'][postgresql_connexions[0]]
                    self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["IS_ACTIVE_POSTGRESQL"] = True
            else:
                self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"] = ""
                self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["IS_ACTIVE_POSTGRESQL"] = False
        elif 'postgresql' in self.project_datasources and not POSTGRESQL_AVAILABLE:
            # PostgreSQL layers detected but psycopg2 not available
            self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"] = ""
            self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["IS_ACTIVE_POSTGRESQL"] = False
            self.iface.messageBar().pushWarning(
                "FilterMate",
                "PostgreSQL layers detected but psycopg2 is not installed. "
                "Using local Spatialite backend. "
                "For better performance with large datasets, install psycopg2."
            )
        else:
            self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"] = ""
            self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["IS_ACTIVE_POSTGRESQL"] = False

        for current_datasource in list(self.project_datasources.keys()):
            if current_datasource != "postgresql":
                for project_datasource in self.project_datasources[current_datasource].keys():
                    datasources = self.project_datasources[current_datasource][project_datasource]
                    for datasource in datasources:
                        # Extract file extension safely
                        datasource_path = datasource.split('|')[0]
                        path_parts = datasource_path.split('.')
                        # Check if there's an extension (at least 2 parts after split)
                        datasource_ext = path_parts[-1] if len(path_parts) >= 2 else datasource_path
                        datasource_type_name = [ogr_name for ogr_name in ogr_driver_list if ogr_name.upper() == datasource_ext.upper()]

                    if self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["IS_ACTIVE_POSTGRESQL"] is True:
                        self.create_foreign_data_wrapper(project_datasource, os.path.basename(project_datasource), datasource_type_name[0])
                        




    def create_foreign_data_wrapper(self, project_datasource, datasource, format):

        sql_request = """CREATE EXTENSION IF NOT EXISTS ogr_fdw;
                        CREATE SCHEMA IF NOT EXISTS filter_mate_temp AUTHORIZATION postgres; 
                        DROP SERVER IF exists server_{datasource_name}  CASCADE;
                        CREATE SERVER server_{datasource_name} 
                        FOREIGN DATA WRAPPER ogr_fdw OPTIONS (
                            datasource '{datasource}', 
                            format '{format}');
                        IMPORT FOREIGN SCHEMA ogr_all
                        FROM SERVER server_{datasource_name} INTO filter_mate_temp;""".format(datasource_name=datasource.replace('.', '_').replace('-', '_').replace('@', '_'),
                                                                                        datasource=project_datasource.replace('\\\\', '\\'),
                                                                                        format=format)

        if self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["IS_ACTIVE_POSTGRESQL"] is True:
            connexion = self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"]
            with connexion.cursor() as cursor:
                cursor.execute(sql_request)

            
        



    def can_cast(self, dest_type, source_value):
        try:
            dest_type(source_value)
            return True
        except (ValueError, TypeError):
            return False


    def return_typped_value(self, value_as_string, action=None):
        value_typped= None
        type_returned = None

        if value_as_string == None or value_as_string == '':   
            value_typped = str('')
            type_returned = str
        elif str(value_as_string).find('{') == 0 and self.can_cast(dict, value_as_string) is True:
            if action == 'save':
                value_typped = json.dumps(dict(value_as_string))
            elif action == 'load':
                value_typped = dict(json.loads(value_as_string))
            type_returned = dict
        elif str(value_as_string).find('[') == 0 and self.can_cast(list, value_as_string) is True:
            if action == 'save':
                value_typped = list(value_as_string)
            elif action == 'load':
                value_typped = list(json.loads(value_as_string))
            type_returned = list
        elif self.can_cast(bool, value_as_string) is True and str(value_as_string).upper() in ('FALSE','TRUE'):
            value_typped = bool(value_as_string)
            type_returned = bool
        elif self.can_cast(float, value_as_string) is True and len(str(value_as_string).split('.')) > 1:
            value_typped = float(value_as_string)
            type_returned = float
        elif self.can_cast(int, value_as_string) is True:
            value_typped = int(value_as_string)
            type_returned = int
        else:
            value_typped = str(value_as_string)
            type_returned = str

        return value_typped, type_returned       

# class barProgress:

#     def __init__(self):
#         self.prog = 0
#         self.bar = None
#         self.type = type
#         iface.messageBar().clearWidgets()
#         self.init()
#         self.bar.show()

#     def init(self):
#         self.bar = QProgressBar()
#         self.bar.setMaximum(100)
#         self.bar.setValue(self.prog)
#         iface.mainWindow().statusBar().addWidget(self.bar)

#     def show(self):
#         self.bar.show()


#     def update(self, prog):
#         self.bar.setValue(prog)

#     def hide(self):
#         self.bar.hide()

# class msgProgress:

#     def __init__(self):
#         self.messageBar = iface.messageBar().createMessage('Doing something time consuming...')
#         self.progressBar = QProgressBar()
#         self.progressBar.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
#         self.cancelButton = QPushButton()
#         self.cancelButton.setText('Cancel')
#         self.messageBar.layout().addWidget(self.progressBar)
#         self.messageBar.layout().addWidget(self.cancelButton)
#         iface.messageBar().pushWidget(self.messageBar, Qgis.Info)


#     def update(self, prog):
#         self.progressBar.setValue(prog)

#     def reset(self):
#         self.progressBar.setValue(0)

#     def setText(self, text):
#         self.messageBar.setText(text)




def zoom_to_features(layer, t0):
    canvas = iface.mapCanvas()
    canvas.setExtent(layer.extent())
    canvas.refresh()

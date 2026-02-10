# -*- coding: utf-8 -*-
"""
Layer Task Completion Handler for FilterMate v4.7

Handles completion of layer management tasks (add/remove layers).
Extracted from FilterMateApp.layer_management_engine_task_completed() for God Class reduction.

Author: FilterMate Team
Date: January 2026
"""
import os
import logging
import weakref
from typing import Dict, Callable, Optional, Any
from qgis.PyQt.QtCore import QTimer

logger = logging.getLogger('FilterMate.LayerTaskCompletionHandler')


class LayerTaskCompletionHandler:
    """
    Handles completion of layer management tasks.
    
    v4.7: Extracted from FilterMateApp.layer_management_engine_task_completed().
    Manages layer additions, removals, database cleanup, and UI updates.
    """
    
    def __init__(
        self,
        get_spatialite_connection: Callable,
        get_project_uuid: Callable,
        get_project: Callable,
        get_dockwidget: Callable,
        get_project_layers: Callable,
        set_project_layers: Callable,
        get_history_manager: Callable,
        save_project_variables_callback: Callable,
        update_datasource_callback: Callable,
        get_env_vars: Callable,
        warm_query_cache_callback: Optional[Callable] = None,
        process_add_layers_queue_callback: Optional[Callable] = None,
        refresh_ui_after_project_load_callback: Optional[Callable] = None,
        set_loading_flag_callback: Optional[Callable] = None,
        validate_layer_info_callback: Optional[Callable] = None,
        update_datasource_for_layer_callback: Optional[Callable] = None,
        remove_datasource_for_layer_callback: Optional[Callable] = None,
        pending_tasks_counter_callbacks: Optional[Dict[str, Callable]] = None,
        stability_constants: Optional[Dict] = None
    ):
        """
        Initialize LayerTaskCompletionHandler.
        
        Args:
            get_spatialite_connection: Callback to get DB connection
            get_project_uuid: Callback to get project UUID
            get_project: Callback to get QgsProject
            get_dockwidget: Callback to get dockwidget
            get_project_layers: Callback to get PROJECT_LAYERS dict
            set_project_layers: Callback to set PROJECT_LAYERS dict
            get_history_manager: Callback to get HistoryManager
            save_project_variables_callback: Callback to save project variables
            update_datasource_callback: Callback to update datasources
            get_env_vars: Callback to get ENV_VARS
            warm_query_cache_callback: Optional callback to warm query cache
            process_add_layers_queue_callback: Optional callback to process queue
            refresh_ui_after_project_load_callback: Optional callback for UI refresh
            set_loading_flag_callback: Optional callback to set loading flag
            validate_layer_info_callback: Optional callback to validate layer info
            update_datasource_for_layer_callback: Optional callback for layer datasource update
            remove_datasource_for_layer_callback: Optional callback for layer datasource removal
            pending_tasks_counter_callbacks: Optional dict with get/decrement callbacks
            stability_constants: Optional stability constants dict
        """
        self._get_connection = get_spatialite_connection
        self._get_uuid = get_project_uuid
        self._get_project = get_project
        self._get_dockwidget = get_dockwidget
        self._get_project_layers = get_project_layers
        self._set_project_layers = set_project_layers
        self._get_history_manager = get_history_manager
        self._save_project_variables = save_project_variables_callback
        self._update_datasource = update_datasource_callback
        self._get_env_vars = get_env_vars
        self._warm_cache = warm_query_cache_callback
        self._process_queue = process_add_layers_queue_callback
        self._refresh_ui = refresh_ui_after_project_load_callback
        self._set_loading_flag = set_loading_flag_callback
        self._validate_layer_info = validate_layer_info_callback
        self._update_layer_datasource = update_datasource_for_layer_callback
        self._remove_layer_datasource = remove_datasource_for_layer_callback
        self._counter_callbacks = pending_tasks_counter_callbacks or {}
        self._stability_constants = stability_constants or {
            'SIGNAL_DEBOUNCE_MS': 150,
            'UI_REFRESH_DELAY_MS': 300
        }
    
    def handle_task_completion(
        self,
        result_project_layers: Dict,
        task_name: str,
        loading_new_project: bool = False
    ) -> None:
        """
        Handle completion of layer management task.
        
        Args:
            result_project_layers: Updated PROJECT_LAYERS dictionary
            task_name: Type of task ('add_layers', 'remove_layers', 'remove_all_layers')
            loading_new_project: True if loading a new project
        """
        print(f"[FM-DIAG] LayerTaskCompletionHandler: task={task_name}, layers={len(result_project_layers) if result_project_layers else 0}")
        logger.info(f"Layer task completed: {task_name}, layers={len(result_project_layers) if result_project_layers else 0}")
        
        # CRITICAL: Validate input
        if result_project_layers is None:
            logger.error("Task completion received None for result_project_layers")
            return
        
        # Update PROJECT_LAYERS
        self._set_project_layers(result_project_layers)
        project = self._get_project()
        
        # Update ENV_VARS paths
        self._update_env_paths()
        
        dockwidget = self._get_dockwidget()
        if dockwidget is None:
            return
        
        # Get database connection
        conn = self._get_connection()
        if conn is None:
            # Update UI even if DB connection fails
            dockwidget.get_project_layers_from_app(result_project_layers, project)
            return
        
        cur = conn.cursor()
        
        try:
            if task_name in ("add_layers", "remove_layers", "remove_all_layers"):
                if task_name == 'add_layers':
                    self._handle_add_layers(result_project_layers, dockwidget)
                else:
                    self._handle_remove_layers(result_project_layers, dockwidget, cur, conn)
                
                self._save_project_variables()
                dockwidget.get_project_layers_from_app(result_project_layers, project)
            
            # Update map layer store and datasources
            map_layer_store = project.layerStore()
            self._update_datasource()
            
        finally:
            # STABILITY: Always close DB connection
            try:
                cur.close()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
        
        # Handle add_layers post-processing
        if task_name == 'add_layers':
            self._handle_add_layers_completion(loading_new_project, dockwidget)
    
    def _update_env_paths(self) -> None:
        """Update ENV_VARS with current project paths."""
        project = self._get_project()
        env_vars = self._get_env_vars()
        
        path_absolute_project = os.path.normpath(project.readPath("./"))
        if path_absolute_project == './':
            # Fallback to home/desktop
            if os.name == 'nt':  # Windows
                path_absolute_project = os.path.normpath(
                    os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop')
                )
            else:
                path_absolute_project = os.path.normpath(os.environ.get('HOME', ''))
        
        env_vars["PATH_ABSOLUTE_PROJECT"] = path_absolute_project
    
    def _handle_add_layers(
        self,
        result_project_layers: Dict,
        dockwidget: Any
    ) -> None:
        """
        Handle layer additions.
        
        Args:
            result_project_layers: Updated PROJECT_LAYERS
            dockwidget: Dockwidget instance
        """
        for layer_key in result_project_layers.keys():
            if layer_key not in dockwidget.PROJECT_LAYERS.keys():
                try:
                    dockwidget.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].remove_list_widget(layer_key)
                except (KeyError, AttributeError, RuntimeError):
                    pass
            
            # Validate and update datasource
            if self._validate_layer_info:
                layer_info = self._validate_layer_info(layer_key)
                if layer_info and self._update_layer_datasource:
                    self._update_layer_datasource(layer_info)
    
    def _handle_remove_layers(
        self,
        result_project_layers: Dict,
        dockwidget: Any,
        cursor: Any,
        connection: Any
    ) -> None:
        """
        Handle layer removals.
        
        Args:
            result_project_layers: Updated PROJECT_LAYERS
            dockwidget: Dockwidget instance
            cursor: Database cursor
            connection: Database connection
        """
        history_manager = self._get_history_manager()
        project_uuid = self._get_uuid()
        
        for layer_key in dockwidget.PROJECT_LAYERS.keys():
            if layer_key not in result_project_layers.keys():
                # Layer removed - clean up database
                cursor.execute(
                    """DELETE FROM fm_project_layers_properties 
                       WHERE fk_project = ? AND layer_id = ?""",
                    (project_uuid, layer_key)
                )
                connection.commit()
                
                # Clean up history
                history_manager.remove_history(layer_key)
                logger.info(f"Removed history for deleted layer {layer_key}")
                
                try:
                    dockwidget.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].remove_list_widget(layer_key)
                except (KeyError, AttributeError, RuntimeError):
                    pass
            else:
                # Update datasource for remaining layers
                if self._validate_layer_info:
                    layer_info = self._validate_layer_info(layer_key)
                    if layer_info and self._remove_layer_datasource:
                        self._remove_layer_datasource(layer_info)
    
    def _handle_add_layers_completion(
        self,
        loading_new_project: bool,
        dockwidget: Any
    ) -> None:
        """
        Handle post-processing after add_layers completion.
        
        Args:
            loading_new_project: True if loading a new project
            dockwidget: Dockwidget instance
        """
        # Decrement pending tasks counter
        if 'get' in self._counter_callbacks and 'decrement' in self._counter_callbacks:
            pending = self._counter_callbacks['get']()
            if pending > 0:
                self._counter_callbacks['decrement']()
                logger.debug(f"Completed add_layers task (remaining: {self._counter_callbacks['get']()})")
        
        # Warm query cache
        if self._warm_cache:
            self._warm_cache()
        
        # Process queued operations
        if self._process_queue and 'get_queue' in self._counter_callbacks:
            queue = self._counter_callbacks['get_queue']()
            pending = self._counter_callbacks.get('get', lambda: 0)()
            if queue and pending == 0:
                logger.info(f"Processing {len(queue)} queued add_layers operations")
                # Use weakref for safety
                weak_callback = weakref.ref(self._process_queue)
                def safe_process():
                    callback = weak_callback()
                    if callback:
                        callback()
                QTimer.singleShot(
                    self._stability_constants['SIGNAL_DEBOUNCE_MS'],
                    safe_process
                )
        
        # UI refresh for new project
        if loading_new_project:
            logger.info("New project loaded - forcing UI refresh")
            if self._set_loading_flag:
                self._set_loading_flag(False)
            
            if dockwidget and dockwidget.widgets_initialized and self._refresh_ui:
                # Use weakref for safety
                weak_callback = weakref.ref(self._refresh_ui)
                def safe_refresh():
                    callback = weak_callback()
                    if callback:
                        callback()
                QTimer.singleShot(
                    self._stability_constants['UI_REFRESH_DELAY_MS'],
                    safe_refresh
                )

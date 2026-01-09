# -*- coding: utf-8 -*-
"""
Layer Lifecycle Port for FilterMate v4.0

Defines the interface for layer lifecycle operations in the hexagonal architecture.
This port is implemented by LayerLifecycleService.

Author: FilterMate Team
Date: January 2026
"""
from typing import List, Dict, Any, Callable, Protocol
from abc import ABC, abstractmethod


class LayerLifecyclePort(Protocol):
    """
    Port (interface) for layer lifecycle operations.
    
    This port defines the contract for managing layer lifecycle within FilterMate.
    Implementations must handle:
    - Layer validation and filtering
    - Layer addition with retry logic
    - PostgreSQL session cleanup
    - Project initialization support
    """
    
    @abstractmethod
    def filter_usable_layers(
        self,
        layers: List[Any],
        postgresql_available: bool = False
    ) -> List[Any]:
        """
        Filter and return only usable vector layers.
        
        Args:
            layers: List of layers to filter
            postgresql_available: Whether PostgreSQL backend is available
            
        Returns:
            List of usable layers
        """
        ...
    
    @abstractmethod
    def handle_layers_added(
        self,
        layers: List[Any],
        postgresql_available: bool,
        add_layers_callback: Callable,
        stability_constants: Dict[str, int]
    ) -> None:
        """
        Handle layer addition with validation and retry logic.
        
        Args:
            layers: Layers that were added
            postgresql_available: Whether PostgreSQL is available
            add_layers_callback: Callback to trigger add_layers task
            stability_constants: Timing constants for debouncing
        """
        ...
    
    @abstractmethod
    def cleanup_postgresql_session_views(
        self,
        session_id: str,
        temp_schema: str,
        project_layers: Dict[str, Any],
        postgresql_available: bool
    ) -> None:
        """
        Clean up PostgreSQL materialized views for a session.
        
        Args:
            session_id: Session ID for materialized view isolation
            temp_schema: PostgreSQL schema for temporary objects
            project_layers: Dictionary of project layers
            postgresql_available: Whether PostgreSQL backend is available
        """
        ...    
    @abstractmethod
    def cleanup(
        self,
        session_id: str,
        temp_schema: str,
        project_layers: Dict[str, Any],
        dockwidget: Any,
        auto_cleanup_enabled: bool,
        postgresql_available: bool
    ) -> None:
        """
        Clean up all plugin resources on unload or reload.
        
        Args:
            session_id: Session ID for cleanup
            temp_schema: PostgreSQL temp schema
            project_layers: Dictionary of layers to cleanup
            dockwidget: Reference to dockwidget for UI cleanup
            auto_cleanup_enabled: Whether PostgreSQL auto-cleanup is enabled
            postgresql_available: Whether PostgreSQL is available
        """
        ...
    
    @abstractmethod
    def force_reload_layers(
        self,
        cancel_tasks_callback: Callable,
        reset_flags_callback: Callable,
        init_db_callback: Callable,
        manage_task_callback: Callable,
        project_layers: Dict[str, Any],
        dockwidget: Any,
        stability_constants: Dict[str, int]
    ) -> None:
        """
        Force a complete reload of all layers in the current project.
        
        Args:
            cancel_tasks_callback: Callback to cancel all tasks
            reset_flags_callback: Callback to reset state flags
            init_db_callback: Callback to reinitialize database
            manage_task_callback: Callback to manage add_layers task
            project_layers: Dictionary to be cleared
            dockwidget: Reference to dockwidget for UI updates
            stability_constants: Timing constants dictionary
        """
        ...
    
    @abstractmethod
    def handle_remove_all_layers(
        self,
        cancel_tasks_callback: Callable,
        dockwidget: Any
    ) -> None:
        """
        Handle remove all layers event.
        
        Args:
            cancel_tasks_callback: Callback to cancel tasks
            dockwidget: Reference to dockwidget for UI cleanup
        """
        ...
    
    @abstractmethod
    def handle_project_initialization(
        self,
        task_name: str,
        is_initializing: bool,
        is_loading: bool,
        dockwidget: Any,
        check_reset_flags_callback: Callable,
        set_initializing_flag_callback: Callable,
        set_loading_flag_callback: Callable,
        cancel_tasks_callback: Callable,
        init_env_vars_callback: Callable,
        get_project_callback: Callable,
        init_db_callback: Callable,
        manage_task_callback: Callable,
        temp_schema: str,
        stability_constants: Dict[str, int]
    ) -> None:
        """
        Handle project read/new project initialization.
        
        Args:
            task_name: 'project_read' or 'new_project'
            is_initializing: Current initializing flag state
            is_loading: Current loading flag state
            dockwidget: Reference to dockwidget
            check_reset_flags_callback: Callback to check/reset stale flags
            set_initializing_flag_callback: Callback to set initializing flag
            set_loading_flag_callback: Callback to set loading flag
            cancel_tasks_callback: Callback to cancel tasks
            init_env_vars_callback: Callback to init environment variables
            get_project_callback: Callback to get current project
            init_db_callback: Callback to initialize database
            manage_task_callback: Callback to manage add_layers task
            temp_schema: PostgreSQL temp schema
            stability_constants: Timing constants dictionary
        """
        ...
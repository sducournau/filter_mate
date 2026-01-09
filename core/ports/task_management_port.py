# -*- coding: utf-8 -*-
"""
Task Management Port for FilterMate v4.0

Defines the interface for task management operations in the hexagonal architecture.
This port is implemented by TaskManagementService.

Author: FilterMate Team
Date: January 2026
"""
from typing import List, Any, Callable, Protocol
from abc import abstractmethod


class TaskManagementPort(Protocol):
    """
    Port (interface) for task management operations.
    
    This port defines the contract for managing asynchronous tasks in FilterMate.
    Implementations must handle:
    - Safe task cancellation
    - Layer-specific task cancellation
    - Queue processing for add_layers operations
    - Task counter management
    """
    
    @abstractmethod
    def safe_cancel_all_tasks(self) -> None:
        """Cancel all tasks safely to avoid access violations."""
        ...
    
    @abstractmethod
    def cancel_layer_tasks(self, layer_id: str, dockwidget: Any) -> None:
        """
        Cancel all running tasks for a specific layer.
        
        Args:
            layer_id: The ID of the layer whose tasks should be cancelled
            dockwidget: Dockwidget instance containing widgets with tasks
        """
        ...
    
    @abstractmethod
    def enqueue_add_layers(self, layers: List[Any]) -> bool:
        """
        Add layers to the processing queue.
        
        Args:
            layers: List of layers to add
            
        Returns:
            True if enqueued successfully, False if queue full
        """
        ...
    
    @abstractmethod
    def process_add_layers_queue(
        self,
        manage_task_callback: Callable[[str, List[Any]], None]
    ) -> None:
        """
        Process queued add_layers operations.
        
        Args:
            manage_task_callback: Callback to trigger task management
        """
        ...
    
    @abstractmethod
    def get_pending_tasks_count(self) -> int:
        """Get number of pending add_layers tasks."""
        ...
    
    @abstractmethod
    def get_queue_size(self) -> int:
        """Get current size of add_layers queue."""
        ...
    
    @abstractmethod
    def clear_queue(self) -> None:
        """Clear all queued add_layers operations."""
        ...

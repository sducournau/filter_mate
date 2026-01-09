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

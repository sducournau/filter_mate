# -*- coding: utf-8 -*-
"""
Base Backend Interface

Abstract base class defining the interface for geometric filtering backends.
All backend implementations must inherit from this class and implement its abstract methods.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from qgis.core import QgsVectorLayer


class GeometricFilterBackend(ABC):
    """
    Abstract base class for geometric filtering backends.
    
    Each backend is responsible for:
    1. Building filter expressions appropriate for its data source
    2. Applying filters to layers
    3. Verifying compatibility with specific layer types
    """
    
    def __init__(self, task_params: Dict):
        """
        Initialize the backend with task parameters.
        
        Args:
            task_params: Dictionary containing all task configuration parameters
        """
        self.task_params = task_params
        self.logger = None  # Will be set by subclasses
    
    @abstractmethod
    def build_expression(
        self, 
        layer_props: Dict, 
        predicates: Dict,
        source_geom: Optional[str] = None,
        buffer_value: Optional[float] = None,
        buffer_expression: Optional[str] = None
    ) -> str:
        """
        Build a filter expression for this backend.
        
        Args:
            layer_props: Layer properties dictionary containing layer metadata
            predicates: Dictionary of spatial predicates to apply
            source_geom: Source geometry for spatial filtering (optional)
            buffer_value: Buffer distance value (optional)
            buffer_expression: Expression for dynamic buffer (optional)
        
        Returns:
            Filter expression as a string suitable for this backend
        
        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement build_expression()")
    
    @abstractmethod
    def apply_filter(
        self, 
        layer: QgsVectorLayer, 
        expression: str,
        old_subset: Optional[str] = None,
        combine_operator: Optional[str] = None
    ) -> bool:
        """
        Apply the filter expression to the layer.
        
        Args:
            layer: QGIS vector layer to filter
            expression: Filter expression to apply
            old_subset: Existing subset string (optional)
            combine_operator: Operator to combine with existing filter (AND/OR)
        
        Returns:
            True if filter was applied successfully, False otherwise
        
        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement apply_filter()")
    
    @abstractmethod
    def supports_layer(self, layer: QgsVectorLayer) -> bool:
        """
        Check if this backend supports the given layer.
        
        Args:
            layer: QGIS vector layer to check
        
        Returns:
            True if this backend can handle the layer, False otherwise
        
        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement supports_layer()")
    
    def get_backend_name(self) -> str:
        """
        Get the human-readable name of this backend.
        
        Returns:
            Backend name as string
        """
        return self.__class__.__name__
    
    def log_info(self, message: str):
        """Helper method for logging info messages"""
        if self.logger:
            self.logger.info(f"[{self.get_backend_name()}] {message}")
    
    def log_warning(self, message: str):
        """Helper method for logging warning messages"""
        if self.logger:
            self.logger.warning(f"[{self.get_backend_name()}] {message}")
    
    def log_error(self, message: str):
        """Helper method for logging error messages"""
        if self.logger:
            self.logger.error(f"[{self.get_backend_name()}] {message}")
    
    def log_debug(self, message: str):
        """Helper method for logging debug messages"""
        if self.logger:
            self.logger.debug(f"[{self.get_backend_name()}] {message}")

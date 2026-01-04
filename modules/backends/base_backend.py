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
        buffer_expression: Optional[str] = None,
        source_filter: Optional[str] = None,
        use_centroids: bool = False,
        **kwargs
    ) -> str:
        """
        Build a filter expression for this backend.
        
        Args:
            layer_props: Layer properties dictionary containing layer metadata
            predicates: Dictionary of spatial predicates to apply
            source_geom: Source geometry for spatial filtering (optional)
            buffer_value: Buffer distance value (optional)
            source_filter: Source layer filter expression (optional, for EXISTS subqueries)
            buffer_expression: Expression for dynamic buffer (optional)
            use_centroids: If True, use centroids instead of full geometries for distant layers (optional)
            **kwargs: Additional backend-specific parameters (e.g., source_wkt, source_srid)
        
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

    # =========================================================================
    # Shared Buffer/Geometry Methods (v2.8.6 - extracted from backends)
    # =========================================================================
    
    def _get_buffer_endcap_style(self) -> str:
        """
        Get the buffer endcap style from task_params.
        
        Supports PostGIS/Spatialite ST_Buffer 'endcap' parameter:
        - 'round' (default)
        - 'flat' 
        - 'square'
        
        Returns:
            Endcap style string for SQL buffer functions
        """
        if not self.task_params:
            return 'round'
        
        filtering_params = self.task_params.get("filtering", {})
        if not filtering_params.get("has_buffer_type", False):
            return 'round'
        
        buffer_type_str = filtering_params.get("buffer_type", "Round")
        
        # Map FilterMate buffer types to SQL endcap styles
        buffer_type_mapping = {
            "Round": "round",
            "Flat": "flat", 
            "Square": "square"
        }
        
        endcap_style = buffer_type_mapping.get(buffer_type_str, "round")
        self.log_debug(f"Using buffer endcap style: {endcap_style}")
        return endcap_style
    
    def _get_buffer_segments(self) -> int:
        """
        Get the buffer segments (quad_segs) from task_params.
        
        Controls precision for curved buffer edges:
        - Higher value = smoother curves (more segments per quarter circle)
        - Lower value = faster but rougher curves
        - Default: 5 (if not using buffer_type options)
        
        Returns:
            Number of segments per quarter circle
        """
        if not self.task_params:
            return 5
        
        filtering_params = self.task_params.get("filtering", {})
        if not filtering_params.get("has_buffer_type", False):
            return 5
        
        segments = filtering_params.get("buffer_segments", 5)
        self.log_debug(f"Using buffer segments (quad_segs): {segments}")
        return int(segments)
    
    def _get_simplify_tolerance(self) -> float:
        """
        Get the geometry simplification tolerance from task_params.
        
        When simplify_tolerance > 0, geometries are simplified using
        SimplifyPreserveTopology before applying buffer. This reduces
        vertex count and improves performance for complex geometries.
        
        Notes:
        - Preserves topology (no self-intersections)
        - Tolerance in same units as geometry (meters for projected CRS)
        - Value of 0 means no simplification
        
        Returns:
            Simplification tolerance (0 = disabled)
        """
        if not self.task_params:
            return 0.0
        
        filtering_params = self.task_params.get("filtering", {})
        
        # Check if simplification is enabled
        if not filtering_params.get("has_simplify_tolerance", False):
            return 0.0
        
        tolerance = filtering_params.get("simplify_tolerance", 0.0)
        if tolerance and tolerance > 0:
            self.log_debug(f"Using geometry simplification tolerance: {tolerance}")
        return float(tolerance) if tolerance else 0.0
    
    def _is_task_canceled(self) -> bool:
        """
        Check if the parent task was canceled.
        
        Returns:
            True if task was canceled, False otherwise
        """
        if hasattr(self, 'task_params') and self.task_params:
            task = self.task_params.get('_parent_task')
            if task and hasattr(task, 'isCanceled'):
                return task.isCanceled()
        return False

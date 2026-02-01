# -*- coding: utf-8 -*-
"""
Abstract Filter Strategy - Base Interface.

Defines the abstract interface for all filter strategies in the unified filter system.
Part of the Unified Filter System (EPIC-UNIFIED-FILTER).

This module provides:
- FilterContext: Shared context for filter operations
- AbstractFilterStrategy: ABC defining the strategy contract

Concrete implementations:
- VectorFilterStrategy (vector_filter_strategy.py)
- RasterFilterStrategy (raster_filter_strategy.py)

Author: FilterMate Team (BMAD - Amelia)
Date: February 2026
Version: 5.0.0-alpha
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Callable, Any, Dict, Tuple
from enum import Enum

from ..domain.filter_criteria import (
    FilterCriteria,
    LayerType,
    UnifiedFilterCriteria
)


class FilterStatus(Enum):
    """Status of a filter operation."""
    SUCCESS = "success"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    ERROR = "error"
    NO_MATCHES = "no_matches"


@dataclass
class UnifiedFilterResult:
    """Unified result from filter operations.
    
    Compatible with both vector and raster filtering.
    
    Attributes:
        layer_id: ID of the processed layer
        layer_type: Type of layer (vector/raster)
        status: Operation status
        affected_count: Number of affected elements (features or pixels)
        expression_raw: Original expression/criteria used
        execution_time_ms: Execution time in milliseconds
        is_cached: Whether result was from cache
        error_message: Error message if status is ERROR
        backend_name: Name of backend that executed the filter
        
        # Vector-specific
        feature_ids: Set of matching feature IDs
        
        # Raster-specific
        pixel_count: Number of pixels in range
        pixel_percentage: Percentage of pixels matching
        statistics: Raster statistics (min, max, mean, etc.)
        output_path: Path to output raster if applicable
    """
    layer_id: str
    layer_type: str  # "vector" or "raster"
    status: FilterStatus = FilterStatus.SUCCESS
    affected_count: int = 0
    expression_raw: str = ""
    execution_time_ms: float = 0.0
    is_cached: bool = False
    error_message: Optional[str] = None
    backend_name: str = ""
    
    # Vector-specific
    feature_ids: Optional[frozenset] = None
    
    # Raster-specific
    pixel_count: int = 0
    pixel_percentage: float = 0.0
    statistics: Optional[Dict[str, Any]] = None
    output_path: Optional[str] = None
    
    @property
    def is_success(self) -> bool:
        """Check if operation was successful."""
        return self.status in (FilterStatus.SUCCESS, FilterStatus.NO_MATCHES)
    
    @property
    def is_vector(self) -> bool:
        """Check if this is a vector result."""
        return self.layer_type == "vector"
    
    @property
    def is_raster(self) -> bool:
        """Check if this is a raster result."""
        return self.layer_type == "raster"
    
    @classmethod
    def vector_success(
        cls,
        layer_id: str,
        feature_ids: frozenset,
        expression_raw: str = "",
        execution_time_ms: float = 0.0,
        backend_name: str = "",
        is_cached: bool = False
    ) -> 'UnifiedFilterResult':
        """Factory for successful vector filter result."""
        return cls(
            layer_id=layer_id,
            layer_type="vector",
            status=FilterStatus.SUCCESS if feature_ids else FilterStatus.NO_MATCHES,
            affected_count=len(feature_ids),
            expression_raw=expression_raw,
            execution_time_ms=execution_time_ms,
            backend_name=backend_name,
            is_cached=is_cached,
            feature_ids=feature_ids
        )
    
    @classmethod
    def raster_success(
        cls,
        layer_id: str,
        pixel_count: int,
        statistics: Dict[str, Any],
        expression_raw: str = "",
        execution_time_ms: float = 0.0,
        pixel_percentage: float = 0.0,
        output_path: Optional[str] = None
    ) -> 'UnifiedFilterResult':
        """Factory for successful raster filter result."""
        return cls(
            layer_id=layer_id,
            layer_type="raster",
            status=FilterStatus.SUCCESS if pixel_count > 0 else FilterStatus.NO_MATCHES,
            affected_count=pixel_count,
            expression_raw=expression_raw,
            execution_time_ms=execution_time_ms,
            pixel_count=pixel_count,
            pixel_percentage=pixel_percentage,
            statistics=statistics,
            output_path=output_path
        )
    
    @classmethod
    def error(
        cls,
        layer_id: str,
        layer_type: str,
        error_message: str,
        expression_raw: str = ""
    ) -> 'UnifiedFilterResult':
        """Factory for error result."""
        return cls(
            layer_id=layer_id,
            layer_type=layer_type,
            status=FilterStatus.ERROR,
            error_message=error_message,
            expression_raw=expression_raw
        )
    
    @classmethod
    def cancelled(
        cls,
        layer_id: str,
        layer_type: str,
        expression_raw: str = ""
    ) -> 'UnifiedFilterResult':
        """Factory for cancelled result."""
        return cls(
            layer_id=layer_id,
            layer_type=layer_type,
            status=FilterStatus.CANCELLED,
            expression_raw=expression_raw
        )


@dataclass
class FilterContext:
    """Shared context for filter execution.
    
    Contains dependencies and callbacks needed by all strategies.
    
    Attributes:
        project: QGIS project instance (or IProject abstraction)
        progress_callback: Callback for progress updates (percent, message)
        cancel_callback: Callback to check if operation should cancel
        use_cache: Whether to use result caching
        batch_mode: Whether running in batch mode (less UI feedback)
        dry_run: If True, don't actually apply filter (preview mode)
    """
    project: Any = None
    progress_callback: Optional[Callable[[int, str], None]] = None
    cancel_callback: Optional[Callable[[], bool]] = None
    use_cache: bool = True
    batch_mode: bool = False
    dry_run: bool = False
    
    def report_progress(self, percentage: int, message: str = "") -> None:
        """Report progress if callback is set.
        
        Args:
            percentage: Progress percentage (0-100)
            message: Optional status message
        """
        if self.progress_callback:
            self.progress_callback(percentage, message)
    
    def is_cancelled(self) -> bool:
        """Check if operation should be cancelled.
        
        Returns:
            True if cancel was requested
        """
        if self.cancel_callback:
            return self.cancel_callback()
        return False


class AbstractFilterStrategy(ABC):
    """Abstract base class for filter strategies.
    
    Implements the Strategy Pattern for unified handling of
    different layer types (vector, raster, future: mesh, point cloud).
    
    Each concrete strategy must implement:
    - supported_layer_type: The LayerType this strategy handles
    - validate_criteria: Validate criteria for this strategy
    - apply_filter: Execute the filter operation
    - get_preview: Get preview without applying
    - export: Export filtered data
    
    Usage:
        class MyStrategy(AbstractFilterStrategy):
            @property
            def supported_layer_type(self) -> LayerType:
                return LayerType.VECTOR
            
            def validate_criteria(self, criteria):
                # validation logic
                return True, ""
            
            def apply_filter(self, criteria):
                # filter logic
                return UnifiedFilterResult.vector_success(...)
            
            # ... other methods
    """
    
    def __init__(self, context: FilterContext):
        """Initialize strategy with shared context.
        
        Args:
            context: FilterContext with project and callbacks
        """
        self.context = context
        self._cancelled = False
    
    @property
    @abstractmethod
    def supported_layer_type(self) -> LayerType:
        """Return the LayerType this strategy handles.
        
        Returns:
            LayerType enum value (VECTOR, RASTER, etc.)
        """
        ...
    
    @abstractmethod
    def validate_criteria(
        self, 
        criteria: UnifiedFilterCriteria
    ) -> Tuple[bool, str]:
        """Validate filter criteria for this strategy.
        
        Args:
            criteria: Filter criteria to validate
            
        Returns:
            Tuple of (is_valid, error_message)
            error_message is empty string if valid
        """
        ...
    
    @abstractmethod
    def apply_filter(
        self, 
        criteria: UnifiedFilterCriteria
    ) -> UnifiedFilterResult:
        """Apply filter to the layer.
        
        This is the main filtering operation. It should:
        1. Validate criteria (or assume pre-validated)
        2. Execute the appropriate filtering logic
        3. Return unified result
        
        Args:
            criteria: Filter criteria defining what to filter
            
        Returns:
            UnifiedFilterResult with operation results
        """
        ...
    
    @abstractmethod
    def get_preview(
        self, 
        criteria: UnifiedFilterCriteria
    ) -> Dict[str, Any]:
        """Get preview of filter without applying.
        
        For vectors: estimated feature count
        For rasters: histogram, statistics preview
        
        Args:
            criteria: Filter criteria to preview
            
        Returns:
            Dict with preview data specific to layer type
        """
        ...
    
    @abstractmethod
    def export(
        self,
        criteria: UnifiedFilterCriteria,
        output_path: str,
        **export_options
    ) -> UnifiedFilterResult:
        """Export filtered data to file.
        
        Args:
            criteria: Filter criteria defining what to export
            output_path: Path for output file
            **export_options: Format-specific options
            
        Returns:
            UnifiedFilterResult with export status and output_path
        """
        ...
    
    # =========================================================================
    # Concrete helper methods (not abstract)
    # =========================================================================
    
    def cancel(self) -> None:
        """Request cancellation of current operation."""
        self._cancelled = True
    
    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation was requested.
        
        Checks both internal flag and context callback.
        
        Returns:
            True if operation should be cancelled
        """
        if self._cancelled:
            return True
        return self.context.is_cancelled()
    
    def _report_progress(self, percentage: int, message: str = "") -> None:
        """Report progress through context.
        
        Args:
            percentage: Progress percentage (0-100)
            message: Optional status message
        """
        self.context.report_progress(percentage, message)
    
    def _check_cancelled(self) -> bool:
        """Check cancellation and return status.
        
        Convenience method for use in loops.
        
        Returns:
            True if cancelled (operation should stop)
        """
        return self.is_cancelled
    
    def _create_error_result(
        self, 
        criteria: UnifiedFilterCriteria,
        error_message: str
    ) -> UnifiedFilterResult:
        """Create an error result for this strategy's layer type.
        
        Args:
            criteria: The criteria that failed
            error_message: Description of the error
            
        Returns:
            UnifiedFilterResult with ERROR status
        """
        return UnifiedFilterResult.error(
            layer_id=criteria.layer_id,
            layer_type=criteria.layer_type.value,
            error_message=error_message,
            expression_raw=criteria.to_display_string()
        )
    
    def _create_cancelled_result(
        self, 
        criteria: UnifiedFilterCriteria
    ) -> UnifiedFilterResult:
        """Create a cancelled result for this strategy's layer type.
        
        Args:
            criteria: The criteria that was cancelled
            
        Returns:
            UnifiedFilterResult with CANCELLED status
        """
        return UnifiedFilterResult.cancelled(
            layer_id=criteria.layer_id,
            layer_type=criteria.layer_type.value,
            expression_raw=criteria.to_display_string()
        )

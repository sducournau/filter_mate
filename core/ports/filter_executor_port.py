# -*- coding: utf-8 -*-
"""
Filter Executor Port Interface.

v4.0.1: Created to fix hexagonal architecture violations.
Provides abstract interface for filter execution, allowing
core/tasks/ to use backends without importing them directly.

This is a PURE PYTHON module with NO QGIS dependencies.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Protocol, Callable
from dataclasses import dataclass, field
from enum import Enum


class FilterStatus(Enum):
    """Status of a filter execution."""
    SUCCESS = "success"
    PARTIAL = "partial"  # Some layers filtered, some failed
    FAILED = "failed"
    CANCELLED = "cancelled"
    NO_RESULTS = "no_results"


@dataclass
class FilterExecutionResult:
    """
    Result of a filter execution operation.
    
    Attributes:
        status: Execution status
        feature_ids: List of matching feature IDs
        expression: Generated filter expression (if applicable)
        feature_count: Number of matched features
        execution_time_ms: Execution time in milliseconds
        backend_used: Name of backend that executed the filter
        error_message: Error message if status is FAILED
        warnings: List of warning messages
        metadata: Additional metadata from execution
    """
    status: FilterStatus
    feature_ids: List[int] = field(default_factory=list)
    expression: Optional[str] = None
    feature_count: int = 0
    execution_time_ms: float = 0.0
    backend_used: str = ""
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def success(cls, feature_ids: List[int], expression: str = None, 
                backend: str = "", execution_time: float = 0.0) -> 'FilterExecutionResult':
        """Create a successful result."""
        return cls(
            status=FilterStatus.SUCCESS,
            feature_ids=feature_ids,
            expression=expression,
            feature_count=len(feature_ids),
            execution_time_ms=execution_time,
            backend_used=backend
        )
    
    @classmethod
    def failed(cls, error: str, backend: str = "") -> 'FilterExecutionResult':
        """Create a failed result."""
        return cls(
            status=FilterStatus.FAILED,
            error_message=error,
            backend_used=backend
        )
    
    @classmethod
    def cancelled(cls) -> 'FilterExecutionResult':
        """Create a cancelled result."""
        return cls(status=FilterStatus.CANCELLED)
    
    @classmethod
    def no_results(cls, backend: str = "") -> 'FilterExecutionResult':
        """Create a no-results result."""
        return cls(status=FilterStatus.NO_RESULTS, backend_used=backend)


class FilterExecutorPort(ABC):
    """
    Abstract interface for filter execution.
    
    This port defines the contract for executing spatial and attribute
    filters. Concrete implementations are provided by adapters.
    
    Usage in core/:
        # Instead of:
        #   from adapters.backends.postgresql import PostgreSQLGeometricFilter
        #   backend = PostgreSQLGeometricFilter()
        
        # Use:
        #   executor: FilterExecutorPort = backend_registry.get_executor(layer)
        #   result = executor.execute_filter(params)
    """
    
    @abstractmethod
    def execute_filter(
        self,
        source_layer_info: Dict[str, Any],
        target_layers_info: List[Dict[str, Any]],
        expression: Optional[str] = None,
        predicates: Optional[Dict[str, str]] = None,
        buffer_value: float = 0.0,
        buffer_type: int = 0,
        use_centroids: bool = False,
        combine_operator: str = "AND",
        is_canceled_callback: Optional[Callable[[], bool]] = None,
    ) -> FilterExecutionResult:
        """
        Execute a filter operation.
        
        Args:
            source_layer_info: Source layer metadata dict
            target_layers_info: Target layers metadata list
            expression: Optional attribute filter expression
            predicates: Spatial predicates mapping {layer_id: predicate}
            buffer_value: Buffer distance (0 = no buffer)
            buffer_type: Buffer end cap style (0=round, 1=flat, 2=square)
            use_centroids: Use centroids instead of full geometries
            combine_operator: How to combine filters ("AND" or "OR")
            is_canceled_callback: Callback to check if operation is cancelled
            
        Returns:
            FilterExecutionResult with matched features or error
        """
    
    @abstractmethod
    def prepare_source_geometry(
        self,
        layer_info: Dict[str, Any],
        feature_ids: Optional[List[int]] = None,
        buffer_value: float = 0.0,
        use_centroids: bool = False,
    ) -> Tuple[Any, Optional[str]]:
        """
        Prepare source geometry for spatial filtering.
        
        Args:
            layer_info: Layer metadata dict
            feature_ids: Optional list of specific feature IDs
            buffer_value: Buffer to apply
            use_centroids: Use centroids
            
        Returns:
            Tuple of (geometry_data, error_message)
        """
    
    @abstractmethod
    def apply_subset_string(
        self,
        layer: Any,  # QgsVectorLayer - Any to avoid QGIS import
        expression: str
    ) -> bool:
        """
        Apply a subset string (filter) to a layer.
        
        Args:
            layer: QGIS vector layer
            expression: Filter expression
            
        Returns:
            True if applied successfully
        """
    
    @abstractmethod
    def cleanup_resources(self) -> None:
        """Clean up any temporary resources (MVs, temp tables, etc.)."""
    
    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Return the name of this backend."""
    
    @property
    @abstractmethod
    def supports_spatial_index(self) -> bool:
        """Return True if backend supports spatial indexing."""
    
    @property
    @abstractmethod
    def supports_materialized_views(self) -> bool:
        """Return True if backend supports materialized views."""


class BackendRegistryPort(ABC):
    """
    Abstract interface for backend registry.
    
    Provides backend selection based on layer type and capabilities.
    This allows core/ to get appropriate backends without knowing
    the concrete implementations.
    """
    
    @abstractmethod
    def get_executor(self, layer_info: Dict[str, Any]) -> FilterExecutorPort:
        """
        Get appropriate filter executor for a layer.
        
        Args:
            layer_info: Layer metadata including provider_type
            
        Returns:
            FilterExecutorPort implementation suitable for the layer
        """
    
    @abstractmethod
    def get_executor_by_name(self, backend_name: str) -> Optional[FilterExecutorPort]:
        """
        Get a specific backend by name.
        
        Args:
            backend_name: 'postgresql', 'spatialite', 'ogr', 'memory'
            
        Returns:
            FilterExecutorPort or None if not available
        """
    
    @abstractmethod
    def is_available(self, backend_name: str) -> bool:
        """Check if a specific backend is available."""
    
    @property
    @abstractmethod
    def postgresql_available(self) -> bool:
        """Return True if PostgreSQL backend is available."""


# Protocol for callbacks (type hints without runtime cost)
class CancellationCallback(Protocol):
    """Protocol for cancellation check callbacks."""
    def __call__(self) -> bool: ...


class ProgressCallback(Protocol):
    """Protocol for progress update callbacks."""
    def __call__(self, progress: float) -> None: ...

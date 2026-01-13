# -*- coding: utf-8 -*-
"""
Spatialite Filter Executor.

v4.0.1: Wrapper implementing FilterExecutorPort for Spatialite backend.
Delegates to existing SpatialiteBackend to avoid breaking changes.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple, Callable

from ....core.ports.filter_executor_port import (
    FilterExecutorPort,
    FilterExecutionResult,
    FilterStatus,
)
from .backend import SpatialiteBackend
from .filter_executor import (
    prepare_spatialite_source_geom,
    apply_spatialite_subset,
    cleanup_session_temp_tables,
)

logger = logging.getLogger('FilterMate')


class SpatialiteFilterExecutor(FilterExecutorPort):
    """
    FilterExecutorPort implementation for Spatialite/GeoPackage.
    
    Wraps existing SpatialiteBackend functionality to provide
    a clean interface for core/ without breaking existing code.
    """
    
    def __init__(self):
        """Initialize the Spatialite executor."""
        self._backend: Optional[SpatialiteBackend] = None
    
    def _get_backend(self) -> SpatialiteBackend:
        """Lazy initialization of backend."""
        if self._backend is None:
            from .backend import create_spatialite_backend
            self._backend = create_spatialite_backend()
        return self._backend
    
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
        Execute a filter operation using Spatialite.
        
        Delegates to existing SpatialiteBackend.execute() method.
        """
        import time
        start_time = time.time()
        
        try:
            backend = self._get_backend()
            
            # Check for cancellation
            if is_canceled_callback and is_canceled_callback():
                return FilterExecutionResult.cancelled()
            
            # Build filter parameters compatible with existing backend
            filter_params = {
                'expression': expression,
                'predicates': predicates or {},
                'buffer_value': buffer_value,
                'buffer_type': buffer_type,
                'use_centroids': use_centroids,
                'combine_operator': combine_operator,
            }
            
            # Execute via existing backend
            result = backend.execute(
                source_layer_info=source_layer_info,
                target_layer_infos=target_layers_info,
                **filter_params
            )
            
            execution_time = (time.time() - start_time) * 1000
            
            if result.success:
                return FilterExecutionResult.success(
                    feature_ids=result.feature_ids or [],
                    expression=result.expression,
                    backend='spatialite',
                    execution_time=execution_time
                )
            else:
                return FilterExecutionResult.failed(
                    error=result.error_message or "Unknown error",
                    backend='spatialite'
                )
                
        except Exception as e:
            logger.error(f"Spatialite filter execution failed: {e}")
            return FilterExecutionResult.failed(str(e), backend='spatialite')
    
    def prepare_source_geometry(
        self,
        layer_info: Dict[str, Any],
        feature_ids: Optional[List[int]] = None,
        buffer_value: float = 0.0,
        use_centroids: bool = False,
    ) -> Tuple[Any, Optional[str]]:
        """Prepare source geometry using existing function."""
        try:
            layer = layer_info.get('layer')
            if not layer:
                return None, "No layer provided"
            
            result = prepare_spatialite_source_geom(
                layer=layer,
                feature_ids=feature_ids,
                buffer_value=buffer_value,
                use_centroids=use_centroids
            )
            
            return result, None
            
        except Exception as e:
            logger.error(f"Spatialite geometry preparation failed: {e}")
            return None, str(e)
    
    def apply_subset_string(
        self,
        layer: Any,
        expression: str
    ) -> bool:
        """Apply subset string to layer."""
        try:
            return apply_spatialite_subset(layer, expression)
        except Exception as e:
            logger.error(f"Failed to apply Spatialite subset: {e}")
            return False
    
    def cleanup_resources(self) -> None:
        """Clean up temporary tables."""
        try:
            cleanup_session_temp_tables()
            logger.debug("Spatialite temp tables cleaned up")
        except Exception as e:
            logger.warning(f"Spatialite cleanup failed: {e}")
    
    @property
    def backend_name(self) -> str:
        return "spatialite"
    
    @property
    def supports_spatial_index(self) -> bool:
        return True  # R-tree support
    
    @property
    def supports_materialized_views(self) -> bool:
        return False  # Uses temp tables instead

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
            logger.error(f"[Spatialite] Spatialite filter execution failed: {e}")
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
            logger.error(f"[Spatialite] Spatialite geometry preparation failed: {e}")
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
            logger.error(f"[Spatialite] Failed to apply Spatialite subset: {e}")
            return False
    
    def cleanup_resources(self) -> None:
        """Clean up temporary tables."""
        try:
            cleanup_session_temp_tables()
            logger.debug(f"[Spatialite] Spatialite temp tables cleaned up")
        except Exception as e:
            logger.warning(f"[Spatialite] Spatialite cleanup failed: {e}")
    
    @property
    def backend_name(self) -> str:
        return "spatialite"
    
    @property
    def supports_spatial_index(self) -> bool:
        return True  # R-tree support
    
    @property
    def supports_materialized_views(self) -> bool:
        return False  # Uses temp tables instead
    
    # ========================================================================
    # v4.2.0: GeometricFilterBackend interface for legacy compatibility
    # ========================================================================
    
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
        Build Spatialite SQL filter expression.
        
        v4.2.0: Added for compatibility with legacy adapter after before_migration removal.
        """
        try:
            from .filter_executor import build_spatial_filter_expression
            
            return build_spatial_filter_expression(
                layer_props=layer_props,
                predicates=predicates,
                source_geom=source_geom,
                buffer_value=buffer_value,
                buffer_expression=buffer_expression,
                source_filter=source_filter,
                use_centroids=use_centroids,
                **kwargs
            )
        except Exception as e:
            logger.error(f"[Spatialite] build_expression failed: {e}")
            # Return empty to trigger QGIS Processing fallback
            return ""
    
    def apply_filter(
        self, 
        layer, 
        expression: str, 
        old_subset: Optional[str] = None, 
        combine_operator: Optional[str] = None
    ) -> bool:
        """
        Apply filter to Spatialite layer.
        
        v4.2.0: Added for compatibility with legacy adapter after before_migration removal.
        """
        # Combine expressions if needed
        final_expr = expression
        if old_subset and combine_operator:
            final_expr = f"({old_subset}) {combine_operator} ({expression})"
        elif old_subset:
            final_expr = f"({old_subset}) AND ({expression})"
        
        return self.apply_subset_string(layer, final_expr)
    
    def supports_layer(self, layer) -> bool:
        """Check if this backend supports the given layer."""
        provider = layer.providerType() if hasattr(layer, 'providerType') else None
        return provider in ('spatialite', 'ogr')  # Spatialite and GeoPackage

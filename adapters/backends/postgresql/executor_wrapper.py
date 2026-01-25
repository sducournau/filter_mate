# -*- coding: utf-8 -*-
"""
PostgreSQL Filter Executor.

v4.0.1: Wrapper implementing FilterExecutorPort for PostgreSQL backend.
Delegates to existing PostgreSQLBackend to avoid breaking changes.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple, Callable

from ....core.ports.filter_executor_port import (
    FilterExecutorPort,
    FilterExecutionResult,
    FilterStatus,
)

logger = logging.getLogger('FilterMate')


class PostgreSQLFilterExecutor(FilterExecutorPort):
    """
    FilterExecutorPort implementation for PostgreSQL/PostGIS.
    
    Wraps existing PostgreSQL backend functionality to provide
    a clean interface for core/ without breaking existing code.
    """
    
    def __init__(self):
        """Initialize the PostgreSQL executor."""
        self._backend = None
        self._available = False
        self._check_availability()
    
    def _check_availability(self):
        """Check if PostgreSQL is available."""
        try:
            from .postgresql_availability import POSTGRESQL_AVAILABLE
            self._available = POSTGRESQL_AVAILABLE
        except ImportError:
            self._available = False
    
    def _get_backend(self):
        """Lazy initialization of backend."""
        if self._backend is None and self._available:
            try:
                from .backend import PostgreSQLBackend
                self._backend = PostgreSQLBackend()
            except Exception as e:
                logger.warning(f"[PostgreSQL] Could not initialize PostgreSQL backend: {e}")
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
        Execute a filter operation using PostgreSQL.
        """
        import time
        start_time = time.time()
        
        if not self._available:
            return FilterExecutionResult.failed(
                "PostgreSQL not available (psycopg2 not installed)",
                backend='postgresql'
            )
        
        try:
            backend = self._get_backend()
            if not backend:
                return FilterExecutionResult.failed(
                    "PostgreSQL backend not initialized",
                    backend='postgresql'
                )
            
            # Check for cancellation
            if is_canceled_callback and is_canceled_callback():
                return FilterExecutionResult.cancelled()
            
            # Build filter parameters
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
                    backend='postgresql',
                    execution_time=execution_time
                )
            else:
                return FilterExecutionResult.failed(
                    error=result.error_message or "Unknown error",
                    backend='postgresql'
                )
                
        except Exception as e:
            logger.error(f"[PostgreSQL] PostgreSQL filter execution failed: {e}")
            return FilterExecutionResult.failed(str(e), backend='postgresql')
    
    def prepare_source_geometry(
        self,
        layer_info: Dict[str, Any],
        feature_ids: Optional[List[int]] = None,
        buffer_value: float = 0.0,
        use_centroids: bool = False,
    ) -> Tuple[Any, Optional[str]]:
        """Prepare source geometry using existing function."""
        try:
            from .filter_executor import prepare_postgresql_source_geom
            
            layer = layer_info.get('layer')
            if not layer:
                return None, "No layer provided"
            
            result = prepare_postgresql_source_geom(
                layer=layer,
                feature_ids=feature_ids,
                buffer_value=buffer_value,
                use_centroids=use_centroids
            )
            
            return result, None
            
        except Exception as e:
            logger.error(f"[PostgreSQL] PostgreSQL geometry preparation failed: {e}")
            return None, str(e)
    
    def apply_subset_string(
        self,
        layer: Any,
        expression: str
    ) -> bool:
        """Apply subset string to layer."""
        try:
            from ....infrastructure.database.sql_utils import safe_set_subset_string
            return safe_set_subset_string(layer, expression)
        except Exception as e:
            logger.error(f"[PostgreSQL] Failed to apply PostgreSQL subset: {e}")
            return False
    
    def cleanup_resources(self) -> None:
        """Clean up materialized views."""
        try:
            from .cleanup import cleanup_materialized_views
            cleanup_materialized_views()
            logger.debug(f"[PostgreSQL] PostgreSQL MVs cleaned up")
        except Exception as e:
            logger.warning(f"[PostgreSQL] PostgreSQL cleanup failed: {e}")
    
    @property
    def backend_name(self) -> str:
        return "postgresql"
    
    @property
    def supports_spatial_index(self) -> bool:
        return True  # GiST index
    
    @property
    def supports_materialized_views(self) -> bool:
        return True

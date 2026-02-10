# -*- coding: utf-8 -*-
"""
OGR Filter Executor.

v4.0.1: Wrapper implementing FilterExecutorPort for OGR backend.
Delegates to existing OGR backend to avoid breaking changes.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple, Callable

from ....core.ports.filter_executor_port import (
    FilterExecutorPort,
    FilterExecutionResult,
)

logger = logging.getLogger('FilterMate')


class OGRFilterExecutor(FilterExecutorPort):
    """
    FilterExecutorPort implementation for OGR (Shapefiles, etc.).

    Wraps existing OGR backend functionality to provide
    a clean interface for core/ without breaking existing code.
    OGR is the universal fallback backend.
    """

    def __init__(self):
        """Initialize the OGR executor."""
        self._backend = None

    def _get_backend(self):
        """Lazy initialization of backend."""
        if self._backend is None:
            try:
                from .backend import OGRBackend
                self._backend = OGRBackend()
            except (ImportError, RuntimeError) as e:
                logger.warning(f"[OGR] Could not initialize OGR backend: {e}")
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
        Execute a filter operation using OGR/QGIS processing.
        """
        import time
        start_time = time.time()

        try:
            backend = self._get_backend()
            if not backend:
                return FilterExecutionResult.failed(
                    "OGR backend not initialized",
                    backend='ogr'
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
                    backend='ogr',
                    execution_time=execution_time
                )
            else:
                return FilterExecutionResult.failed(
                    error=result.error_message or "Unknown error",
                    backend='ogr'
                )

        except (RuntimeError, AttributeError) as e:
            logger.error(f"[OGR] OGR filter execution failed: {e}")
            return FilterExecutionResult.failed(str(e), backend='ogr')
        except Exception as e:  # catch-all safety net
            logger.error(f"[OGR] OGR filter unexpected error: {e}")
            return FilterExecutionResult.failed(str(e), backend='ogr')

    def prepare_source_geometry(
        self,
        layer_info: Dict[str, Any],
        feature_ids: Optional[List[int]] = None,
        buffer_value: float = 0.0,
        use_centroids: bool = False,
    ) -> Tuple[Any, Optional[str]]:
        """Prepare source geometry using existing function."""
        try:
            from .filter_executor import prepare_ogr_source_geom

            layer = layer_info.get('layer')
            if not layer:
                return None, "No layer provided"

            result = prepare_ogr_source_geom(
                layer=layer,
                feature_ids=feature_ids,
                buffer_value=buffer_value,
                use_centroids=use_centroids
            )

            return result, None

        except (RuntimeError, AttributeError, ImportError) as e:
            logger.error(f"[OGR] OGR geometry preparation failed: {e}")
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
        except (RuntimeError, ImportError) as e:
            logger.error(f"[OGR] Failed to apply OGR subset: {e}")
            return False

    def cleanup_resources(self) -> None:
        """Clean up temporary memory layers."""
        try:
            from .filter_executor import cleanup_ogr_temp_layers
            cleanup_ogr_temp_layers()
            logger.debug("[OGR] OGR temp layers cleaned up")
        except (RuntimeError, ImportError) as e:
            logger.warning(f"[OGR] OGR cleanup failed: {e}")

    @property
    def backend_name(self) -> str:
        return "ogr"

    @property
    def supports_spatial_index(self) -> bool:
        return False  # No native spatial index

    @property
    def supports_materialized_views(self) -> bool:
        return False

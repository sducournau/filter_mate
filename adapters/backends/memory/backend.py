# -*- coding: utf-8 -*-
"""
FilterMate Memory Backend Implementation - ARCH-045

Lightweight backend for in-memory layers and testing.
Optimized for speed with small to medium datasets.

Part of Phase 4 Backend Refactoring.

Features:
- Fast in-memory filtering
- No external dependencies
- Ideal for temporary layers

Author: FilterMate Team
Date: January 2026
"""

import logging
import time
from typing import Optional, List, Dict, Any

from core.ports.backend_port import BackendPort, BackendInfo, BackendCapability
from core.domain.filter_expression import FilterExpression, ProviderType
from core.domain.filter_result import FilterResult
from core.domain.layer_info import LayerInfo

logger = logging.getLogger('FilterMate.Backend.Memory')


class MemoryBackend(BackendPort):
    """
    Memory backend for in-memory vector layers.

    Optimized for speed with small to medium datasets
    that fit entirely in memory.

    Example:
        backend = MemoryBackend()
        result = backend.execute(expression, layer_info)
    """

    # Maximum recommended features for memory backend
    MAX_RECOMMENDED_FEATURES = 50000

    def __init__(self):
        """Initialize Memory backend."""
        self._metrics = {
            'executions': 0,
            'features_processed': 0,
            'total_time_ms': 0.0,
            'errors': 0
        }

        logger.debug("Memory backend initialized")

    @property
    def metrics(self) -> Dict[str, Any]:
        """Get backend metrics."""
        return self._metrics.copy()

    def get_statistics(self) -> Dict[str, Any]:
        """Get backend execution statistics."""
        return self.metrics

    def reset_statistics(self) -> None:
        """Reset backend execution statistics."""
        self._metrics = {
            'executions': 0,
            'features_processed': 0,
            'total_time_ms': 0.0,
            'errors': 0
        }

    def execute(
        self,
        expression: FilterExpression,
        layer_info: LayerInfo,
        target_layer_infos: Optional[List[LayerInfo]] = None
    ) -> FilterResult:
        """
        Execute filter on memory layer.

        Args:
            expression: Filter expression
            layer_info: Source layer information
            target_layer_infos: Optional target layers

        Returns:
            FilterResult with matching feature IDs
        """
        start_time = time.time()
        self._metrics['executions'] += 1

        # Warn if layer is large
        if layer_info.feature_count > self.MAX_RECOMMENDED_FEATURES:
            logger.warning(
                f"Memory backend used for large layer ({layer_info.feature_count} features). "
                "Consider using PostgreSQL or Spatialite for better performance."
            )

        try:
            from qgis.core import (
                QgsProject, QgsExpression,
                QgsExpressionContext, QgsExpressionContextUtils
            )

            layer = QgsProject.instance().mapLayer(layer_info.layer_id)

            if not layer:
                return FilterResult.error(
                    layer_id=layer_info.layer_id,
                    expression_raw=expression.raw,
                    error_message="Layer not found",
                    backend_name=self.name
                )

            qgs_expr = QgsExpression(expression.raw)

            if qgs_expr.hasParserError():
                return FilterResult.error(
                    layer_id=layer_info.layer_id,
                    expression_raw=expression.raw,
                    error_message=qgs_expr.parserErrorString(),
                    backend_name=self.name
                )

            context = QgsExpressionContext()
            context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(layer))
            qgs_expr.prepare(context)

            # Memory layers are fast - iterate directly
            feature_ids: List[int] = []
            features_processed = 0

            for feature in layer.getFeatures():
                context.setFeature(feature)

                if qgs_expr.evaluate(context):
                    feature_ids.append(feature.id())

                features_processed += 1

            self._metrics['features_processed'] += features_processed
            execution_time = (time.time() - start_time) * 1000
            self._metrics['total_time_ms'] += execution_time

            return FilterResult.success(
                feature_ids=feature_ids,
                layer_id=layer_info.layer_id,
                expression_raw=expression.raw,
                execution_time_ms=execution_time,
                backend_name=self.name
            )

        except ImportError:
            self._metrics['errors'] += 1
            return FilterResult.error(
                layer_id=layer_info.layer_id,
                expression_raw=expression.raw,
                error_message="QGIS modules not available",
                backend_name=self.name
            )
        except Exception as e:
            self._metrics['errors'] += 1
            logger.exception(f"Memory filter failed: {e}")
            return FilterResult.error(
                layer_id=layer_info.layer_id,
                expression_raw=expression.raw,
                error_message=str(e),
                backend_name=self.name
            )

    def supports_layer(self, layer_info: LayerInfo) -> bool:
        """Check if backend supports layer."""
        return layer_info.provider_type == ProviderType.MEMORY

    def get_info(self) -> BackendInfo:
        """Get backend info."""
        return BackendInfo(
            name="Memory",
            version="1.0.0",
            capabilities=BackendCapability.SPATIAL_FILTER,
            priority=60,  # Medium priority
            max_features=self.MAX_RECOMMENDED_FEATURES,
            description="In-memory layer backend"
        )

    def cleanup(self) -> None:
        """No cleanup needed."""

    def estimate_execution_time(
        self,
        expression: FilterExpression,
        layer_info: LayerInfo
    ) -> float:
        """
        Estimate execution time.

        Memory is faster than OGR but still per-feature.
        """
        # 0.02ms per feature base
        base_time = layer_info.feature_count * 0.02

        if expression.is_spatial:
            base_time *= 1.5

        return base_time


def create_memory_backend() -> MemoryBackend:
    """
    Factory function for MemoryBackend.

    Returns:
        Configured MemoryBackend instance
    """
    return MemoryBackend()

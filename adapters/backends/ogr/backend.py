# -*- coding: utf-8 -*-
"""
FilterMate OGR Backend Implementation - ARCH-044

Universal fallback backend using QGIS expression evaluation.
Supports any vector format readable by OGR/GDAL.

Part of Phase 4 Backend Refactoring.

Features:
- Universal format support (Shapefile, GeoJSON, GeoPackage, etc.)
- QGIS expression evaluation
- Fallback for unsupported providers

Author: FilterMate Team
Date: January 2026
"""

import logging
import time
from typing import Optional, List, Dict, Any

from ....core.ports.backend_port import BackendPort, BackendInfo, BackendCapability
from ....core.domain.filter_expression import FilterExpression, ProviderType
from ....core.domain.filter_result import FilterResult
from ....core.domain.layer_info import LayerInfo

logger = logging.getLogger('FilterMate.Backend.OGR')


class OGRBackend(BackendPort):
    """
    OGR/GDAL backend for filter operations.

    This is the universal fallback backend that works with any
    vector format supported by OGR (Shapefile, GeoJSON, GeoPackage, etc.)

    Uses QGIS expression evaluation rather than native SQL,
    which is slower but more compatible.

    Example:
        backend = OGRBackend()
        result = backend.execute(expression, layer_info)
    """

    def __init__(
        self,
        batch_size: int = 1000,
        use_progress: bool = True
    ):
        """
        Initialize OGR backend.

        Args:
            batch_size: Features to process before progress update
            use_progress: Enable progress reporting
        """
        self._batch_size = batch_size
        self._use_progress = use_progress

        # Metrics
        self._metrics = {
            'executions': 0,
            'features_processed': 0,
            'total_time_ms': 0.0,
            'errors': 0
        }

        logger.info("OGR backend initialized")

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
        Execute filter using QGIS expression evaluation.

        This iterates through all features and evaluates the expression
        for each one. Slower than SQL but works with any format.

        Args:
            expression: Filter expression
            layer_info: Source layer information
            target_layer_infos: Optional target layers

        Returns:
            FilterResult with matching feature IDs
        """
        start_time = time.time()
        self._metrics['executions'] += 1

        try:
            # Import QGIS modules (may not be available in all contexts)
            from qgis.core import (
                QgsProject, QgsExpression,
                QgsExpressionContext, QgsExpressionContextUtils
            )

            # Get QGIS layer
            layer = QgsProject.instance().mapLayer(layer_info.layer_id)

            if not layer:
                return FilterResult.error(
                    layer_id=layer_info.layer_id,
                    expression_raw=expression.raw,
                    error_message=f"Layer not found: {layer_info.layer_id}",
                    backend_name=self.name
                )

            # Create expression
            qgs_expression = QgsExpression(expression.raw)

            if qgs_expression.hasParserError():
                return FilterResult.error(
                    layer_id=layer_info.layer_id,
                    expression_raw=expression.raw,
                    error_message=f"Expression error: {qgs_expression.parserErrorString()}",
                    backend_name=self.name
                )

            # Create context
            context = QgsExpressionContext()
            context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(layer))

            # Prepare expression
            qgs_expression.prepare(context)

            # Evaluate for each feature
            feature_ids: List[int] = []
            features_processed = 0

            for feature in layer.getFeatures():
                context.setFeature(feature)

                result = qgs_expression.evaluate(context)

                # Handle evaluation errors
                if qgs_expression.hasEvalError():
                    logger.warning(
                        f"Expression eval error on feature {feature.id()}: "
                        f"{qgs_expression.evalErrorString()}"
                    )
                    continue

                if result:
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
            logger.exception(f"OGR filter execution failed: {e}")
            return FilterResult.error(
                layer_id=layer_info.layer_id,
                expression_raw=expression.raw,
                error_message=str(e),
                backend_name=self.name
            )

    def supports_layer(self, layer_info: LayerInfo) -> bool:
        """
        OGR supports any layer type as fallback.

        Returns True for OGR, Memory, and Unknown provider types.
        """
        return layer_info.provider_type in (
            ProviderType.OGR,
            ProviderType.MEMORY,
            ProviderType.UNKNOWN
        )

    def get_info(self) -> BackendInfo:
        """Get backend information."""
        return BackendInfo(
            name="OGR",
            version="1.0.0",
            capabilities=(
                BackendCapability.SPATIAL_FILTER |
                BackendCapability.BUFFER_OPERATIONS
            ),
            priority=50,  # Lower priority, used as fallback
            max_features=100000,
            description="Universal OGR backend using QGIS expressions"
        )

    def cleanup(self) -> None:
        """No cleanup needed for OGR backend."""

    def estimate_execution_time(
        self,
        expression: FilterExpression,
        layer_info: LayerInfo
    ) -> float:
        """
        Estimate execution time.

        OGR is slowest as it evaluates each feature individually.
        """
        # Base estimate: 0.1ms per feature
        base_time = layer_info.feature_count * 0.1

        # Spatial expressions are slower
        if expression.is_spatial:
            base_time *= 2.0

        return base_time

    def validate_expression(
        self,
        expression: FilterExpression
    ) -> List[str]:
        """
        Validate expression syntax.

        Args:
            expression: Expression to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors: List[str] = []

        try:
            from qgis.core import QgsExpression

            qgs_expr = QgsExpression(expression.raw)
            if qgs_expr.hasParserError():
                errors.append(qgs_expr.parserErrorString())

        except ImportError:
            errors.append("QGIS modules not available for validation")
        except Exception as e:
            errors.append(str(e))

        return errors


def create_ogr_backend(
    batch_size: int = 1000,
    use_progress: bool = True
) -> OGRBackend:
    """
    Factory function for OGRBackend.

    Args:
        batch_size: Features per progress update
        use_progress: Enable progress

    Returns:
        Configured OGRBackend instance
    """
    return OGRBackend(
        batch_size=batch_size,
        use_progress=use_progress
    )

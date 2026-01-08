# -*- coding: utf-8 -*-
"""
FilterMate Layer Task - ARCH-047

Async tasks for layer operations.
Handles layer loading, validation, and management.

Part of Phase 4 Task Refactoring.

Features:
- Layer information gathering
- Layer validation
- Bulk layer operations

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Optional, List, Dict, Any, Callable

from .base_task import BaseFilterMateTask, TaskResult

logger = logging.getLogger('FilterMate.Tasks.Layer')


class GatherLayerInfoTask(BaseFilterMateTask):
    """
    Async task for gathering layer information.

    Collects metadata about multiple layers efficiently.
    """

    def __init__(
        self,
        layer_ids: List[str],
        include_feature_count: bool = True,
        include_extent: bool = False,
        on_complete: Optional[Callable[[TaskResult], None]] = None,
        on_error: Optional[Callable[[TaskResult], None]] = None
    ):
        """
        Initialize layer info task.

        Args:
            layer_ids: Layer IDs to gather info for
            include_feature_count: Calculate feature count
            include_extent: Calculate extent
            on_complete: Success callback
            on_error: Error callback
        """
        super().__init__(
            description=f"Gathering info for {len(layer_ids)} layers",
            on_complete=on_complete,
            on_error=on_error
        )

        self._layer_ids = layer_ids
        self._include_feature_count = include_feature_count
        self._include_extent = include_extent
        self._layer_infos: Dict[str, Dict[str, Any]] = {}

    def _execute(self) -> TaskResult:
        """Gather layer information."""
        try:
            from qgis.core import QgsProject, QgsVectorLayer

            total = len(self._layer_ids)

            for i, layer_id in enumerate(self._layer_ids):
                if self.check_cancelled():
                    return TaskResult.cancelled_result()

                layer = QgsProject.instance().mapLayer(layer_id)

                if not layer:
                    self._layer_infos[layer_id] = {
                        'valid': False,
                        'error': 'Layer not found'
                    }
                    continue

                info = {
                    'valid': layer.isValid(),
                    'name': layer.name(),
                    'provider': layer.providerType(),
                    'source': layer.source(),
                    'crs': layer.crs().authid() if layer.crs() else None,
                }

                if isinstance(layer, QgsVectorLayer):
                    info['is_vector'] = True
                    info['geometry_type'] = layer.geometryType()
                    info['wkb_type'] = layer.wkbType()

                    if self._include_feature_count:
                        info['feature_count'] = layer.featureCount()

                    if self._include_extent:
                        extent = layer.extent()
                        info['extent'] = {
                            'xmin': extent.xMinimum(),
                            'ymin': extent.yMinimum(),
                            'xmax': extent.xMaximum(),
                            'ymax': extent.yMaximum()
                        }

                    # Get fields
                    info['fields'] = [
                        {'name': f.name(), 'type': f.typeName()}
                        for f in layer.fields()
                    ]

                    # Check for spatial index
                    info['has_spatial_index'] = layer.hasSpatialIndex() == 2  # QgsFeatureSource.SpatialIndexPresent

                else:
                    info['is_vector'] = False

                self._layer_infos[layer_id] = info
                self.report_progress(i + 1, total)

            return TaskResult.success_result(
                data={'layer_infos': self._layer_infos},
                metrics={'layers_processed': len(self._layer_infos)}
            )

        except Exception as e:
            logger.exception(f"Layer info gathering failed: {e}")
            return TaskResult.error_result(str(e))

    @property
    def layer_infos(self) -> Dict[str, Dict[str, Any]]:
        """Get gathered layer information."""
        return self._layer_infos


class ValidateExpressionsTask(BaseFilterMateTask):
    """
    Async task for validating expressions on layers.

    Checks if expressions are valid for given layers.
    """

    def __init__(
        self,
        validations: List[tuple],  # List of (layer_id, expression_str) tuples
        on_complete: Optional[Callable[[TaskResult], None]] = None,
        on_error: Optional[Callable[[TaskResult], None]] = None
    ):
        """
        Initialize validation task.

        Args:
            validations: List of (layer_id, expression_str) tuples
            on_complete: Success callback
            on_error: Error callback
        """
        super().__init__(
            description=f"Validating {len(validations)} expressions",
            on_complete=on_complete,
            on_error=on_error
        )

        self._validations = validations
        self._results: Dict[str, Dict[str, Any]] = {}

    def _execute(self) -> TaskResult:
        """Validate expressions."""
        try:
            from qgis.core import (
                QgsProject, QgsVectorLayer, QgsExpression,
                QgsExpressionContext, QgsExpressionContextUtils
            )

            total = len(self._validations)
            valid_count = 0
            invalid_count = 0

            for i, (layer_id, expression_str) in enumerate(self._validations):
                if self.check_cancelled():
                    return TaskResult.cancelled_result()

                layer = QgsProject.instance().mapLayer(layer_id)

                if not isinstance(layer, QgsVectorLayer):
                    self._results[f"{layer_id}:{expression_str}"] = {
                        'valid': False,
                        'error': 'Layer not found or not a vector layer'
                    }
                    invalid_count += 1
                    continue

                # Create expression
                expr = QgsExpression(expression_str)

                if expr.hasParserError():
                    self._results[f"{layer_id}:{expression_str}"] = {
                        'valid': False,
                        'error': expr.parserErrorString()
                    }
                    invalid_count += 1
                else:
                    # Prepare with layer context to check field references
                    context = QgsExpressionContext()
                    context.appendScopes(
                        QgsExpressionContextUtils.globalProjectLayerScopes(layer)
                    )
                    expr.prepare(context)

                    if expr.hasEvalError():
                        self._results[f"{layer_id}:{expression_str}"] = {
                            'valid': False,
                            'error': expr.evalErrorString()
                        }
                        invalid_count += 1
                    else:
                        self._results[f"{layer_id}:{expression_str}"] = {
                            'valid': True,
                            'referenced_columns': list(expr.referencedColumns())
                        }
                        valid_count += 1

                self.report_progress(i + 1, total)

            return TaskResult.success_result(
                data={
                    'results': self._results,
                    'valid_count': valid_count,
                    'invalid_count': invalid_count
                },
                metrics={
                    'expressions_validated': total,
                    'valid': valid_count,
                    'invalid': invalid_count
                }
            )

        except Exception as e:
            logger.exception(f"Expression validation failed: {e}")
            return TaskResult.error_result(str(e))


class CreateSpatialIndexTask(BaseFilterMateTask):
    """
    Async task for creating spatial indexes.

    Creates spatial indexes for layers that don't have them.
    """

    def __init__(
        self,
        layer_ids: List[str],
        on_complete: Optional[Callable[[TaskResult], None]] = None,
        on_error: Optional[Callable[[TaskResult], None]] = None
    ):
        """
        Initialize spatial index task.

        Args:
            layer_ids: Layer IDs to create indexes for
            on_complete: Success callback
            on_error: Error callback
        """
        super().__init__(
            description=f"Creating spatial indexes for {len(layer_ids)} layers",
            on_complete=on_complete,
            on_error=on_error
        )

        self._layer_ids = layer_ids
        self._created = 0
        self._skipped = 0
        self._failed = 0

    def _execute(self) -> TaskResult:
        """Create spatial indexes."""
        try:
            from qgis.core import QgsProject, QgsVectorLayer
            from qgis import processing

            total = len(self._layer_ids)

            for i, layer_id in enumerate(self._layer_ids):
                if self.check_cancelled():
                    return TaskResult.cancelled_result()

                layer = QgsProject.instance().mapLayer(layer_id)

                if not isinstance(layer, QgsVectorLayer):
                    self._failed += 1
                    continue

                # Check if already has spatial index
                if layer.hasSpatialIndex() == 2:  # SpatialIndexPresent
                    self._skipped += 1
                    continue

                try:
                    # Create spatial index using processing
                    processing.run("native:createspatialindex", {
                        'INPUT': layer
                    })
                    self._created += 1
                except Exception as e:
                    logger.warning(f"Failed to create index for {layer.name()}: {e}")
                    self._failed += 1

                self.report_progress(i + 1, total)

            return TaskResult.success_result(
                data={
                    'created': self._created,
                    'skipped': self._skipped,
                    'failed': self._failed
                },
                metrics={
                    'indexes_created': self._created
                }
            )

        except Exception as e:
            logger.exception(f"Spatial index creation failed: {e}")
            return TaskResult.error_result(str(e))

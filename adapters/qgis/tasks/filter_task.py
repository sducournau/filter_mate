# -*- coding: utf-8 -*-
"""
FilterMate Filter Task - ARCH-047

Async task for executing filter operations.
Focused, single-responsibility task class.

Part of Phase 4 Task Refactoring.

Features:
- Multi-layer filtering
- Progress reporting
- Result aggregation
- Layer application

Author: FilterMate Team
Date: January 2026
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional, List, Dict, Callable

from .base_task import BaseFilterMateTask, TaskResult, TaskStatus

if TYPE_CHECKING:
    from ....core.domain.filter_expression import FilterExpression
    from ....core.domain.filter_result import FilterResult
    from ....core.domain.layer_info import LayerInfo
    from ....core.services.filter_service import FilterService
    from ....core.ports.backend_port import BackendPort

logger = logging.getLogger('FilterMate.Tasks.Filter')


class FilterTask(BaseFilterMateTask):
    """
    Async task for filter execution.

    Executes filter expressions against source layers and
    applies results to target layers.

    Example:
        task = FilterTask(
            expression=expression,
            source_layer_info=source,
            target_layer_infos=[target1, target2],
            filter_service=service
        )
        QgsApplication.taskManager().addTask(task)
    """

    def __init__(
        self,
        expression: 'FilterExpression',
        source_layer_info: 'LayerInfo',
        target_layer_infos: List['LayerInfo'],
        filter_service: Optional['FilterService'] = None,
        backend: Optional['BackendPort'] = None,
        apply_to_layers: bool = True,
        on_complete: Optional[Callable[[TaskResult], None]] = None,
        on_error: Optional[Callable[[TaskResult], None]] = None,
        on_progress: Optional[Callable[[int, str], None]] = None
    ):
        """
        Initialize filter task.

        Args:
            expression: Filter expression to execute
            source_layer_info: Source layer info
            target_layer_infos: Target layers to filter
            filter_service: FilterService for execution (optional)
            backend: Backend to use directly (alternative to service)
            apply_to_layers: Whether to apply filter to layers
            on_complete: Success callback
            on_error: Error callback
            on_progress: Progress callback
        """
        super().__init__(
            description=f"Filtering {len(target_layer_infos)} layers",
            on_complete=on_complete,
            on_error=on_error,
            on_progress=on_progress
        )

        self._expression = expression
        self._source_layer = source_layer_info
        self._target_layers = target_layer_infos
        self._filter_service = filter_service
        self._backend = backend
        self._apply_to_layers = apply_to_layers
        self._results: Dict[str, 'FilterResult'] = {}

    def _execute(self) -> TaskResult:
        """Execute filter operation."""
        from ....core.domain.filter_result import FilterResult

        total = len(self._target_layers)
        successful = 0
        failed = 0

        for i, target in enumerate(self._target_layers):
            if self.check_cancelled():
                return TaskResult.cancelled_result()

            self.report_progress(i, total, f"Filtering {target.name}")

            try:
                # Execute filter
                if self._filter_service:
                    result = self._filter_via_service(target)
                elif self._backend:
                    result = self._filter_via_backend(target)
                else:
                    result = FilterResult.error(
                        layer_id=target.layer_id,
                        expression_raw=self._expression.raw,
                        error_message="No filter service or backend provided"
                    )

                self._results[target.layer_id] = result

                # Apply to layer if requested
                if self._apply_to_layers and result.is_success:
                    self._apply_filter_to_layer(target.layer_id, result)
                    successful += 1
                elif not result.is_success:
                    failed += 1
                    logger.warning(
                        f"Filter failed for {target.name}: {result.error_message}"
                    )

            except Exception as e:
                logger.error(f"Failed to filter {target.name}: {e}")
                self._results[target.layer_id] = FilterResult.error(
                    layer_id=target.layer_id,
                    expression_raw=self._expression.raw,
                    error_message=str(e)
                )
                failed += 1

        self.report_progress(total, total, "Complete")

        # Calculate totals
        total_matches = sum(
            len(r.feature_ids) for r in self._results.values() if r.is_success
        )

        # Determine overall success
        all_success = failed == 0

        return TaskResult(
            success=all_success,
            status=TaskStatus.COMPLETED if all_success else TaskStatus.FAILED,
            data={
                'results': self._results,
                'total_matches': total_matches,
                'successful_layers': successful,
                'failed_layers': failed
            },
            metrics={
                'layers_processed': total,
                'total_matches': total_matches
            }
        )

    def _filter_via_service(self, target: 'LayerInfo') -> 'FilterResult':
        """Execute filter using FilterService."""
        # FilterService provides full orchestration
        return self._filter_service.filter_layer(
            expression=self._expression,
            source_layer_info=self._source_layer,
            target_layer_info=target,
            use_cache=True
        )

    def _filter_via_backend(self, target: 'LayerInfo') -> 'FilterResult':
        """Execute filter using backend directly."""
        return self._backend.execute(
            expression=self._expression,
            layer_info=target
        )

    def _apply_filter_to_layer(
        self,
        layer_id: str,
        result: 'FilterResult'
    ) -> None:
        """Apply filter result to QGIS layer."""
        try:
            from qgis.core import QgsProject, QgsVectorLayer

            layer = QgsProject.instance().mapLayer(layer_id)
            if not isinstance(layer, QgsVectorLayer):
                return

            if len(result.feature_ids) == 0:
                # No matches - set impossible filter
                layer.setSubsetString("1=0")
            else:
                # Build feature ID filter
                ids = ','.join(str(fid) for fid in result.feature_ids)
                pk = self._get_pk_field(layer)
                layer.setSubsetString(f'"{pk}" IN ({ids})')

            layer.triggerRepaint()

        except Exception as e:
            logger.warning(f"Failed to apply filter to layer {layer_id}: {e}")

    def _get_pk_field(self, layer) -> str:
        """Get primary key field name."""
        try:
            pk_attrs = layer.primaryKeyAttributes()
            if pk_attrs:
                return layer.fields()[pk_attrs[0]].name()
        except Exception:
            pass
        return "fid"

    def _on_completed(self, result: TaskResult) -> None:
        """Handle completion."""
        data = result.data or {}
        logger.info(
            f"Filter completed: {data.get('total_matches', 0)} total matches "
            f"across {data.get('successful_layers', 0)} layers"
        )

    @property
    def results(self) -> Dict[str, 'FilterResult']:
        """Get filter results by layer ID."""
        return self._results


class ClearFilterTask(BaseFilterMateTask):
    """
    Async task for clearing filters from layers.

    Removes subset strings from target layers.
    """

    def __init__(
        self,
        layer_ids: List[str],
        on_complete: Optional[Callable[[TaskResult], None]] = None,
        on_error: Optional[Callable[[TaskResult], None]] = None
    ):
        """
        Initialize clear filter task.

        Args:
            layer_ids: Layer IDs to clear filters from
            on_complete: Success callback
            on_error: Error callback
        """
        super().__init__(
            description=f"Clearing filters from {len(layer_ids)} layers",
            on_complete=on_complete,
            on_error=on_error
        )

        self._layer_ids = layer_ids
        self._cleared = 0

    def _execute(self) -> TaskResult:
        """Clear filters from layers."""
        try:
            from qgis.core import QgsProject, QgsVectorLayer

            total = len(self._layer_ids)

            for i, layer_id in enumerate(self._layer_ids):
                if self.check_cancelled():
                    return TaskResult.cancelled_result()

                layer = QgsProject.instance().mapLayer(layer_id)
                if isinstance(layer, QgsVectorLayer):
                    layer.setSubsetString("")
                    layer.triggerRepaint()
                    self._cleared += 1

                self.report_progress(i + 1, total)

            return TaskResult.success_result(
                data={'cleared': self._cleared},
                metrics={'layers_cleared': self._cleared}
            )

        except Exception as e:
            logger.exception(f"Clear filters failed: {e}")
            return TaskResult.error_result(str(e))

    @property
    def cleared_count(self) -> int:
        """Get number of layers cleared."""
        return self._cleared

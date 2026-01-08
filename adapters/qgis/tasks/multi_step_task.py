# -*- coding: utf-8 -*-
"""
FilterMate Multi-Step Filter Task - ARCH-047

Async task for multi-step filtering operations.
Orchestrates progressive filtering using the filter optimizer port.

Part of Phase 4 Task Refactoring.

Features:
- Multi-step progressive filtering
- Strategy selection based on data size
- Progress reporting per step
- Memory-efficient for large datasets

Author: FilterMate Team
Date: January 2026
"""

import logging
import time
from typing import Optional, List, Dict, Callable, Any

from .base_task import BaseFilterMateTask, TaskResult, TaskStatus

logger = logging.getLogger('FilterMate.Tasks.MultiStep')


class MultiStepFilterTask(BaseFilterMateTask):
    """
    Async task for multi-step filter execution.

    Executes multi-step filtering using adaptive strategies:
    - ATTRIBUTE_FIRST: Apply attribute filter before geometry
    - BBOX_THEN_FULL: Bounding box pre-filter then full predicate
    - PROGRESSIVE: Chunked filtering for very large datasets

    Example:
        task = MultiStepFilterTask(
            source_layer_info=source,
            target_layer_info=target,
            attribute_expression="status = 'active'",
            spatial_expression="ST_Intersects(...)",
            filter_optimizer=optimizer
        )
        QgsApplication.taskManager().addTask(task)
    """

    def __init__(
        self,
        source_layer_info: 'LayerInfo',
        target_layer_info: 'LayerInfo',
        attribute_expression: Optional[str] = None,
        spatial_expression: Optional[str] = None,
        source_bbox: Optional[tuple] = None,
        filter_optimizer: Optional['IFilterOptimizer'] = None,
        apply_to_layer: bool = True,
        max_candidates: int = 100000,
        on_complete: Optional[Callable[[TaskResult], None]] = None,
        on_error: Optional[Callable[[TaskResult], None]] = None,
        on_progress: Optional[Callable[[int, str], None]] = None,
        on_step_complete: Optional[Callable[[int, str, int], None]] = None
    ):
        """
        Initialize multi-step filter task.

        Args:
            source_layer_info: Source layer info
            target_layer_info: Target layer info
            attribute_expression: Attribute filter expression
            spatial_expression: Spatial filter expression
            source_bbox: Source bounding box (xmin, ymin, xmax, ymax)
            filter_optimizer: Filter optimizer port instance
            apply_to_layer: Whether to apply result to layer
            max_candidates: Maximum candidates per step
            on_complete: Success callback
            on_error: Error callback
            on_progress: Progress callback
            on_step_complete: Callback when each step completes
        """
        super().__init__(
            description=f"Multi-step filter on {target_layer_info.name}",
            on_complete=on_complete,
            on_error=on_error,
            on_progress=on_progress
        )

        self._source_layer = source_layer_info
        self._target_layer = target_layer_info
        self._attribute_expr = attribute_expression
        self._spatial_expr = spatial_expression
        self._source_bbox = source_bbox
        self._filter_optimizer = filter_optimizer
        self._apply_to_layer = apply_to_layer
        self._max_candidates = max_candidates
        self._on_step_complete = on_step_complete

        # Execution state
        self._steps_executed: List[Dict[str, Any]] = []
        self._current_candidates: int = 0
        self._final_feature_ids: List[int] = []

    def _execute(self) -> TaskResult:
        """Execute multi-step filter."""
        start_time = time.time()

        try:
            # Phase 1: Build filter plan
            self.report_progress(0, 100, "Building filter plan...")
            plan = self._build_filter_plan()

            if not plan or not plan.steps:
                # Fallback to direct filter
                return self._execute_direct_filter()

            # Phase 2: Execute plan steps
            total_steps = len(plan.steps)
            candidates = None

            for i, step in enumerate(plan.steps):
                if self.check_cancelled():
                    return TaskResult.cancelled_result()

                progress = int((i / total_steps) * 80) + 10
                self.report_progress(
                    progress, 100,
                    f"Step {i+1}/{total_steps}: {step.step_type.value}"
                )

                step_result = self._execute_step(step, candidates)
                self._steps_executed.append({
                    'step_type': step.step_type.value,
                    'candidates_before': candidates if candidates else 'all',
                    'candidates_after': step_result.get('count', 0),
                    'time_ms': step_result.get('time_ms', 0)
                })

                candidates = step_result.get('feature_ids', [])
                self._current_candidates = len(candidates) if candidates else 0

                # Notify step completion
                if self._on_step_complete:
                    try:
                        self._on_step_complete(
                            i + 1,
                            step.step_type.value,
                            self._current_candidates
                        )
                    except Exception:
                        pass

                # Early termination if no candidates
                if candidates is not None and len(candidates) == 0:
                    logger.info("Multi-step filter: No candidates after step %d", i + 1)
                    break

            self._final_feature_ids = candidates or []

            # Phase 3: Apply to layer
            if self._apply_to_layer:
                self.report_progress(90, 100, "Applying filter to layer...")
                self._apply_filter_result()

            self.report_progress(100, 100, "Complete")

            execution_time = (time.time() - start_time) * 1000

            return TaskResult.success_result(
                data={
                    'feature_ids': self._final_feature_ids,
                    'feature_count': len(self._final_feature_ids),
                    'steps_executed': self._steps_executed,
                    'strategy': plan.strategy.value if hasattr(plan, 'strategy') else 'multi_step'
                },
                execution_time_ms=execution_time,
                metrics={
                    'steps': len(self._steps_executed),
                    'final_count': len(self._final_feature_ids),
                    'reduction_ratio': self._calculate_reduction_ratio()
                }
            )

        except Exception as e:
            logger.exception(f"Multi-step filter failed: {e}")
            execution_time = (time.time() - start_time) * 1000
            return TaskResult.error_result(str(e), execution_time)

    def _build_filter_plan(self) -> Optional['FilterPlan']:
        """Build filter execution plan."""
        if not self._filter_optimizer:
            return None

        try:
            return self._filter_optimizer.create_optimal_plan(
                attribute_expression=self._attribute_expr,
                spatial_expression=self._spatial_expr,
                source_bbox=self._source_bbox,
                estimated_feature_count=getattr(
                    self._target_layer, 'feature_count', 0
                )
            )
        except Exception as e:
            logger.warning(f"Failed to build filter plan: {e}")
            return None

    def _execute_step(
        self,
        step: 'FilterStep',
        current_candidates: Optional[List[int]]
    ) -> Dict[str, Any]:
        """Execute a single filter step."""
        start = time.time()

        try:
            if self._filter_optimizer:
                result = self._filter_optimizer.execute_step(
                    step=step,
                    candidates=current_candidates,
                    layer_info=self._target_layer
                )
                return {
                    'feature_ids': result.feature_ids if hasattr(result, 'feature_ids') else [],
                    'count': result.count if hasattr(result, 'count') else 0,
                    'time_ms': (time.time() - start) * 1000
                }
            else:
                # Fallback: no optimizer
                return {
                    'feature_ids': current_candidates or [],
                    'count': len(current_candidates) if current_candidates else 0,
                    'time_ms': (time.time() - start) * 1000
                }

        except Exception as e:
            logger.warning(f"Step execution failed: {e}")
            return {
                'feature_ids': current_candidates or [],
                'count': len(current_candidates) if current_candidates else 0,
                'time_ms': (time.time() - start) * 1000,
                'error': str(e)
            }

    def _execute_direct_filter(self) -> TaskResult:
        """Execute direct filter without optimizer."""
        start_time = time.time()

        try:
            from qgis.core import QgsProject, QgsVectorLayer

            layer = QgsProject.instance().mapLayer(self._target_layer.layer_id)
            if not isinstance(layer, QgsVectorLayer):
                return TaskResult.error_result("Layer not found")

            # Build combined expression
            expression_parts = []
            if self._attribute_expr:
                expression_parts.append(self._attribute_expr)
            if self._spatial_expr:
                expression_parts.append(self._spatial_expr)

            expression = " AND ".join(expression_parts) if expression_parts else ""

            if self._apply_to_layer and expression:
                layer.setSubsetString(expression)
                layer.triggerRepaint()

            self._final_feature_ids = []
            execution_time = (time.time() - start_time) * 1000

            return TaskResult.success_result(
                data={
                    'feature_ids': self._final_feature_ids,
                    'feature_count': layer.featureCount(),
                    'strategy': 'direct'
                },
                execution_time_ms=execution_time
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return TaskResult.error_result(str(e), execution_time)

    def _apply_filter_result(self) -> None:
        """Apply filter result to layer."""
        try:
            from qgis.core import QgsProject, QgsVectorLayer

            layer = QgsProject.instance().mapLayer(self._target_layer.layer_id)
            if not isinstance(layer, QgsVectorLayer):
                return

            if len(self._final_feature_ids) == 0:
                layer.setSubsetString("1=0")
            else:
                # Build ID filter
                pk = self._get_pk_field(layer)
                ids_str = ','.join(str(fid) for fid in self._final_feature_ids)
                layer.setSubsetString(f'"{pk}" IN ({ids_str})')

            layer.triggerRepaint()

        except Exception as e:
            logger.warning(f"Failed to apply filter result: {e}")

    def _get_pk_field(self, layer) -> str:
        """Get primary key field name."""
        try:
            pk_attrs = layer.primaryKeyAttributes()
            if pk_attrs:
                return layer.fields()[pk_attrs[0]].name()
        except Exception:
            pass
        return "fid"

    def _calculate_reduction_ratio(self) -> float:
        """Calculate overall reduction ratio."""
        if not self._steps_executed:
            return 0.0

        first_step = self._steps_executed[0]
        if first_step.get('candidates_before') == 'all':
            # Use estimated feature count
            initial = getattr(self._target_layer, 'feature_count', 0)
            if initial > 0:
                return 1.0 - (len(self._final_feature_ids) / initial)
        return 0.0

    @property
    def steps_executed(self) -> List[Dict[str, Any]]:
        """Get executed steps info."""
        return self._steps_executed

    @property
    def final_feature_ids(self) -> List[int]:
        """Get final filtered feature IDs."""
        return self._final_feature_ids

    def _on_completed(self, result: TaskResult) -> None:
        """Handle completion."""
        data = result.data or {}
        steps = data.get('steps_executed', [])
        count = data.get('feature_count', 0)
        logger.info(
            f"Multi-step filter completed: {count} features "
            f"after {len(steps)} steps"
        )

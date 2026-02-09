# -*- coding: utf-8 -*-
"""
FilterMate Spatial Task - ARCH-047

Async tasks for spatial operations.
Handles buffer, intersection, and other spatial ops.

Part of Phase 4 Task Refactoring.

Features:
- Buffer operations
- Spatial intersections
- Selection by geometry

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Optional, List, Tuple, Callable

from .base_task import BaseFilterMateTask, TaskResult

logger = logging.getLogger('FilterMate.Tasks.Spatial')


class SpatialFilterTask(BaseFilterMateTask):
    """
    Async task for spatial filtering operations.

    Filters target layers based on spatial relationship
    with source features.
    """

    # Spatial predicates
    INTERSECTS = "intersects"
    CONTAINS = "contains"
    WITHIN = "within"
    CROSSES = "crosses"
    TOUCHES = "touches"
    DISJOINT = "disjoint"
    OVERLAPS = "overlaps"

    def __init__(
        self,
        source_layer_id: str,
        target_layer_ids: List[str],
        predicate: str = "intersects",
        source_feature_ids: Optional[Tuple[int, ...]] = None,
        on_complete: Optional[Callable[[TaskResult], None]] = None,
        on_error: Optional[Callable[[TaskResult], None]] = None,
        on_progress: Optional[Callable[[int, str], None]] = None
    ):
        """
        Initialize spatial filter task.

        Args:
            source_layer_id: Source layer ID
            target_layer_ids: Target layer IDs to filter
            predicate: Spatial predicate (intersects, contains, etc.)
            source_feature_ids: Optional source feature filter
            on_complete: Success callback
            on_error: Error callback
            on_progress: Progress callback
        """
        super().__init__(
            description=f"Spatial filter ({predicate}) on {len(target_layer_ids)} layers",
            on_complete=on_complete,
            on_error=on_error,
            on_progress=on_progress
        )

        self._source_layer_id = source_layer_id
        self._target_layer_ids = target_layer_ids
        self._predicate = predicate
        self._source_feature_ids = source_feature_ids
        self._results: dict = {}

    def _execute(self) -> TaskResult:
        """Execute spatial filter."""
        try:
            from qgis.core import (
                QgsProject, QgsVectorLayer
            )

            self.report_progress(0, 100, "Loading source layer...")

            # Get source layer
            source_layer = QgsProject.instance().mapLayer(self._source_layer_id)
            if not isinstance(source_layer, QgsVectorLayer):
                return TaskResult.error_result("Source layer not found")

            # Get source geometries
            source_geoms = self._get_source_geometries(source_layer)
            if not source_geoms:
                return TaskResult.error_result("No source geometries found")

            self.report_progress(10, 100, "Processing targets...")

            # Combine source geometries
            combined_geom = source_geoms[0]
            for geom in source_geoms[1:]:
                combined_geom = combined_geom.combine(geom)

            total = len(self._target_layer_ids)
            total_matches = 0

            for i, target_id in enumerate(self._target_layer_ids):
                if self.check_cancelled():
                    return TaskResult.cancelled_result()

                target_layer = QgsProject.instance().mapLayer(target_id)
                if not isinstance(target_layer, QgsVectorLayer):
                    self._results[target_id] = {'error': 'Layer not found'}
                    continue

                self.report_progress(
                    10 + int((i / total) * 80),
                    100,
                    f"Filtering {target_layer.name()}"
                )

                matches = self._filter_target(target_layer, combined_geom)
                self._results[target_id] = {
                    'matches': matches,
                    'count': len(matches)
                }
                total_matches += len(matches)

            self.report_progress(100, 100, "Complete")

            return TaskResult.success_result(
                data={
                    'results': self._results,
                    'total_matches': total_matches
                },
                metrics={
                    'layers_processed': len(self._target_layer_ids),
                    'total_matches': total_matches
                }
            )

        except Exception as e:
            logger.exception(f"Spatial filter failed: {e}")
            return TaskResult.error_result(str(e))

    def _get_source_geometries(self, layer) -> List:
        """Get source geometries."""
        from qgis.core import QgsFeatureRequest

        geoms = []

        if self._source_feature_ids:
            request = QgsFeatureRequest()
            request.setFilterFids(list(self._source_feature_ids))
        else:
            request = QgsFeatureRequest()

        for feature in layer.getFeatures(request):
            if feature.hasGeometry():
                geoms.append(feature.geometry())

        return geoms

    def _filter_target(self, layer, source_geom) -> List[int]:
        """Filter target layer by spatial predicate."""
        from qgis.core import QgsFeatureRequest

        matches = []

        # Use spatial index if available
        bbox = source_geom.boundingBox()
        request = QgsFeatureRequest()
        request.setFilterRect(bbox)

        for feature in layer.getFeatures(request):
            if not feature.hasGeometry():
                continue

            target_geom = feature.geometry()

            if self._check_predicate(source_geom, target_geom):
                matches.append(feature.id())

        return matches

    def _check_predicate(self, geom1, geom2) -> bool:
        """Check spatial predicate."""
        predicate_map = {
            self.INTERSECTS: lambda g1, g2: g1.intersects(g2),
            self.CONTAINS: lambda g1, g2: g1.contains(g2),
            self.WITHIN: lambda g1, g2: g1.within(g2),
            self.CROSSES: lambda g1, g2: g1.crosses(g2),
            self.TOUCHES: lambda g1, g2: g1.touches(g2),
            self.DISJOINT: lambda g1, g2: g1.disjoint(g2),
            self.OVERLAPS: lambda g1, g2: g1.overlaps(g2),
        }

        check_func = predicate_map.get(self._predicate, predicate_map[self.INTERSECTS])
        return check_func(geom1, geom2)

    @property
    def results(self) -> dict:
        """Get spatial filter results."""
        return self._results


class BufferFilterTask(BaseFilterMateTask):
    """
    Async task for buffer-based filtering.

    Creates buffer around source features and filters targets.
    """

    def __init__(
        self,
        source_layer_id: str,
        target_layer_ids: List[str],
        buffer_distance: float,
        buffer_segments: int = 8,
        source_feature_ids: Optional[Tuple[int, ...]] = None,
        apply_to_layers: bool = True,
        on_complete: Optional[Callable[[TaskResult], None]] = None,
        on_error: Optional[Callable[[TaskResult], None]] = None
    ):
        """
        Initialize buffer filter task.

        Args:
            source_layer_id: Source layer ID
            target_layer_ids: Target layer IDs to filter
            buffer_distance: Buffer distance in layer units
            buffer_segments: Number of segments for buffer
            source_feature_ids: Optional source feature filter
            apply_to_layers: Apply filter to target layers
            on_complete: Success callback
            on_error: Error callback
        """
        super().__init__(
            description=f"Buffer filter ({buffer_distance}m) on {len(target_layer_ids)} layers",
            on_complete=on_complete,
            on_error=on_error
        )

        self._source_layer_id = source_layer_id
        self._target_layer_ids = target_layer_ids
        self._buffer_distance = buffer_distance
        self._buffer_segments = buffer_segments
        self._source_feature_ids = source_feature_ids
        self._apply_to_layers = apply_to_layers
        self._results: dict = {}

    def _execute(self) -> TaskResult:
        """Execute buffer filter."""
        try:
            from qgis.core import QgsProject, QgsVectorLayer

            self.report_progress(0, 100, "Loading source layer...")

            # Get source layer
            source_layer = QgsProject.instance().mapLayer(self._source_layer_id)
            if not isinstance(source_layer, QgsVectorLayer):
                return TaskResult.error_result("Source layer not found")

            # Build buffered geometry
            self.report_progress(10, 100, "Creating buffer...")

            buffered_geom = self._create_buffer(source_layer)
            if not buffered_geom:
                return TaskResult.error_result("Failed to create buffer")

            total = len(self._target_layer_ids)
            total_matches = 0

            for i, target_id in enumerate(self._target_layer_ids):
                if self.check_cancelled():
                    return TaskResult.cancelled_result()

                target_layer = QgsProject.instance().mapLayer(target_id)
                if not isinstance(target_layer, QgsVectorLayer):
                    self._results[target_id] = {'error': 'Layer not found'}
                    continue

                self.report_progress(
                    20 + int((i / total) * 70),
                    100,
                    f"Filtering {target_layer.name()}"
                )

                matches = self._filter_by_buffer(target_layer, buffered_geom)
                self._results[target_id] = {
                    'matches': matches,
                    'count': len(matches)
                }
                total_matches += len(matches)

                # Apply filter if requested
                if self._apply_to_layers and matches:
                    self._apply_filter(target_layer, matches)

            self.report_progress(100, 100, "Complete")

            return TaskResult.success_result(
                data={
                    'results': self._results,
                    'total_matches': total_matches,
                    'buffer_distance': self._buffer_distance
                },
                metrics={
                    'layers_processed': total,
                    'total_matches': total_matches
                }
            )

        except Exception as e:
            logger.exception(f"Buffer filter failed: {e}")
            return TaskResult.error_result(str(e))

    def _create_buffer(self, layer):
        """Create buffered geometry from source features."""
        from qgis.core import QgsFeatureRequest

        if self._source_feature_ids:
            request = QgsFeatureRequest()
            request.setFilterFids(list(self._source_feature_ids))
        else:
            request = QgsFeatureRequest()

        combined = None
        for feature in layer.getFeatures(request):
            if not feature.hasGeometry():
                continue

            buffered = feature.geometry().buffer(
                self._buffer_distance,
                self._buffer_segments
            )

            if combined is None:
                combined = buffered
            else:
                combined = combined.combine(buffered)

        return combined

    def _filter_by_buffer(self, layer, buffer_geom) -> List[int]:
        """Find features intersecting buffer."""
        from qgis.core import QgsFeatureRequest

        matches = []

        bbox = buffer_geom.boundingBox()
        request = QgsFeatureRequest()
        request.setFilterRect(bbox)

        for feature in layer.getFeatures(request):
            if feature.hasGeometry() and buffer_geom.intersects(feature.geometry()):
                matches.append(feature.id())

        return matches

    def _apply_filter(self, layer, feature_ids: List[int]) -> None:
        """Apply filter to layer."""
        if not feature_ids:
            layer.setSubsetString("1=0")
        else:
            pk = self._get_pk_field(layer)
            ids = ','.join(str(fid) for fid in feature_ids)
            layer.setSubsetString(f'"{pk}" IN ({ids})')

        layer.triggerRepaint()

    def _get_pk_field(self, layer) -> str:
        """Get primary key field name."""
        from infrastructure.utils.layer_utils import get_primary_key_name
        return get_primary_key_name(layer) or "fid"

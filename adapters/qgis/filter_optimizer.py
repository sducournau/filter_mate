# -*- coding: utf-8 -*-
"""
QGIS implementation of multi-step filter optimization.

This module provides the concrete implementation of IFilterOptimizer
for QGIS environments, adapting the legacy MultiStepFilterOptimizer
to the hexagonal architecture.

Part of FilterMate Hexagonal Architecture v3.0
"""

import logging
import time
import sqlite3
from typing import Dict, List, Optional, Tuple, Set, Any, Callable

from qgis.core import (
    QgsVectorLayer,
    QgsFeature,
    QgsFeatureRequest,
    QgsFeatureSource,
    QgsGeometry,
    QgsRectangle,
    QgsSpatialIndex,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsProject,
)

from ...core.ports.filter_optimizer import (
    IFilterOptimizer,
    ISelectivityEstimator,
    FilterStrategy,
    FilterPlan,
    FilterStep,
    LayerStatistics,
    PlanBuilderConfig,
)

logger = logging.getLogger(__name__)

# Singleton instances
_optimizer_instance: Optional["QgisFilterOptimizer"] = None


def get_filter_optimizer() -> "QgisFilterOptimizer":
    """Get singleton optimizer instance."""
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = QgisFilterOptimizer()
    return _optimizer_instance


def create_filter_optimizer(
    config: Optional[PlanBuilderConfig] = None
) -> "QgisFilterOptimizer":
    """Create new optimizer instance with custom config."""
    return QgisFilterOptimizer(config)


class QgisSelectivityEstimator(ISelectivityEstimator):
    """
    QGIS implementation of selectivity estimation.

    Uses sampling-based estimation since QGIS backends
    don't have PostgreSQL-style statistics.
    """

    # Statistics cache
    _stats_cache: Dict[str, LayerStatistics] = {}
    _cache_timestamps: Dict[str, float] = {}
    _cache_max_age: float = 300.0  # 5 minutes

    def __init__(self):
        """Initialize estimator."""

    def get_layer_statistics(
        self,
        layer_id: str,
        force_refresh: bool = False
    ) -> LayerStatistics:
        """Get or compute statistics for a layer."""
        current_time = time.time()

        # Check cache
        if not force_refresh and layer_id in self._stats_cache:
            cache_age = current_time - self._cache_timestamps.get(layer_id, 0)
            if cache_age < self._cache_max_age:
                return self._stats_cache[layer_id]

        # Get QGIS layer
        layer = self._get_layer(layer_id)
        if layer is None:
            return LayerStatistics(feature_count=0)

        # Compute stats
        stats = self._compute_statistics(layer)

        # Cache
        self._stats_cache[layer_id] = stats
        self._cache_timestamps[layer_id] = current_time

        return stats

    def _get_layer(self, layer_id: str) -> Optional[QgsVectorLayer]:
        """Get QGIS layer by ID."""
        project = QgsProject.instance()
        layer = project.mapLayer(layer_id)

        if layer and isinstance(layer, QgsVectorLayer):
            return layer
        return None

    def _compute_statistics(self, layer: QgsVectorLayer) -> LayerStatistics:
        """Compute statistics by sampling layer."""
        # Get safe feature count
        raw_count = layer.featureCount()
        feature_count = raw_count if raw_count is not None and raw_count >= 0 else 0

        # Get extent
        extent = layer.extent()
        extent_area = 0.0
        extent_bounds = None

        if extent and not extent.isNull():
            extent_area = extent.area()
            extent_bounds = (
                extent.xMinimum(),
                extent.yMinimum(),
                extent.xMaximum(),
                extent.yMaximum()
            )

        # Check spatial index
        # NOTE: hasSpatialIndex() returns QgsFeatureSource.SpatialIndexPresence enum:
        #   0 = SpatialIndexUnknown, 1 = SpatialIndexNotPresent, 2 = SpatialIndexPresent
        has_spatial_index = False
        if hasattr(layer, 'hasSpatialIndex'):
            has_spatial_index = layer.hasSpatialIndex() == QgsFeatureSource.SpatialIndexPresent

        stats = LayerStatistics(
            feature_count=feature_count,
            extent_area=extent_area,
            extent_bounds=extent_bounds,
            has_spatial_index=has_spatial_index,
            geometry_type=layer.geometryType(),
            avg_vertices_per_feature=0.0,
            estimated_complexity=1.0
        )

        # Sample for vertex complexity
        sample_size = min(100, feature_count) if feature_count > 0 else 0

        if sample_size > 0:
            total_vertices = 0
            sampled = 0

            request = QgsFeatureRequest()
            request.setLimit(sample_size)

            for feat in layer.getFeatures(request):
                geom = feat.geometry()
                if geom and not geom.isEmpty():
                    wkt = geom.asWkt()
                    vertex_count = wkt.count(',') + 1
                    total_vertices += vertex_count
                    sampled += 1

            if sampled > 0:
                stats.avg_vertices_per_feature = total_vertices / sampled
                stats.estimated_complexity = max(
                    1.0,
                    stats.avg_vertices_per_feature / 10.0
                )

        return stats

    def estimate_attribute_selectivity(
        self,
        layer_id: str,
        expression: str,
        sample_size: int = 200
    ) -> float:
        """Estimate attribute filter selectivity by sampling."""
        if not expression or not expression.strip():
            return 1.0

        layer = self._get_layer(layer_id)
        if layer is None:
            return 0.5

        feature_count = layer.featureCount()
        if feature_count == 0:
            return 0.0

        try:
            expr = QgsExpression(expression)
            if expr.hasParserError():
                return 0.5

            context = QgsExpressionContext()
            context.appendScopes(
                QgsExpressionContextUtils.globalProjectLayerScopes(layer)
            )

            actual_sample = min(sample_size, feature_count)
            request = QgsFeatureRequest()
            request.setLimit(actual_sample)

            matching = 0
            evaluated = 0

            for feat in layer.getFeatures(request):
                context.setFeature(feat)
                result = expr.evaluate(context)

                if result:
                    matching += 1
                evaluated += 1

            if evaluated == 0:
                return 0.5

            return matching / evaluated

        except Exception as e:
            logger.debug(f"Ignored in attribute selectivity estimation: {e}")
            return 0.5

    def estimate_spatial_selectivity(
        self,
        layer_id: str,
        source_extent: tuple
    ) -> float:
        """Estimate spatial filter selectivity based on extent overlap."""
        if not source_extent:
            return 1.0

        layer = self._get_layer(layer_id)
        if layer is None:
            return 0.5

        target_extent = layer.extent()
        if target_extent is None or target_extent.isNull():
            return 0.5

        # Create QgsRectangle from tuple
        source_rect = QgsRectangle(
            source_extent[0], source_extent[1],
            source_extent[2], source_extent[3]
        )

        if not target_extent.intersects(source_rect):
            return 0.0

        intersection = target_extent.intersect(source_rect)

        target_area = target_extent.area()
        if target_area <= 0:
            return 0.5

        overlap_ratio = intersection.area() / target_area

        # Dampening factor (empirical)
        estimated_selectivity = overlap_ratio * 0.7

        return min(1.0, max(0.0, estimated_selectivity))

    def clear_cache(self, layer_id: Optional[str] = None) -> int:
        """Clear statistics cache."""
        if layer_id:
            removed = 0
            if layer_id in self._stats_cache:
                del self._stats_cache[layer_id]
                removed += 1
            if layer_id in self._cache_timestamps:
                del self._cache_timestamps[layer_id]
            return removed
        else:
            count = len(self._stats_cache)
            self._stats_cache.clear()
            self._cache_timestamps.clear()
            return count


class QgisFilterOptimizer(IFilterOptimizer):
    """
    QGIS implementation of filter optimization.

    Provides multi-step filter optimization for non-PostgreSQL backends
    (Spatialite, OGR, Memory) following the hexagonal architecture pattern.
    """

    def __init__(self, config: Optional[PlanBuilderConfig] = None):
        """
        Initialize optimizer.

        Args:
            config: Optional configuration for plan building
        """
        self.config = config or PlanBuilderConfig()
        self.estimator = QgisSelectivityEstimator()

        # Statistics
        self._plans_built = 0
        self._prefilters_executed = 0

    def _get_layer(self, layer_id: str) -> Optional[QgsVectorLayer]:
        """Get QGIS layer by ID."""
        project = QgsProject.instance()
        layer = project.mapLayer(layer_id)

        if layer and isinstance(layer, QgsVectorLayer):
            return layer
        return None

    def get_layer_statistics(
        self,
        layer_id: str,
        force_refresh: bool = False
    ) -> LayerStatistics:
        """Get statistics for a layer."""
        return self.estimator.get_layer_statistics(layer_id, force_refresh)

    def build_filter_plan(
        self,
        layer_id: str,
        attribute_filter: Optional[str] = None,
        spatial_extent: Optional[tuple] = None,
        has_spatial_filter: bool = False
    ) -> FilterPlan:
        """Build an optimal filter execution plan."""
        stats = self.get_layer_statistics(layer_id)
        feature_count = stats.feature_count

        # Estimate selectivities
        attr_selectivity = 1.0
        if attribute_filter:
            attr_selectivity = self.estimator.estimate_attribute_selectivity(
                layer_id, attribute_filter
            )

        spatial_selectivity = 1.0
        if has_spatial_filter and spatial_extent:
            spatial_selectivity = self.estimator.estimate_spatial_selectivity(
                layer_id, spatial_extent
            )

        combined_selectivity = attr_selectivity * spatial_selectivity

        self._plans_built += 1

        # Strategy selection based on dataset size and selectivity

        # Small datasets: direct processing
        if feature_count <= self.config.small_dataset_threshold:
            return FilterPlan(
                strategy=FilterStrategy.DIRECT,
                estimated_selectivity=combined_selectivity,
                estimated_cost=1.0,
                attribute_filter=attribute_filter,
                spatial_filter=None,
                use_spatial_index=False
            )

        # Attribute-first strategy if attribute filter is very selective
        if (attribute_filter and
            attr_selectivity < self.config.attribute_first_selectivity_threshold and
                feature_count > self.config.small_dataset_threshold):

            estimated_after_attr = int(feature_count * attr_selectivity)

            steps = [
                FilterStep(
                    step_type="attribute",
                    expression=attribute_filter,
                    estimated_output=estimated_after_attr
                )
            ]

            if has_spatial_filter:
                steps.append(FilterStep(
                    step_type="spatial",
                    estimated_output=int(estimated_after_attr * spatial_selectivity)
                ))

            return FilterPlan(
                strategy=FilterStrategy.ATTRIBUTE_FIRST,
                estimated_selectivity=combined_selectivity,
                estimated_cost=2.0 + (0.5 if has_spatial_filter else 0.0),
                steps=steps,
                attribute_filter=attribute_filter,
                spatial_filter=None,
                use_spatial_index=stats.has_spatial_index
            )

        # Large datasets with spatial filter: bbox pre-filtering
        if (has_spatial_filter and
            spatial_selectivity < self.config.bbox_prefilter_threshold and
                feature_count > self.config.medium_dataset_threshold):

            # BBox is less selective than exact geometry
            estimated_after_bbox = int(feature_count * (spatial_selectivity * 1.5))

            steps = []

            if attribute_filter:
                steps.append(FilterStep(
                    step_type="attribute",
                    expression=attribute_filter,
                    estimated_output=int(feature_count * attr_selectivity)
                ))

            steps.append(FilterStep(
                step_type="bbox_filter",
                estimated_output=estimated_after_bbox
            ))

            steps.append(FilterStep(
                step_type="exact_spatial",
                estimated_output=int(feature_count * spatial_selectivity)
            ))

            return FilterPlan(
                strategy=FilterStrategy.BBOX_THEN_EXACT,
                estimated_selectivity=combined_selectivity,
                estimated_cost=3.0,
                steps=steps,
                attribute_filter=attribute_filter,
                use_spatial_index=True
            )

        # Very large datasets: progressive chunking
        if feature_count > self.config.large_dataset_threshold:
            chunk_size = self.config.calculate_chunk_size(
                feature_count,
                stats.estimated_complexity
            )

            return FilterPlan(
                strategy=FilterStrategy.PROGRESSIVE_CHUNKS,
                estimated_selectivity=combined_selectivity,
                estimated_cost=5.0 + (feature_count / chunk_size) * 0.1,
                chunk_size=chunk_size,
                attribute_filter=attribute_filter,
                use_spatial_index=True
            )

        # Default: hybrid approach
        return FilterPlan(
            strategy=FilterStrategy.HYBRID,
            estimated_selectivity=combined_selectivity,
            estimated_cost=2.5,
            attribute_filter=attribute_filter,
            use_spatial_index=stats.has_spatial_index
        )

    def execute_attribute_prefilter(
        self,
        layer_id: str,
        expression: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Set[int]:
        """Execute attribute pre-filtering phase."""
        layer = self._get_layer(layer_id)
        if layer is None:
            return set()

        matching_fids: Set[int] = set()

        try:
            expr = QgsExpression(expression)
            if expr.hasParserError():
                return matching_fids

            context = QgsExpressionContext()
            context.appendScopes(
                QgsExpressionContextUtils.globalProjectLayerScopes(layer)
            )

            # Request only attributes (no geometry)
            request = QgsFeatureRequest()
            request.setFlags(QgsFeatureRequest.NoGeometry)

            total = layer.featureCount()
            processed = 0

            for feat in layer.getFeatures(request):
                context.setFeature(feat)
                result = expr.evaluate(context)

                if result:
                    matching_fids.add(feat.id())

                processed += 1
                if progress_callback and processed % 1000 == 0:
                    progress_callback(processed, total)

            self._prefilters_executed += 1

            return matching_fids

        except Exception as e:
            logger.debug(f"Ignored in attribute prefilter execution: {e}")
            return matching_fids

    def execute_chunked_filter(
        self,
        layer_id: str,
        processor: Callable[[List[QgsFeature]], Set[int]],
        prefiltered_fids: Optional[Set[int]] = None,
        chunk_size: int = 10000,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Set[int]:
        """
        Execute spatial filtering in chunks.

        Args:
            layer_id: Layer identifier
            processor: Function that processes a chunk and returns matching FIDs
            prefiltered_fids: Optional pre-filtered FIDs
            chunk_size: Features per chunk
            progress_callback: Optional (current, total, message) callback

        Returns:
            Set of matching feature IDs
        """
        layer = self._get_layer(layer_id)
        if layer is None:
            return set()

        all_matching: Set[int] = set()

        request = QgsFeatureRequest()

        # Apply pre-filter if provided
        if prefiltered_fids is not None:
            if len(prefiltered_fids) == 0:
                return all_matching

            if len(prefiltered_fids) <= 1000:
                request.setFilterFids(list(prefiltered_fids))
            else:
                fid_list = ','.join(str(f) for f in sorted(prefiltered_fids))
                request.setFilterExpression(f'$id IN ({fid_list})')

        total = len(prefiltered_fids) if prefiltered_fids else layer.featureCount()
        processed = 0
        chunk_num = 0
        current_chunk: List[QgsFeature] = []

        for feat in layer.getFeatures(request):
            current_chunk.append(feat)

            if len(current_chunk) >= chunk_size:
                chunk_result = processor(current_chunk)
                all_matching.update(chunk_result)

                processed += len(current_chunk)
                chunk_num += 1
                current_chunk = []

                if progress_callback:
                    progress_callback(
                        processed, total,
                        f"Chunk {chunk_num}: {len(all_matching)} matches"
                    )

        # Process remaining
        if current_chunk:
            chunk_result = processor(current_chunk)
            all_matching.update(chunk_result)

        return all_matching

    def clear_cache(self, layer_id: Optional[str] = None) -> int:
        """Clear statistics cache."""
        return self.estimator.clear_cache(layer_id)

    def get_statistics(self) -> Dict[str, Any]:
        """Get optimizer usage statistics."""
        return {
            "plans_built": self._plans_built,
            "prefilters_executed": self._prefilters_executed,
            "cache_size": len(self.estimator._stats_cache)
        }

    def reset_statistics(self) -> None:
        """Reset usage statistics."""
        self._plans_built = 0
        self._prefilters_executed = 0


# Utility classes for specific backends

class SpatialiteQueryBuilder:
    """Builds optimized Spatialite SQL queries."""

    @staticmethod
    def build_optimized_query(
        table_name: str,
        geom_column: str,
        attribute_filter: Optional[str],
        spatial_predicate: str,
        source_wkt: str,
        source_srid: int,
        use_bbox_prefilter: bool = True
    ) -> str:
        """
        Build an optimized Spatialite SQL query.

        Uses R-tree index for bbox pre-filtering when available.
        """
        geom_expr = f"GeomFromText('{source_wkt}', {source_srid})"

        where_clauses = []

        # Attribute filter first
        if attribute_filter:
            where_clauses.append(f"({attribute_filter})")

        # R-tree bbox pre-filter
        if use_bbox_prefilter:
            f"idx_{table_name}_geometry"
            bbox_filter = """
                rowid IN (
                    SELECT pkid FROM {rtree_table}
                    WHERE xmin <= MbrMaxX({geom_expr})
                      AND xmax >= MbrMinX({geom_expr})
                      AND ymin <= MbrMaxY({geom_expr})
                      AND ymax >= MbrMinY({geom_expr})
                )
            """
            where_clauses.append(bbox_filter.strip())

        # Exact spatial predicate
        spatial_filter = f'{spatial_predicate}("{geom_column}", {geom_expr})'
        where_clauses.append(spatial_filter)

        where_clause = " AND ".join(where_clauses)

        return f'SELECT rowid FROM "{table_name}" WHERE {where_clause}'  # nosec B608 - table_name from QGIS layer metadata (SpatiaLite path)

    @staticmethod
    def get_sqlite_stats(db_path: str, table_name: str) -> Dict[str, Any]:
        """Get SQLite statistics for a table."""
        stats = {}

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check for sqlite_stat1
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_stat1'"
            )
            if cursor.fetchone():
                cursor.execute(
                    "SELECT stat FROM sqlite_stat1 WHERE tbl=?",
                    (table_name,)
                )
                row = cursor.fetchone()
                if row:
                    stat_parts = row[0].split()
                    if stat_parts:
                        stats['row_count'] = int(stat_parts[0])

            # Check for R-tree index
            cursor.execute(
                """SELECT name FROM sqlite_master
                   WHERE type='table' AND name LIKE 'idx_%_geometry'"""
            )
            if cursor.fetchone():
                stats['has_rtree'] = True

            conn.close()

        except Exception as e:
            logger.debug(f"Ignored in SQLite stats retrieval: {e}")

        return stats


class OgrSubsetBuilder:
    """Builds OGR-compatible subset strings."""

    @staticmethod
    def build_fid_subset(fids: Set[int]) -> str:
        """
        Build an OGR-compatible subset string from FIDs.

        OGR subset strings use 'fid' instead of '$id'.
        """
        if not fids:
            return 'fid = -1'  # Match nothing

        if len(fids) == 1:
            return f'fid = {next(iter(fids))}'

        if len(fids) <= 500:
            fid_list = ','.join(str(f) for f in sorted(fids))
            return f'fid IN ({fid_list})'

        # Large set: try to use consecutive ranges
        sorted_fids = sorted(fids)
        ranges = OgrSubsetBuilder._find_consecutive_ranges(sorted_fids)

        if len(ranges) < len(fids) / 3:
            range_exprs = []
            for start, end in ranges:
                if start == end:
                    range_exprs.append(f'fid = {start}')
                else:
                    range_exprs.append(f'(fid >= {start} AND fid <= {end})')
            return ' OR '.join(range_exprs)

        # Fall back to IN clause
        fid_list = ','.join(str(f) for f in sorted_fids)
        return f'fid IN ({fid_list})'

    @staticmethod
    def _find_consecutive_ranges(
        sorted_fids: List[int]
    ) -> List[Tuple[int, int]]:
        """Find consecutive ranges in sorted FIDs."""
        if not sorted_fids:
            return []

        ranges = []
        start = sorted_fids[0]
        end = start

        for fid in sorted_fids[1:]:
            if fid == end + 1:
                end = fid
            else:
                ranges.append((start, end))
                start = fid
                end = fid

        ranges.append((start, end))
        return ranges


class MemorySpatialIndex:
    """Manages spatial indices for memory layers."""

    _index_cache: Dict[str, Tuple[QgsSpatialIndex, Dict[int, QgsGeometry]]] = {}

    @classmethod
    def get_or_create(
        cls,
        layer: QgsVectorLayer
    ) -> Tuple[QgsSpatialIndex, Dict[int, QgsGeometry]]:
        """Get or create spatial index for a memory layer."""
        layer_id = layer.id()

        if layer_id in cls._index_cache:
            return cls._index_cache[layer_id]

        spatial_index = QgsSpatialIndex()
        geom_cache: Dict[int, QgsGeometry] = {}

        for feat in layer.getFeatures():
            geom = feat.geometry()
            if geom and not geom.isEmpty() and geom.isGeosValid():
                spatial_index.addFeature(feat)
                geom_cache[feat.id()] = geom

        cls._index_cache[layer_id] = (spatial_index, geom_cache)
        return spatial_index, geom_cache

    @classmethod
    def clear_cache(cls, layer_id: Optional[str] = None) -> int:
        """Clear index cache."""
        if layer_id:
            if layer_id in cls._index_cache:
                del cls._index_cache[layer_id]
                return 1
            return 0
        else:
            count = len(cls._index_cache)
            cls._index_cache.clear()
            return count

    @classmethod
    def filter_by_spatial_predicate(
        cls,
        layer: QgsVectorLayer,
        fids: Set[int],
        intersect_geom: QgsGeometry,
        predicate: str = 'intersects'
    ) -> Set[int]:
        """Apply spatial predicate to pre-filtered FIDs."""
        matching: Set[int] = set()

        if not fids:
            return matching

        request = QgsFeatureRequest()
        request.setFilterFids(list(fids))

        predicate_lower = predicate.lower()

        for feat in layer.getFeatures(request):
            geom = feat.geometry()
            if not geom or geom.isEmpty():
                continue

            try:
                match = False
                if predicate_lower == 'intersects':
                    match = geom.intersects(intersect_geom)
                elif predicate_lower == 'within':
                    match = geom.within(intersect_geom)
                elif predicate_lower == 'contains':
                    match = geom.contains(intersect_geom)
                elif predicate_lower == 'overlaps':
                    match = geom.overlaps(intersect_geom)

                if match:
                    matching.add(feat.id())

            except Exception as e:
                logger.debug(f"Ignored in spatial predicate evaluation: {e}")

        return matching

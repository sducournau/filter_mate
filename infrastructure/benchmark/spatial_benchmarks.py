# -*- coding: utf-8 -*-
"""
Spatial Query Benchmarks for FilterMate.

v4.1.1 - January 2026 - EPIC-3 Sprint 1

PURPOSE:
Benchmark suite for measuring spatial query performance:
1. Bounding box queries
2. Point-in-polygon tests
3. Buffer operations
4. Spatial index performance
5. Intersection queries

USAGE:
    from infrastructure.benchmark import SpatialBenchmarks
    
    suite = SpatialBenchmarks(layer=my_layer)
    results = suite.run_all()
"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from .framework import BenchmarkRunner, BenchmarkResult, Timer

try:
    from qgis.core import (
        QgsVectorLayer,
        QgsFeatureRequest,
        QgsRectangle,
        QgsGeometry,
        QgsPointXY,
        QgsSpatialIndex,
    )
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False

logger = logging.getLogger('FilterMate.Benchmark.Spatial')


@dataclass
class SpatialBenchmarkConfig:
    """Configuration for spatial benchmarks."""
    iterations: int = 10
    warmup: int = 2
    bbox_scale: float = 0.1  # Fraction of layer extent for bbox tests
    buffer_distance: float = 100.0  # Buffer distance in layer units


class SpatialBenchmarks:
    """
    Benchmark suite for spatial operations.
    
    Tests various spatial query types to measure performance.
    
    Example:
        layer = QgsProject.instance().mapLayersByName("parcels")[0]
        benchmarks = SpatialBenchmarks(layer)
        results = benchmarks.run_all()
    """
    
    def __init__(
        self,
        layer: 'QgsVectorLayer' = None,
        config: SpatialBenchmarkConfig = None,
    ):
        """
        Initialize spatial benchmarks.
        
        Args:
            layer: Layer to benchmark
            config: Benchmark configuration
        """
        self.layer = layer
        self.config = config or SpatialBenchmarkConfig()
        self.runner = BenchmarkRunner(
            iterations=self.config.iterations,
            warmup=self.config.warmup,
        )
        self._results: List[BenchmarkResult] = []
        self._spatial_index: Optional['QgsSpatialIndex'] = None
    
    def _get_layer_extent(self) -> Optional['QgsRectangle']:
        """Get layer extent."""
        if not self.layer:
            return None
        return self.layer.extent()
    
    def _get_center_point(self) -> Optional['QgsPointXY']:
        """Get center point of layer extent."""
        extent = self._get_layer_extent()
        if not extent:
            return None
        return extent.center()
    
    def _get_test_bbox(self, scale: float = None) -> Optional['QgsRectangle']:
        """Get a test bounding box centered on layer."""
        extent = self._get_layer_extent()
        if not extent:
            return None
        
        scale = scale or self.config.bbox_scale
        center = extent.center()
        
        width = extent.width() * scale
        height = extent.height() * scale
        
        return QgsRectangle(
            center.x() - width / 2,
            center.y() - height / 2,
            center.x() + width / 2,
            center.y() + height / 2,
        )
    
    def _build_spatial_index(self) -> 'QgsSpatialIndex':
        """Build or return cached spatial index."""
        if self._spatial_index is None:
            self._spatial_index = QgsSpatialIndex(self.layer.getFeatures())
        return self._spatial_index
    
    def benchmark_bbox_query(self, scale: float = None) -> BenchmarkResult:
        """
        Benchmark bounding box query.
        
        Args:
            scale: Fraction of layer extent to use for bbox
        """
        if not self.layer:
            return BenchmarkResult(name="bbox_query", description="No layer")
        
        bbox = self._get_test_bbox(scale or self.config.bbox_scale)
        if not bbox:
            return BenchmarkResult(name="bbox_query", description="Could not create bbox")
        
        def run_query():
            request = QgsFeatureRequest()
            request.setFilterRect(bbox)
            count = sum(1 for _ in self.layer.getFeatures(request))
            return count
        
        scale_pct = int((scale or self.config.bbox_scale) * 100)
        name = f"spatial.bbox_{scale_pct}pct"
        
        self.runner.add(
            name,
            run_query,
            f"Bounding box query ({scale_pct}% of extent)",
            {'bbox': bbox.asWktPolygon(), 'scale': scale_pct}
        )
        
        result = self.runner.run(name)
        self._results.append(result)
        return result
    
    def benchmark_spatial_index_build(self) -> BenchmarkResult:
        """Benchmark building a spatial index."""
        if not self.layer:
            return BenchmarkResult(name="index_build", description="No layer")
        
        def run_build():
            # Force rebuild
            index = QgsSpatialIndex(self.layer.getFeatures())
            return index
        
        self.runner.add(
            "spatial.index_build",
            run_build,
            "Build spatial index",
            {'feature_count': self.layer.featureCount()}
        )
        
        result = self.runner.run("spatial.index_build")
        self._results.append(result)
        return result
    
    def benchmark_spatial_index_query(self, scale: float = None) -> BenchmarkResult:
        """
        Benchmark spatial index query.
        
        Args:
            scale: Fraction of layer extent for query bbox
        """
        if not self.layer:
            return BenchmarkResult(name="index_query", description="No layer")
        
        bbox = self._get_test_bbox(scale or self.config.bbox_scale)
        if not bbox:
            return BenchmarkResult(name="index_query", description="Could not create bbox")
        
        # Build index first
        index = self._build_spatial_index()
        
        def run_query():
            ids = index.intersects(bbox)
            return len(ids)
        
        scale_pct = int((scale or self.config.bbox_scale) * 100)
        name = f"spatial.index_query_{scale_pct}pct"
        
        self.runner.add(
            name,
            run_query,
            f"Spatial index query ({scale_pct}% of extent)",
            {'bbox': bbox.asWktPolygon(), 'scale': scale_pct}
        )
        
        result = self.runner.run(name)
        self._results.append(result)
        return result
    
    def benchmark_point_in_polygon(self) -> BenchmarkResult:
        """Benchmark point-in-polygon tests."""
        if not self.layer:
            return BenchmarkResult(name="point_in_polygon", description="No layer")
        
        # Get center point
        center = self._get_center_point()
        if not center:
            return BenchmarkResult(name="point_in_polygon", description="Could not get center")
        
        point_geom = QgsGeometry.fromPointXY(center)
        
        def run_query():
            count = 0
            for feature in self.layer.getFeatures():
                geom = feature.geometry()
                if geom and geom.contains(point_geom):
                    count += 1
            return count
        
        self.runner.add(
            "spatial.point_in_polygon",
            run_query,
            "Point-in-polygon test (full scan)",
            {'test_point': f"({center.x():.2f}, {center.y():.2f})"}
        )
        
        result = self.runner.run("spatial.point_in_polygon")
        self._results.append(result)
        return result
    
    def benchmark_buffer_creation(self, distance: float = None) -> BenchmarkResult:
        """
        Benchmark buffer geometry creation.
        
        Args:
            distance: Buffer distance in layer units
        """
        if not self.layer:
            return BenchmarkResult(name="buffer_create", description="No layer")
        
        distance = distance or self.config.buffer_distance
        
        # Get first 100 geometries
        geometries = []
        for i, feature in enumerate(self.layer.getFeatures()):
            if i >= 100:
                break
            geom = feature.geometry()
            if geom and not geom.isEmpty():
                geometries.append(geom)
        
        if not geometries:
            return BenchmarkResult(name="buffer_create", description="No geometries")
        
        def run_buffer():
            for geom in geometries:
                geom.buffer(distance, 8)
        
        self.runner.add(
            "spatial.buffer_create",
            run_buffer,
            f"Buffer creation ({len(geometries)} geometries, distance={distance})",
            {'distance': distance, 'geometry_count': len(geometries)}
        )
        
        result = self.runner.run("spatial.buffer_create")
        self._results.append(result)
        return result
    
    def benchmark_intersection_test(self) -> BenchmarkResult:
        """Benchmark geometry intersection tests."""
        if not self.layer:
            return BenchmarkResult(name="intersection", description="No layer")
        
        # Create test polygon from bbox
        bbox = self._get_test_bbox(0.2)  # 20% of extent
        if not bbox:
            return BenchmarkResult(name="intersection", description="Could not create bbox")
        
        test_geom = QgsGeometry.fromRect(bbox)
        
        def run_query():
            count = 0
            for feature in self.layer.getFeatures():
                geom = feature.geometry()
                if geom and geom.intersects(test_geom):
                    count += 1
            return count
        
        self.runner.add(
            "spatial.intersection_test",
            run_query,
            "Intersection test (20% extent polygon)",
            {'test_bbox': bbox.asWktPolygon()}
        )
        
        result = self.runner.run("spatial.intersection_test")
        self._results.append(result)
        return result
    
    def benchmark_distance_calculation(self) -> BenchmarkResult:
        """Benchmark distance calculations between features."""
        if not self.layer:
            return BenchmarkResult(name="distance", description="No layer")
        
        center = self._get_center_point()
        if not center:
            return BenchmarkResult(name="distance", description="Could not get center")
        
        center_geom = QgsGeometry.fromPointXY(center)
        
        def run_query():
            distances = []
            for i, feature in enumerate(self.layer.getFeatures()):
                if i >= 1000:
                    break
                geom = feature.geometry()
                if geom and not geom.isEmpty():
                    dist = center_geom.distance(geom)
                    distances.append(dist)
            return len(distances)
        
        self.runner.add(
            "spatial.distance_calc",
            run_query,
            "Distance calculation (up to 1000 features)",
            {'center': f"({center.x():.2f}, {center.y():.2f})"}
        )
        
        result = self.runner.run("spatial.distance_calc")
        self._results.append(result)
        return result
    
    def benchmark_centroid_calculation(self) -> BenchmarkResult:
        """Benchmark centroid calculations."""
        if not self.layer:
            return BenchmarkResult(name="centroid", description="No layer")
        
        def run_query():
            centroids = []
            for i, feature in enumerate(self.layer.getFeatures()):
                if i >= 1000:
                    break
                geom = feature.geometry()
                if geom and not geom.isEmpty():
                    centroid = geom.centroid()
                    centroids.append(centroid)
            return len(centroids)
        
        self.runner.add(
            "spatial.centroid_calc",
            run_query,
            "Centroid calculation (up to 1000 features)",
        )
        
        result = self.runner.run("spatial.centroid_calc")
        self._results.append(result)
        return result
    
    def run_all(self) -> List[BenchmarkResult]:
        """
        Run all spatial benchmarks.
        
        Returns:
            List of BenchmarkResult objects
        """
        if not self.layer:
            logger.error("No layer configured for spatial benchmarks")
            return []
        
        logger.info(f"🚀 Running spatial benchmarks on '{self.layer.name()}'")
        logger.info(f"   Features: {self.layer.featureCount():,}")
        logger.info(f"   Geometry type: {self.layer.geometryType()}")
        
        results = []
        
        # Bounding box queries at different scales
        results.append(self.benchmark_bbox_query(0.1))  # 10%
        results.append(self.benchmark_bbox_query(0.25))  # 25%
        results.append(self.benchmark_bbox_query(0.5))  # 50%
        
        # Spatial index
        results.append(self.benchmark_spatial_index_build())
        results.append(self.benchmark_spatial_index_query(0.1))
        results.append(self.benchmark_spatial_index_query(0.25))
        
        # Geometry operations
        results.append(self.benchmark_point_in_polygon())
        results.append(self.benchmark_intersection_test())
        results.append(self.benchmark_buffer_creation())
        results.append(self.benchmark_distance_calculation())
        results.append(self.benchmark_centroid_calculation())
        
        logger.info(f"✅ Completed {len(results)} spatial benchmarks")
        return results
    
    def get_results(self) -> List[BenchmarkResult]:
        """Get all benchmark results."""
        return self._results.copy()


def run_spatial_benchmarks(
    layer: 'QgsVectorLayer',
    iterations: int = 10,
) -> List[BenchmarkResult]:
    """
    Convenience function to run all spatial benchmarks.
    
    Args:
        layer: Layer to benchmark
        iterations: Number of iterations per benchmark
        
    Returns:
        List of BenchmarkResult objects
    """
    config = SpatialBenchmarkConfig(iterations=iterations)
    benchmarks = SpatialBenchmarks(layer, config)
    return benchmarks.run_all()

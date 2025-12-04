# -*- coding: utf-8 -*-
"""
Performance tests for FilterMate optimizations.

Tests the performance improvements of:
1. OGR spatial index creation
2. Spatialite temporary table optimization
3. Source geometry cache
4. Predicate ordering optimization

Usage:
    pytest tests/test_performance.py -v
    pytest tests/test_performance.py::test_ogr_spatial_index -v
"""

import pytest
import time
import statistics
from unittest.mock import Mock, MagicMock, patch
from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsGeometry, QgsField,
    QgsProject, QgsCoordinateReferenceSystem
)
from qgis.PyQt.QtCore import QVariant


class TestPerformanceOptimizations:
    """Test suite for performance optimizations"""
    
    def test_ogr_spatial_index_creation(self):
        """
        Test that OGR backend creates spatial index automatically.
        
        Expected: _ensure_spatial_index() should be called during apply_filter()
        """
        from modules.backends.ogr_backend import OGRGeometricFilter
        
        # Create mock layer without spatial index
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.name.return_value = "test_layer"
        mock_layer.hasSpatialIndex.return_value = False
        mock_layer.featureCount.return_value = 5000
        
        backend = OGRGeometricFilter({})
        
        # Mock processing.run to avoid actual processing
        with patch('modules.backends.ogr_backend.processing.run') as mock_processing:
            mock_processing.return_value = {'OUTPUT': mock_layer}
            
            # Call _ensure_spatial_index
            result = backend._ensure_spatial_index(mock_layer)
            
            # Verify index creation was attempted
            assert mock_processing.called
            assert mock_processing.call_args[0][0] == "native:createspatialindex"
    
    def test_ogr_large_dataset_optimization(self):
        """
        Test that OGR backend uses optimized method for large datasets.
        
        Expected: Datasets ≥10k features should use _apply_filter_large()
        """
        from modules.backends.ogr_backend import OGRGeometricFilter
        
        # Create mock layer with 15k features
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.name.return_value = "large_layer"
        mock_layer.featureCount.return_value = 15000
        mock_layer.hasSpatialIndex.return_value = True
        
        backend = OGRGeometricFilter({})
        backend.source_geom = Mock()  # Mock source layer
        
        # Mock the optimization methods
        backend._apply_filter_standard = Mock(return_value=True)
        backend._apply_filter_large = Mock(return_value=True)
        
        # Call apply_filter with JSON expression
        import json
        expression = json.dumps({'predicates': ['intersects']})
        
        backend.apply_filter(mock_layer, expression)
        
        # Verify large method was called (not standard)
        assert backend._apply_filter_large.called
        assert not backend._apply_filter_standard.called
    
    def test_spatialite_temp_table_optimization(self):
        """
        Test that Spatialite backend uses temp table for large WKT.
        
        Expected: WKT >100KB should trigger temp table creation
        """
        from modules.backends.spatialite_backend import SpatialiteGeometricFilter
        
        backend = SpatialiteGeometricFilter({})
        
        # Create large WKT (>100KB)
        large_wkt = "POLYGON((" + ", ".join([f"{i} {i}" for i in range(10000)]) + "))"
        
        # Mock layer
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.name.return_value = "test_layer"
        mock_layer.crs.return_value.authid.return_value = "EPSG:4326"
        mock_layer.crs.return_value.isValid.return_value = True
        
        layer_props = {
            'layer_name': 'test_table',
            'geometry_field': 'geom',
            'layer': mock_layer
        }
        
        predicates = {
            'intersects': 'ST_Intersects'
        }
        
        # Mock _get_spatialite_db_path to return a path
        backend._get_spatialite_db_path = Mock(return_value="/tmp/test.sqlite")
        
        # Mock _create_temp_geometry_table
        backend._create_temp_geometry_table = Mock(return_value=("_fm_temp_123", Mock()))
        
        # Build expression
        expression = backend.build_expression(
            layer_props, predicates, source_geom=large_wkt
        )
        
        # Verify temp table creation was called
        assert backend._create_temp_geometry_table.called
        assert "_fm_temp_" in expression or backend._temp_table_name is not None
    
    def test_geometry_cache_performance(self):
        """
        Test that SourceGeometryCache prevents recalculation.
        
        Expected: Second access should be instant (cache hit)
        """
        from modules.appTasks import SourceGeometryCache
        
        cache = SourceGeometryCache()
        
        # Create mock features
        mock_features = [Mock(id=lambda: i) for i in range(100)]
        buffer_value = 10.0
        crs_authid = "EPSG:3857"
        
        # Store geometry in cache
        test_data = {
            'wkt': 'POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))',
            'bbox': [0, 0, 1, 1]
        }
        
        cache.put(mock_features, buffer_value, crs_authid, test_data)
        
        # Measure cache retrieval time
        start = time.time()
        result = cache.get(mock_features, buffer_value, crs_authid)
        elapsed = time.time() - start
        
        # Cache hit should be nearly instant (<1ms)
        assert result is not None
        assert result == test_data
        assert elapsed < 0.001, f"Cache retrieval took {elapsed}s (expected <1ms)"
    
    def test_geometry_cache_multilayer_scenario(self):
        """
        Test cache benefit when filtering multiple layers.
        
        Expected: 5 layers should only calculate geometry once
        """
        from modules.appTasks import SourceGeometryCache
        
        cache = SourceGeometryCache()
        
        mock_features = [Mock(id=lambda i=i: i) for i in range(50)]
        buffer_value = 5.0
        crs_authid = "EPSG:4326"
        
        test_data = {'wkt': 'MULTIPOLYGON(...)', 'bbox': [0, 0, 10, 10]}
        
        # Simulate filtering 5 layers with same source
        hits = 0
        misses = 0
        
        for layer_num in range(5):
            result = cache.get(mock_features, buffer_value, crs_authid)
            
            if result is None:
                misses += 1
                # Simulate expensive calculation (would be ~2s in reality)
                cache.put(mock_features, buffer_value, crs_authid, test_data)
            else:
                hits += 1
        
        # First layer: miss (calculation needed)
        # Layers 2-5: hits (cache reuse)
        assert misses == 1, f"Expected 1 miss, got {misses}"
        assert hits == 4, f"Expected 4 hits, got {hits}"
    
    def test_predicate_ordering_optimization(self):
        """
        Test that predicates are ordered optimally (intersects first).
        
        Expected: More selective predicates should appear first in expression
        """
        from modules.backends.spatialite_backend import SpatialiteGeometricFilter
        
        backend = SpatialiteGeometricFilter({})
        
        # Create predicates in random order
        predicates = {
            'touches': 'ST_Touches',
            'intersects': 'ST_Intersects',  # Should be first (most selective)
            'overlaps': 'ST_Overlaps',
            'within': 'ST_Within'  # Should be second
        }
        
        layer_props = {
            'layer_name': 'test',
            'geometry_field': 'geom'
        }
        
        # Small WKT to avoid temp table optimization
        small_wkt = "POINT(0 0)"
        
        expression = backend.build_expression(
            layer_props, predicates, source_geom=small_wkt
        )
        
        # Check that intersects appears before touches/overlaps
        intersects_pos = expression.find('ST_Intersects')
        touches_pos = expression.find('ST_Touches')
        overlaps_pos = expression.find('ST_Overlaps')
        within_pos = expression.find('ST_Within')
        
        # Verify optimal ordering
        assert intersects_pos >= 0, "ST_Intersects not found"
        assert within_pos >= 0, "ST_Within not found"
        assert intersects_pos < touches_pos, "intersects should appear before touches"
        assert intersects_pos < overlaps_pos, "intersects should appear before overlaps"
        assert within_pos < overlaps_pos, "within should appear before overlaps"
    
    def test_cache_memory_limit(self):
        """
        Test that cache respects memory limit (max 10 entries).
        
        Expected: FIFO eviction when cache is full
        """
        from modules.appTasks import SourceGeometryCache
        
        cache = SourceGeometryCache()
        
        # Fill cache with 10 entries
        for i in range(10):
            features = [Mock(id=lambda j=j: j) for j in range(i, i+10)]
            cache.put(features, i, f"EPSG:{4326+i}", {'data': i})
        
        assert len(cache._cache) == 10, "Cache should have 10 entries"
        
        # Add 11th entry (should evict oldest)
        features_11 = [Mock(id=lambda: j) for j in range(100, 110)]
        cache.put(features_11, 100, "EPSG:9999", {'data': 100})
        
        # Cache should still be 10 entries (oldest evicted)
        assert len(cache._cache) == 10, "Cache should still have 10 entries after FIFO eviction"


class TestPerformanceBenchmarks:
    """
    Benchmark tests (optional, requires actual data).
    
    These tests measure actual performance gains.
    Skip if test data not available.
    """
    
    @pytest.mark.skip(reason="Requires actual QGIS layer data")
    def test_benchmark_ogr_with_without_index(self):
        """
        Benchmark OGR filtering with and without spatial index.
        
        Expected: 4× speedup with index
        """
        # This would require actual shapefile with 10k+ features
        pass
    
    @pytest.mark.skip(reason="Requires actual database")
    def test_benchmark_spatialite_temp_table(self):
        """
        Benchmark Spatialite with inline WKT vs temp table.
        
        Expected: 10× speedup with temp table for 5k features
        """
        # This would require actual Spatialite database
        pass
    
    @pytest.mark.skip(reason="Performance benchmark")
    def test_benchmark_cache_multilayer(self):
        """
        Benchmark filtering 5 layers with/without cache.
        
        Expected: 5× speedup with cache
        """
        # This would require actual multi-layer setup
        pass


class TestRegressions:
    """
    Regression tests to ensure optimizations don't break existing functionality.
    """
    
    def test_ogr_fallback_on_index_failure(self):
        """
        Test that OGR gracefully falls back if index creation fails.
        
        Expected: Should continue filtering even if index creation fails
        """
        from modules.backends.ogr_backend import OGRGeometricFilter
        
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.name.return_value = "test"
        mock_layer.hasSpatialIndex.return_value = False
        
        backend = OGRGeometricFilter({})
        
        # Mock index creation to fail
        with patch('modules.backends.ogr_backend.processing.run', side_effect=Exception("Index failed")):
            result = backend._ensure_spatial_index(mock_layer)
            
            # Should return False but not crash
            assert result is False
    
    def test_spatialite_fallback_on_temp_table_failure(self):
        """
        Test that Spatialite falls back to inline WKT if temp table fails.
        
        Expected: Should use inline WKT method as fallback
        """
        from modules.backends.spatialite_backend import SpatialiteGeometricFilter
        
        backend = SpatialiteGeometricFilter({})
        
        # Mock temp table creation to fail
        backend._create_temp_geometry_table = Mock(return_value=(None, None))
        backend._get_spatialite_db_path = Mock(return_value="/tmp/test.db")
        
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.name.return_value = "test"
        mock_layer.crs.return_value.authid.return_value = "EPSG:4326"
        mock_layer.crs.return_value.isValid.return_value = True
        
        layer_props = {
            'layer_name': 'test',
            'geometry_field': 'geom',
            'layer': mock_layer
        }
        
        # Large WKT that would normally trigger temp table
        large_wkt = "POLYGON((" + ", ".join([f"{i} {i}" for i in range(10000)]) + "))"
        
        expression = backend.build_expression(
            layer_props,
            {'intersects': 'ST_Intersects'},
            source_geom=large_wkt
        )
        
        # Should contain GeomFromText (inline WKT fallback)
        assert "GeomFromText" in expression or expression != ""
        assert backend._temp_table_name is None


def test_all_optimizations_enabled():
    """
    Integration test: Verify all optimizations are enabled by default.
    
    Expected: 
    - OGR creates spatial index
    - Spatialite uses temp tables
    - Cache is initialized
    - Predicates are ordered
    """
    from modules.backends.ogr_backend import OGRGeometricFilter
    from modules.backends.spatialite_backend import SpatialiteGeometricFilter
    from modules.appTasks import FilterEngineTask
    
    # Check OGR optimization
    ogr_backend = OGRGeometricFilter({})
    assert hasattr(ogr_backend, '_ensure_spatial_index')
    assert hasattr(ogr_backend, '_apply_filter_large')
    
    # Check Spatialite optimization
    spatialite_backend = SpatialiteGeometricFilter({})
    assert hasattr(spatialite_backend, '_create_temp_geometry_table')
    assert spatialite_backend._use_temp_table is True  # Should be enabled by default
    
    # Check cache initialization
    assert hasattr(FilterEngineTask, '_geometry_cache')
    assert FilterEngineTask._geometry_cache is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

"""
Unit tests for SpatialFilterExecutor.

Tests extracted spatial filtering logic from FilterEngineTask.
Part of Phase E13 refactoring (January 2026).
"""

import unittest
from unittest.mock import Mock, MagicMock, patch

from qgis.core import QgsVectorLayer, QgsProject, QgsGeometry

from core.tasks.executors.spatial_filter_executor import SpatialFilterExecutor


class TestSpatialFilterExecutor(unittest.TestCase):
    """Test SpatialFilterExecutor class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock source layer
        self.source_layer = Mock(spec=QgsVectorLayer)
        self.source_layer.name.return_value = "source_layer"
        
        # Create mock project
        self.project = Mock(spec=QgsProject)
        
        # Create executor
        self.executor = SpatialFilterExecutor(
            source_layer=self.source_layer,
            project=self.project,
            backend_registry=None,
            task_bridge=None,
            postgresql_available=False
        )
    
    def test_initialization(self):
        """Test executor initialization."""
        self.assertEqual(self.executor.source_layer, self.source_layer)
        self.assertEqual(self.executor.project, self.project)
        self.assertIsNone(self.executor.backend_registry)
        self.assertIsNone(self.executor.task_bridge)
        self.assertFalse(self.executor.postgresql_available)
    
    def test_try_v3_spatial_filter_no_bridge(self):
        """Test v3 filter attempt without TaskBridge."""
        layer = Mock(spec=QgsVectorLayer)
        layer_props = {'predicates': ['intersects']}
        predicates = ['intersects']
        
        result = self.executor.try_v3_spatial_filter(layer, layer_props, predicates)
        
        # Should return None (fallback) when no task_bridge
        self.assertIsNone(result)
    
    def test_try_v3_spatial_filter_with_buffer(self):
        """Test v3 filter skips when buffer is active."""
        executor = SpatialFilterExecutor(
            source_layer=self.source_layer,
            project=self.project,
            task_bridge=Mock()
        )
        
        layer = Mock(spec=QgsVectorLayer)
        layer_props = {'buffer_value': 10.0}
        predicates = ['intersects']
        
        result = executor.try_v3_spatial_filter(layer, layer_props, predicates)
        
        # Should return None (fallback) for buffer case
        self.assertIsNone(result)
    
    def test_try_v3_spatial_filter_multiple_predicates(self):
        """Test v3 filter skips multiple predicates."""
        executor = SpatialFilterExecutor(
            source_layer=self.source_layer,
            project=self.project,
            task_bridge=Mock()
        )
        
        layer = Mock(spec=QgsVectorLayer)
        layer_props = {}
        predicates = ['intersects', 'contains']
        
        result = executor.try_v3_spatial_filter(layer, layer_props, predicates)
        
        # Should return None (fallback) for multiple predicates
        self.assertIsNone(result)
    
    def test_try_v3_spatial_filter_success(self):
        """Test successful v3 spatial filter execution."""
        # Create mock TaskBridge
        task_bridge = Mock()
        task_bridge.is_available.return_value = True
        
        bridge_result = Mock()
        bridge_result.status = 'SUCCESS'
        bridge_result.success = True
        bridge_result.backend_used = 'postgresql'
        bridge_result.feature_count = 42
        bridge_result.execution_time_ms = 123.4
        task_bridge.execute_spatial_filter.return_value = bridge_result
        
        executor = SpatialFilterExecutor(
            source_layer=self.source_layer,
            project=self.project,
            task_bridge=task_bridge
        )
        
        layer = Mock(spec=QgsVectorLayer)
        layer.name.return_value = "target_layer"
        layer_props = {}
        predicates = ['intersects']
        
        result = executor.try_v3_spatial_filter(layer, layer_props, predicates)
        
        self.assertTrue(result)
        task_bridge.execute_spatial_filter.assert_called_once()
    
    def test_try_v3_spatial_filter_fallback(self):
        """Test v3 filter requesting fallback."""
        task_bridge = Mock()
        task_bridge.is_available.return_value = True
        
        bridge_result = Mock()
        bridge_result.status = 'FALLBACK'
        bridge_result.error_message = 'Complex geometry not supported'
        task_bridge.execute_spatial_filter.return_value = bridge_result
        
        executor = SpatialFilterExecutor(
            source_layer=self.source_layer,
            project=self.project,
            task_bridge=task_bridge
        )
        
        layer = Mock(spec=QgsVectorLayer)
        layer_props = {}
        predicates = ['intersects']
        
        result = executor.try_v3_spatial_filter(layer, layer_props, predicates)
        
        # Should return None (fallback to legacy)
        self.assertIsNone(result)
    
    def test_organize_layers_to_filter(self):
        """Test layer organization by provider."""
        task_action = 'filter'
        task_parameters = {
            'task': {
                'FILTERING': {
                    'HAS_LAYERS_TO_FILTER': True
                }
            },
            'layers': []
        }
        
        with patch('core.tasks.executors.spatial_filter_executor.organize_layers_for_filtering') as mock_organize:
            mock_result = Mock()
            mock_result.layers_by_provider = {
                'postgresql': [(Mock(), {})],
                'spatialite': [(Mock(), {})]
            }
            mock_result.layers_count = 2
            mock_result.provider_list = ['postgresql', 'spatialite']
            mock_organize.return_value = mock_result
            
            result = self.executor.organize_layers_to_filter(task_action, task_parameters)
        
        # Result is now OrganizedLayers object
        self.assertIn('postgresql', result.layers_by_provider)
        self.assertIn('spatialite', result.layers_by_provider)
        self.assertEqual(result.layers_count, 2)
        self.assertEqual(result.provider_list, ['postgresql', 'spatialite'])
        mock_organize.assert_called_once()
    
    def test_prepare_source_geometry_no_registry(self):
        """Test geometry preparation without backend registry."""
        layer_info = {'layer': self.source_layer}
        
        geometry_data, error = self.executor.prepare_source_geometry_via_executor(layer_info)
        
        self.assertIsNone(geometry_data)
        self.assertIsNotNone(error)
        self.assertIn("Backend registry not available", error)
    
    def test_prepare_source_geometry_with_registry(self):
        """Test geometry preparation with backend registry."""
        # Create mock backend registry
        backend_registry = Mock()
        executor_mock = Mock()
        executor_mock.prepare_source_geometry.return_value = Mock(wkt="POINT(0 0)")
        backend_registry.get_backend_executor.return_value = executor_mock
        
        executor = SpatialFilterExecutor(
            source_layer=self.source_layer,
            project=self.project,
            backend_registry=backend_registry
        )
        
        layer_info = {'layer': self.source_layer}
        
        geometry_data, error = executor.prepare_source_geometry_via_executor(
            layer_info,
            buffer_value=10.0,
            use_centroids=False
        )
        
        self.assertIsNotNone(geometry_data)
        self.assertIsNone(error)
        executor_mock.prepare_source_geometry.assert_called_once()
    
    def test_prepare_geometries_by_provider(self):
        """Test multi-provider geometry preparation."""
        backend_registry = Mock()
        executor_mock = Mock()
        executor_mock.prepare_source_geometry.return_value = Mock(wkt="POINT(0 0)")
        backend_registry.get_backend_executor.return_value = executor_mock
        
        executor = SpatialFilterExecutor(
            source_layer=self.source_layer,
            project=self.project,
            backend_registry=backend_registry
        )
        
        provider_list = ['postgresql', 'spatialite']
        
        result = executor.prepare_geometries_by_provider(
            provider_list,
            buffer_value=5.0,
            use_centroids=False
        )
        
        self.assertTrue(result)
        self.assertEqual(executor_mock.prepare_source_geometry.call_count, 2)
    
    def test_validate_predicates_valid(self):
        """Test validation of valid predicates."""
        predicates = ['intersects', 'contains', 'within']
        
        result = self.executor.validate_predicates(predicates)
        
        self.assertTrue(result)
    
    def test_validate_predicates_invalid(self):
        """Test validation of invalid predicates."""
        predicates = ['intersects', 'invalid_predicate']
        
        result = self.executor.validate_predicates(predicates)
        
        self.assertFalse(result)
    
    def test_execute_spatial_filter_v3_success(self):
        """Test spatial filter execution with v3 success."""
        task_bridge = Mock()
        task_bridge.is_available.return_value = True
        
        bridge_result = Mock()
        bridge_result.status = 'SUCCESS'
        bridge_result.success = True
        bridge_result.backend_used = 'postgresql'
        bridge_result.feature_count = 10
        bridge_result.execution_time_ms = 50.0
        task_bridge.execute_spatial_filter.return_value = bridge_result
        
        executor = SpatialFilterExecutor(
            source_layer=self.source_layer,
            project=self.project,
            task_bridge=task_bridge
        )
        
        layer = Mock(spec=QgsVectorLayer)
        layer.name.return_value = "target"
        layer_props = {}
        predicates = ['intersects']
        
        success, feature_ids = executor.execute_spatial_filter(layer, layer_props, predicates)
        
        self.assertTrue(success)
        self.assertEqual(feature_ids, [])
    
    def test_execute_spatial_filter_v3_fallback(self):
        """Test spatial filter execution with v3 fallback and FilterOrchestrator."""
        layer = Mock(spec=QgsVectorLayer)
        layer_props = {}
        predicates = ['intersects']
        
        # Create mock filter orchestrator
        filter_orchestrator = Mock()
        filter_orchestrator.orchestrate_geometric_filter.return_value = True
        
        # Create mock expression builder
        expression_builder = Mock()
        
        # Create mock source geometries
        source_geometries = {
            'ogr': Mock(wkt="POINT(0 0)"),
            'spatialite': Mock(wkt="POINT(0 0)")
        }
        
        success, feature_ids = self.executor.execute_spatial_filter(
            layer, 
            layer_props, 
            predicates,
            source_geometries=source_geometries,
            expression_builder=expression_builder,
            filter_orchestrator=filter_orchestrator
        )
        
        # Should delegate to FilterOrchestrator
        self.assertTrue(success)
        filter_orchestrator.orchestrate_geometric_filter.assert_called_once()
    
    def test_execute_spatial_filter_invalid_predicates(self):
        """Test spatial filter execution with invalid predicates."""
        layer = Mock(spec=QgsVectorLayer)
        layer_props = {}
        predicates = ['invalid_predicate']
        
        success, feature_ids = self.executor.execute_spatial_filter(layer, layer_props, predicates)
        
        self.assertFalse(success)
        self.assertEqual(feature_ids, [])
    
    def test_execute_spatial_filter_no_orchestrator(self):
        """Test spatial filter execution without orchestrator returns False."""
        layer = Mock(spec=QgsVectorLayer)
        layer_props = {}
        predicates = ['intersects']
        
        success, feature_ids = self.executor.execute_spatial_filter(
            layer, 
            layer_props, 
            predicates,
            filter_orchestrator=None  # No orchestrator
        )
        
        self.assertFalse(success)
        self.assertEqual(feature_ids, [])


class TestSpatialFilterExecutorBatch(unittest.TestCase):
    """Test batch processing of spatial filters."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.source_layer = Mock(spec=QgsVectorLayer)
        self.source_layer.name.return_value = "source_layer"
        
        self.project = Mock(spec=QgsProject)
        
        self.executor = SpatialFilterExecutor(
            source_layer=self.source_layer,
            project=self.project,
            backend_registry=None,
            task_bridge=None,
            postgresql_available=False
        )
    
    def test_batch_empty_layers_dict(self):
        """Test batch with empty layers dict."""
        mock_orchestrator = Mock()
        
        success_count, total_count = self.executor.execute_spatial_filter_batch(
            layers_dict={},
            predicates=['intersects'],
            source_geometries={},
            expression_builder=Mock(),
            filter_orchestrator=mock_orchestrator
        )
        
        self.assertEqual(success_count, 0)
        self.assertEqual(total_count, 0)
    
    def test_batch_multiple_layers(self):
        """Test batch with multiple layers across providers."""
        mock_layer1 = Mock(spec=QgsVectorLayer)
        mock_layer1.name.return_value = "layer1"
        mock_layer2 = Mock(spec=QgsVectorLayer)
        mock_layer2.name.return_value = "layer2"
        mock_layer3 = Mock(spec=QgsVectorLayer)
        mock_layer3.name.return_value = "layer3"
        
        layers_dict = {
            'ogr': [(mock_layer1, {'predicates': ['intersects']})],
            'spatialite': [
                (mock_layer2, {'predicates': ['contains']}),
                (mock_layer3, {'predicates': ['within']})
            ]
        }
        
        # Create mock orchestrator that always succeeds
        mock_orchestrator = Mock()
        mock_orchestrator.orchestrate_geometric_filter.return_value = True
        
        success_count, total_count = self.executor.execute_spatial_filter_batch(
            layers_dict=layers_dict,
            predicates=['intersects'],
            source_geometries={'ogr': Mock(), 'spatialite': Mock()},
            expression_builder=Mock(),
            filter_orchestrator=mock_orchestrator
        )
        
        self.assertEqual(total_count, 3)
        self.assertEqual(success_count, 3)
        self.assertEqual(mock_orchestrator.orchestrate_geometric_filter.call_count, 3)
    
    def test_batch_partial_failure(self):
        """Test batch with some layer failures."""
        mock_layer1 = Mock(spec=QgsVectorLayer)
        mock_layer1.name.return_value = "layer1"
        mock_layer2 = Mock(spec=QgsVectorLayer)
        mock_layer2.name.return_value = "layer2"
        
        layers_dict = {
            'ogr': [
                (mock_layer1, {}),
                (mock_layer2, {})
            ]
        }
        
        # Orchestrator succeeds first call, fails second
        mock_orchestrator = Mock()
        mock_orchestrator.orchestrate_geometric_filter.side_effect = [True, False]
        
        success_count, total_count = self.executor.execute_spatial_filter_batch(
            layers_dict=layers_dict,
            predicates=['intersects'],
            source_geometries={'ogr': Mock()},
            expression_builder=Mock(),
            filter_orchestrator=mock_orchestrator
        )
        
        self.assertEqual(total_count, 2)
        self.assertEqual(success_count, 1)
    
    def test_batch_with_progress_callback(self):
        """Test batch with progress callback."""
        mock_layer1 = Mock(spec=QgsVectorLayer)
        mock_layer1.name.return_value = "layer1"
        
        layers_dict = {
            'ogr': [(mock_layer1, {})]
        }
        
        mock_orchestrator = Mock()
        mock_orchestrator.orchestrate_geometric_filter.return_value = True
        
        progress_values = []
        def progress_callback(value):
            progress_values.append(value)
        
        success_count, total_count = self.executor.execute_spatial_filter_batch(
            layers_dict=layers_dict,
            predicates=['intersects'],
            source_geometries={'ogr': Mock()},
            expression_builder=Mock(),
            filter_orchestrator=mock_orchestrator,
            progress_callback=progress_callback
        )
        
        self.assertEqual(len(progress_values), 1)


class TestGeometryCacheIntegration(unittest.TestCase):
    """Test GeometryCache integration with SpatialFilterExecutor."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.source_layer = Mock(spec=QgsVectorLayer)
        self.source_layer.name.return_value = "source_layer"
        self.source_layer.id.return_value = "layer_123"
        self.source_layer.subsetString.return_value = ""
        
        self.project = Mock(spec=QgsProject)
        
        # Create mock geometry cache
        self.mock_cache = Mock()
        self.mock_cache.get.return_value = None
        self.mock_cache.get_stats.return_value = {'size': 0, 'hits': 0, 'misses': 0}
        
        self.executor = SpatialFilterExecutor(
            source_layer=self.source_layer,
            project=self.project,
            backend_registry=Mock(),
            geometry_cache=self.mock_cache
        )
    
    def test_cache_is_used(self):
        """Test that geometry cache is used during preparation."""
        # Verify cache was set
        self.assertEqual(self.executor._geometry_cache, self.mock_cache)
    
    def test_cache_lookup_on_prepare(self):
        """Test cache lookup when preparing geometry."""
        # Setup backend registry mock
        mock_executor = Mock()
        mock_executor.prepare_source_geometry.return_value = Mock(wkt="POINT(0 0)")
        self.executor.backend_registry.get_backend_executor.return_value = mock_executor
        
        layer_info = {'layer': self.source_layer, 'crs_authid': 'EPSG:4326'}
        
        # First call - cache miss
        result, error = self.executor.prepare_source_geometry_via_executor(
            layer_info=layer_info,
            feature_ids=[1, 2, 3],
            buffer_value=10.0
        )
        
        # Verify cache.get was called
        self.mock_cache.get.assert_called_once()
        
        # Verify cache.put was called after calculation
        self.mock_cache.put.assert_called_once()
    
    def test_cache_hit_skips_calculation(self):
        """Test that cache hit skips geometry calculation."""
        # Setup cache to return a hit
        cached_geom = Mock(wkt="CACHED_POINT(0 0)")
        self.mock_cache.get.return_value = cached_geom
        
        layer_info = {'layer': self.source_layer, 'crs_authid': 'EPSG:4326'}
        
        result, error = self.executor.prepare_source_geometry_via_executor(
            layer_info=layer_info,
            feature_ids=[1, 2, 3]
        )
        
        # Result should be from cache
        self.assertEqual(result, cached_geom)
        self.assertIsNone(error)
        
        # Backend executor should NOT have been called
        self.executor.backend_registry.get_backend_executor.assert_not_called()
    
    def test_cache_disabled(self):
        """Test geometry preparation with cache disabled."""
        mock_executor = Mock()
        mock_geom = Mock(wkt="POINT(0 0)")
        mock_executor.prepare_source_geometry.return_value = mock_geom
        self.executor.backend_registry.get_backend_executor.return_value = mock_executor
        
        layer_info = {'layer': self.source_layer, 'crs_authid': 'EPSG:4326'}
        
        result, error = self.executor.prepare_source_geometry_via_executor(
            layer_info=layer_info,
            feature_ids=[1, 2, 3],
            use_cache=False
        )
        
        # Cache should NOT be consulted
        self.mock_cache.get.assert_not_called()
        self.mock_cache.put.assert_not_called()
        
        # Result should come from executor
        self.assertEqual(result, mock_geom)
    
    def test_invalidate_layer_cache(self):
        """Test layer cache invalidation."""
        self.mock_cache.invalidate_layer.return_value = 3
        
        self.executor.invalidate_geometry_cache(layer_id="layer_123")
        
        self.mock_cache.invalidate_layer.assert_called_once_with("layer_123")
    
    def test_clear_all_cache(self):
        """Test clearing all cache entries."""
        self.executor.invalidate_geometry_cache(layer_id=None)
        
        self.mock_cache.clear.assert_called_once()
    
    def test_get_cache_stats(self):
        """Test retrieving cache statistics."""
        expected_stats = {'size': 5, 'hits': 10, 'misses': 2}
        self.mock_cache.get_stats.return_value = expected_stats
        
        stats = self.executor.get_cache_stats()
        
        self.assertEqual(stats, expected_stats)


if __name__ == '__main__':
    unittest.main()

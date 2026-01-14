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
            mock_organize.return_value = mock_result
            
            result = self.executor.organize_layers_to_filter(task_action, task_parameters)
        
        self.assertIn('postgresql', result)
        self.assertIn('spatialite', result)
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
        """Test spatial filter execution with v3 fallback."""
        layer = Mock(spec=QgsVectorLayer)
        layer_props = {}
        predicates = ['intersects']
        
        success, feature_ids = self.executor.execute_spatial_filter(layer, layer_props, predicates)
        
        # Should use legacy code (TODO Phase E13 Step 7)
        self.assertFalse(success)
        self.assertEqual(feature_ids, [])


if __name__ == '__main__':
    unittest.main()

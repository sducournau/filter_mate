"""
Unit tests for BackendExpressionBuilder service (Phase 14.1)

Tests validate that the extracted service behaves identically to the original
_build_backend_expression method in FilterEngineTask.

Author: Murat (Tea) - BMAD Test Architect
Date: January 12, 2026
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import sys
import os

# Add parent directory to path for imports
test_dir = os.path.dirname(os.path.abspath(__file__))
plugin_dir = os.path.dirname(test_dir)
sys.path.insert(0, plugin_dir)

# Mock problematic imports BEFORE importing the service
sys.modules['infrastructure'] = MagicMock()
sys.modules['infrastructure.logging'] = MagicMock()
sys.modules['config'] = MagicMock()
sys.modules['config.config'] = MagicMock()

# Create a mock logger
mock_logger = MagicMock()
sys.modules['infrastructure.logging'].setup_logger = MagicMock(return_value=mock_logger)

# Mock ENV_VARS
sys.modules['config.config'].ENV_VARS = {}

# Mock source_filter_builder functions
sys.modules['core.filter'] = MagicMock()
sys.modules['core.filter.source_filter_builder'] = MagicMock()

# Mock backend classes
sys.modules['adapters.backends'] = MagicMock()
sys.modules['adapters.backends.postgresql_backend'] = MagicMock()

# Now we can import - directly from file to avoid core.__init__.py circular imports
import importlib.util
spec = importlib.util.spec_from_file_location(
    "backend_expression_builder",
    os.path.join(plugin_dir, "core", "services", "backend_expression_builder.py")
)
backend_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend_module)

BackendExpressionBuilder = backend_module.BackendExpressionBuilder
create_expression_builder = backend_module.create_expression_builder


class TestBackendExpressionBuilderCreation(unittest.TestCase):
    """Test builder creation and initialization."""
    
    def test_create_expression_builder_factory(self):
        """Test factory function creates builder correctly."""
        source_layer = Mock()
        task_parameters = {"task": {}, "filtering": {}}
        expr_cache = Mock()
        format_callback = Mock()
        thresholds_callback = Mock()
        
        builder = create_expression_builder(
            source_layer=source_layer,
            task_parameters=task_parameters,
            expr_cache=expr_cache,
            format_pk_values_callback=format_callback,
            get_optimization_thresholds_callback=thresholds_callback
        )
        
        self.assertIsInstance(builder, BackendExpressionBuilder)
        self.assertEqual(builder.source_layer, source_layer)
        self.assertEqual(builder.task_parameters, task_parameters)
        self.assertEqual(builder.expr_cache, expr_cache)
    
    def test_builder_initialization_state(self):
        """Test builder initializes with correct default state."""
        builder = BackendExpressionBuilder(
            source_layer=Mock(),
            task_parameters={},
            expr_cache=None
        )
        
        # Check default values
        self.assertIsNone(builder.param_buffer_value)
        self.assertIsNone(builder.param_buffer_expression)
        self.assertFalse(builder.param_use_centroids_distant_layers)
        self.assertFalse(builder.param_use_centroids_source_layer)
        self.assertEqual(builder.current_predicates, [])
        self.assertEqual(builder.approved_optimizations, {})
        self.assertFalse(builder.auto_apply_optimizations)
        self.assertEqual(builder._source_selection_mvs, [])


class TestBackendExpressionBuilderPostgreSQLSourceFilter(unittest.TestCase):
    """Test PostgreSQL source filter generation logic."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.source_layer = Mock()
        self.source_layer.subsetString.return_value = ""
        self.task_parameters = {"task": {}, "filtering": {}}
        
        self.builder = BackendExpressionBuilder(
            source_layer=self.source_layer,
            task_parameters=self.task_parameters
        )
    
    @patch('core.services.backend_expression_builder.should_skip_source_subset')
    def test_no_source_filter_when_no_subset(self, mock_skip):
        """Test no source filter when source layer has no subset."""
        mock_skip.return_value = False
        
        source_filter = self.builder._get_source_filter_for_postgresql()
        
        self.assertIsNone(source_filter)
    
    @patch('core.services.backend_expression_builder.should_skip_source_subset')
    def test_use_subset_when_available(self, mock_skip):
        """Test uses source subset when available and not skipped."""
        self.source_layer.subsetString.return_value = "status = 'active'"
        mock_skip.return_value = False
        
        source_filter = self.builder._get_source_filter_for_postgresql()
        
        self.assertEqual(source_filter, "status = 'active'")
    
    @patch('core.services.backend_expression_builder.should_skip_source_subset')
    @patch('core.services.backend_expression_builder.sfb_get_primary_key_field')
    @patch('core.services.backend_expression_builder.extract_feature_ids')
    @patch('core.services.backend_expression_builder.sfb_get_source_table_name')
    @patch('core.services.backend_expression_builder.build_source_filter_inline')
    def test_task_features_override_subset(
        self, mock_inline, mock_table_name, mock_extract, mock_pk, mock_skip
    ):
        """Test task_features take priority over source subset."""
        # Setup
        self.source_layer.subsetString.return_value = "old_filter = true"
        mock_skip.return_value = False
        mock_pk.return_value = "id"
        mock_extract.return_value = [1, 2, 3]
        mock_table_name.return_value = "test_table"
        mock_inline.return_value = "id IN (1,2,3)"
        
        # Add task_features to parameters
        self.task_parameters["task"]["features"] = [Mock(), Mock(), Mock()]
        
        source_filter = self.builder._get_source_filter_for_postgresql()
        
        # Should use task_features, not the subset
        self.assertEqual(source_filter, "id IN (1,2,3)")
        mock_inline.assert_called_once()


class TestBackendExpressionBuilderMaterializedViews(unittest.TestCase):
    """Test MV creation logic for large selections."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.source_layer = Mock()
        self.task_parameters = {"task": {"features": []}, "filtering": {}}
        
        def mock_get_thresholds():
            return {'source_mv_fid_threshold': 500}
        
        self.builder = BackendExpressionBuilder(
            source_layer=self.source_layer,
            task_parameters=self.task_parameters,
            get_optimization_thresholds_callback=mock_get_thresholds
        )
        self.builder.param_source_geom = "geom"
    
    @patch('core.services.backend_expression_builder.build_source_filter_inline')
    def test_small_selection_uses_inline_filter(self, mock_inline):
        """Test selections under threshold use inline IN clause."""
        fids = list(range(100))  # 100 features < 500 threshold
        pk_field = "id"
        source_table = "test_table"
        mock_inline.return_value = "id IN (...)"
        
        result = self.builder._build_filter_with_mv(fids, pk_field, source_table, 500)
        
        # Should NOT create MV, should call inline builder
        mock_inline.assert_called_once()
        self.assertEqual(len(self.builder._source_selection_mvs), 0)
    
    @patch('core.services.backend_expression_builder.PostgreSQLGeometricFilter')
    @patch('core.services.backend_expression_builder.build_source_filter_with_mv')
    def test_large_selection_creates_mv(self, mock_mv_filter, mock_pg_backend_class):
        """Test selections over threshold create MV."""
        # Setup
        fids = list(range(1000))  # 1000 features > 500 threshold
        pk_field = "id"
        source_table = "test_table"
        
        mock_backend = Mock()
        mock_backend.create_source_selection_mv.return_value = "mv_temp_123"
        mock_pg_backend_class.return_value = mock_backend
        mock_mv_filter.return_value = "EXISTS (SELECT 1 FROM mv_temp_123 ...)"
        
        result = self.builder._build_filter_with_mv(fids, pk_field, source_table, 500)
        
        # Should create MV
        mock_backend.create_source_selection_mv.assert_called_once()
        mock_mv_filter.assert_called_once()
        
        # MV should be tracked for cleanup
        self.assertIn("mv_temp_123", self.builder._source_selection_mvs)
        self.assertEqual(result, "EXISTS (SELECT 1 FROM mv_temp_123 ...)")


class TestBackendExpressionBuilderCaching(unittest.TestCase):
    """Test expression caching behavior."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.source_layer = Mock()
        self.expr_cache = Mock()
        self.task_parameters = {"task": {}, "filtering": {}}
        
        self.builder = BackendExpressionBuilder(
            source_layer=self.source_layer,
            task_parameters=self.task_parameters,
            expr_cache=self.expr_cache
        )
        
        # Set required attributes
        self.builder.current_predicates = ["intersects"]
        self.builder.param_buffer_value = 10.0
    
    def test_cache_key_computation(self):
        """Test cache key is computed correctly."""
        layer = Mock()
        layer.id.return_value = "layer_123"
        source_geom = Mock()
        
        self.expr_cache.compute_source_hash.return_value = "hash_abc"
        self.expr_cache.get_cache_key.return_value = "cache_key_xyz"
        
        backend = Mock()
        backend.get_backend_name.return_value = "PostgreSQL"
        
        cache_key = self.builder._compute_cache_key(
            layer, source_geom, "postgresql", source_filter=None
        )
        
        self.assertEqual(cache_key, "cache_key_xyz")
        self.expr_cache.get_cache_key.assert_called_once()
    
    def test_cache_hit_returns_cached_expression(self):
        """Test cache hit returns cached expression without building new one."""
        layer = Mock()
        layer.id.return_value = "layer_123"
        layer.name.return_value = "Test Layer"
        layer_props = {"layer": layer}
        source_geom = Mock()
        backend = Mock()
        backend.get_backend_name.return_value = "PostgreSQL"
        
        # Setup cache to return hit
        self.expr_cache.compute_source_hash.return_value = "hash"
        self.expr_cache.get_cache_key.return_value = "key"
        self.expr_cache.get.return_value = "CACHED EXPRESSION"
        
        self.builder.current_predicates = ["intersects"]
        result = self.builder.build(backend, layer_props, source_geom)
        
        # Should return cached expression without calling backend
        self.assertEqual(result, "CACHED EXPRESSION")
        backend.build_expression.assert_not_called()


class TestBackendExpressionBuilderStateTransfer(unittest.TestCase):
    """Test that task state is correctly transferred to builder."""
    
    def test_all_state_attributes_transferable(self):
        """Test all required state attributes can be set on builder."""
        builder = BackendExpressionBuilder(
            source_layer=Mock(),
            task_parameters={}
        )
        
        # All attributes that need to be transferred from FilterEngineTask
        required_attributes = [
            'param_buffer_value',
            'param_buffer_expression',
            'param_use_centroids_distant_layers',
            'param_use_centroids_source_layer',
            'param_source_table',
            'param_source_geom',
            'current_predicates',
            'approved_optimizations',
            'auto_apply_optimizations',
            'spatialite_source_geom',
            'ogr_source_geom',
            'source_layer_crs_authid',
        ]
        
        for attr in required_attributes:
            self.assertTrue(
                hasattr(builder, attr),
                f"Builder missing required attribute: {attr}"
            )


class TestBackendExpressionBuilderIntegration(unittest.TestCase):
    """Integration tests for full build() workflow."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.source_layer = Mock()
        self.source_layer.subsetString.return_value = ""
        self.task_parameters = {"task": {}, "filtering": {}}
        
        self.builder = BackendExpressionBuilder(
            source_layer=self.source_layer,
            task_parameters=self.task_parameters,
            expr_cache=None
        )
        
        # Set required state
        self.builder.current_predicates = ["intersects"]
        self.builder.param_buffer_value = None
        self.builder.param_buffer_expression = None
        self.builder.param_use_centroids_distant_layers = False
        self.builder.param_use_centroids_source_layer = False
    
    @patch('core.services.backend_expression_builder.should_skip_source_subset')
    def test_build_calls_backend_with_correct_parameters(self, mock_skip):
        """Test build() calls backend.build_expression with correct params."""
        mock_skip.return_value = False
        
        # Setup backend
        backend = Mock()
        backend.get_backend_name.return_value = "PostgreSQL"
        backend.build_expression.return_value = "ST_Intersects(geom, ST_GeomFromText(...))"
        
        layer = Mock()
        layer.id.return_value = "layer_123"
        layer_props = {"layer": layer}
        source_geom = Mock()
        
        result = self.builder.build(backend, layer_props, source_geom)
        
        # Verify backend was called
        backend.build_expression.assert_called_once()
        call_kwargs = backend.build_expression.call_args[1]
        
        self.assertEqual(call_kwargs['layer_props'], layer_props)
        self.assertEqual(call_kwargs['predicates'], ["intersects"])
        self.assertEqual(call_kwargs['source_geom'], source_geom)
        self.assertIn('source_filter', call_kwargs)
        
        self.assertEqual(result, "ST_Intersects(geom, ST_GeomFromText(...))")
    
    def test_build_handles_ogr_fallback_sentinel(self):
        """Test build() handles __USE_OGR_FALLBACK__ sentinel correctly."""
        backend = Mock()
        backend.get_backend_name.return_value = "Spatialite"
        backend.build_expression.return_value = "__USE_OGR_FALLBACK__"
        
        layer_props = {"layer": Mock()}
        source_geom = Mock()
        
        result = self.builder.build(backend, layer_props, source_geom)
        
        # Should return None to trigger fallback
        self.assertIsNone(result)
    
    def test_mv_cleanup_collection(self):
        """Test that created MVs are collected for cleanup."""
        # This would require more complex mocking of the MV creation path
        # For now, test the API exists
        builder = BackendExpressionBuilder(
            source_layer=Mock(),
            task_parameters={}
        )
        
        builder._source_selection_mvs.append("mv_test_1")
        builder._source_selection_mvs.append("mv_test_2")
        
        mvs = builder.get_created_mvs()
        self.assertEqual(mvs, ["mv_test_1", "mv_test_2"])
        
        builder.clear_created_mvs()
        self.assertEqual(builder._source_selection_mvs, [])


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)

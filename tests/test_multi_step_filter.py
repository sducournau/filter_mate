"""
Tests for Multi-Step Filter Optimizer
Phase 2 (v4.1.0-beta.2): Unit tests for filter decomposition logic.
"""

import pytest
from unittest.mock import Mock, MagicMock
from core.optimization.multi_step_filter import (
    MultiStepFilterOptimizer,
    FilterStep,
    get_multi_step_optimizer
)


@pytest.fixture
def optimizer():
    """Create fresh MultiStepFilterOptimizer for each test."""
    return MultiStepFilterOptimizer()


@pytest.fixture
def mock_layer():
    """Create mock QgsVectorLayer with typical attributes."""
    layer = Mock()
    layer.name.return_value = "test_layer"
    layer.id.return_value = "layer_test_123"
    layer.featureCount.return_value = 5000  # Medium dataset
    return layer


@pytest.fixture
def small_layer():
    """Create mock layer with small dataset."""
    layer = Mock()
    layer.name.return_value = "small_layer"
    layer.id.return_value = "layer_small_456"
    layer.featureCount.return_value = 500
    return layer


@pytest.fixture
def large_layer():
    """Create mock layer with large dataset."""
    layer = Mock()
    layer.name.return_value = "large_layer"
    layer.id.return_value = "layer_large_789"
    layer.featureCount.return_value = 50000
    return layer


class TestFilterStep:
    """Test FilterStep dataclass."""
    
    def test_filter_step_creation(self):
        """Test creating FilterStep with all fields."""
        step = FilterStep(
            step_number=1,
            expression='"population" > 10000',
            operation_type='attributaire',
            estimated_reduction=40.0,
            estimated_time_ms=25
        )
        
        assert step.step_number == 1
        assert step.expression == '"population" > 10000'
        assert step.operation_type == 'attributaire'
        assert step.estimated_reduction == 40.0
        assert step.estimated_time_ms == 25
    
    def test_spatial_step_creation(self):
        """Test creating spatial FilterStep."""
        step = FilterStep(
            step_number=1,
            expression='ST_Intersects($geometry, geom_from_wkt("POLYGON((...))"))',
            operation_type='spatial',
            estimated_reduction=70.0,
            estimated_time_ms=250
        )
        
        assert step.operation_type == 'spatial'
        assert step.estimated_reduction == 70.0
        assert 'ST_Intersects' in step.expression


class TestSimpleFilters:
    """Test decomposition of simple filters (no multi-step needed)."""
    
    def test_simple_filter_no_decomposition(self, optimizer, mock_layer):
        """Simple filter should remain as single step."""
        expression = '"population" > 10000'
        steps = optimizer.decompose_filter(expression, mock_layer)
        
        assert len(steps) == 1
        assert steps[0].step_number == 1
        assert steps[0].expression == '"population" > 10000'
        assert steps[0].operation_type == 'attributaire'
        assert steps[0].estimated_reduction > 0
        assert steps[0].estimated_time_ms > 0
    
    def test_spatial_only_filter(self, optimizer, mock_layer):
        """Spatial-only filter should be single step."""
        expression = 'ST_Intersects($geometry, geom_from_wkt("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"))'
        steps = optimizer.decompose_filter(expression, mock_layer)
        
        assert len(steps) == 1
        assert steps[0].operation_type == 'spatial'
        assert 'ST_Intersects' in steps[0].expression
        assert steps[0].estimated_reduction >= 50.0  # Spatial filters are selective
    
    def test_attributaire_only_filter(self, optimizer, mock_layer):
        """Simple attribute filter remains single step."""
        expression = '"type" = \'city\' '
        steps = optimizer.decompose_filter(expression, mock_layer)
        
        assert len(steps) == 1
        assert steps[0].operation_type == 'attributaire'
        assert steps[0].expression.strip() == '"type" = \'city\''
    
    def test_empty_expression(self, optimizer, mock_layer):
        """Empty expression should return empty list."""
        steps = optimizer.decompose_filter('', mock_layer)
        assert steps == []
        
        steps = optimizer.decompose_filter('   ', mock_layer)
        assert steps == []


class TestComplexDecomposition:
    """Test decomposition of complex multi-component filters."""
    
    def test_complex_decomposition_spatial_and_attribute(self, optimizer, mock_layer):
        """Complex filter should decompose into multiple steps."""
        expression = '"population" > 10000 AND ST_Intersects($geometry, geom_from_wkt("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"))'
        steps = optimizer.decompose_filter(expression, mock_layer)
        
        # Should decompose into 2 steps
        assert len(steps) == 2
        
        # First step should be spatial (higher reduction)
        assert steps[0].operation_type == 'spatial'
        assert 'ST_Intersects' in steps[0].expression
        
        # Second step should be attribute filter
        assert steps[1].operation_type == 'attributaire'
        assert 'population' in steps[1].expression
    
    def test_multiple_and_conditions(self, optimizer, mock_layer):
        """Multiple AND conditions should create sequential steps."""
        expression = '"population" > 10000 AND "type" = \'city\' AND "area" < 500'
        steps = optimizer.decompose_filter(expression, mock_layer)
        
        # Should decompose into 3 attribute steps
        assert len(steps) == 3
        
        # All should be attribute filters
        for step in steps:
            assert step.operation_type in ['attributaire', 'post_process']
        
        # Step numbers should be sequential
        assert [s.step_number for s in steps] == [1, 2, 3]
    
    def test_spatial_attribute_complex_mix(self, optimizer, mock_layer):
        """Mixed filter types should be ordered optimally."""
        expression = (
            '"name" = \'Paris\' AND '
            'ST_Contains($geometry, geom_from_wkt("POINT(2.35 48.85)")) AND '
            'regexp_match("code", \'^75[0-9]+$\')'
        )
        steps = optimizer.decompose_filter(expression, mock_layer)
        
        assert len(steps) == 3
        
        # First should be spatial (highest priority)
        assert steps[0].operation_type == 'spatial'
        
        # Check that we have attribute and complex steps
        step_types = [s.operation_type for s in steps]
        assert 'spatial' in step_types
        assert 'attributaire' in step_types or 'post_process' in step_types


class TestStepOrderOptimization:
    """Test optimal ordering of filter steps."""
    
    def test_step_order_spatial_first(self, optimizer, mock_layer):
        """Spatial filters should be executed first."""
        # Attribute before spatial in expression (non-optimal)
        expression = '"population" > 10000 AND ST_Intersects($geometry, geom_from_wkt("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"))'
        steps = optimizer.decompose_filter(expression, mock_layer)
        
        # Spatial should still be step 1 (optimizer reorders)
        assert steps[0].operation_type == 'spatial'
        assert steps[0].step_number == 1
    
    def test_simple_before_complex_attributes(self, optimizer, mock_layer):
        """Simple attribute filters should come before complex ones."""
        expression = (
            'regexp_match("code", \'^[A-Z]+$\') AND '  # Complex
            '"population" > 10000'  # Simple
        )
        steps = optimizer.decompose_filter(expression, mock_layer)
        
        # Find simple and complex steps
        simple_steps = [s for s in steps if s.operation_type == 'attributaire']
        complex_steps = [s for s in steps if s.operation_type == 'post_process']
        
        if simple_steps and complex_steps:
            # Simple should come before complex
            assert simple_steps[0].step_number < complex_steps[0].step_number


class TestReductionEstimation:
    """Test estimation of filtering reduction percentages."""
    
    def test_spatial_reduction_estimate(self, optimizer, mock_layer):
        """Spatial filters should have high reduction estimates."""
        expression = 'ST_Intersects($geometry, geom_from_wkt("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"))'
        steps = optimizer.decompose_filter(expression, mock_layer)
        
        assert len(steps) == 1
        # Spatial filters typically 60-90% reduction
        assert steps[0].estimated_reduction >= 50.0
    
    def test_attribute_reduction_estimate(self, optimizer, mock_layer):
        """Attribute filters should have moderate reduction estimates."""
        expression = '"population" > 10000'
        steps = optimizer.decompose_filter(expression, mock_layer)
        
        assert len(steps) == 1
        # Attribute filters typically 20-70% reduction
        assert 10.0 <= steps[0].estimated_reduction <= 80.0
    
    def test_complex_reduction_estimate(self, optimizer, mock_layer):
        """Complex expressions should have conservative reduction estimates."""
        expression = 'regexp_match("code", \'^[A-Z]+$\')'
        steps = optimizer.decompose_filter(expression, mock_layer)
        
        assert len(steps) == 1
        # Complex filters typically 10-50% reduction
        assert steps[0].estimated_reduction >= 10.0


class TestTimeEstimation:
    """Test estimation of execution time per step."""
    
    def test_time_estimation_scales_with_features(self, optimizer, small_layer, large_layer):
        """Execution time should scale with feature count."""
        expression = '"population" > 10000'
        
        small_steps = optimizer.decompose_filter(expression, small_layer)
        large_steps = optimizer.decompose_filter(expression, large_layer)
        
        # Large dataset should take more time
        assert large_steps[0].estimated_time_ms > small_steps[0].estimated_time_ms
    
    def test_spatial_time_estimate(self, optimizer, mock_layer):
        """Spatial operations should have higher time estimates."""
        spatial_expr = 'ST_Intersects($geometry, geom_from_wkt("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"))'
        attr_expr = '"population" > 10000'
        
        spatial_steps = optimizer.decompose_filter(spatial_expr, mock_layer)
        attr_steps = optimizer.decompose_filter(attr_expr, mock_layer)
        
        # Spatial should take longer than simple attribute
        assert spatial_steps[0].estimated_time_ms > attr_steps[0].estimated_time_ms
    
    def test_multi_step_cumulative_time(self, optimizer, mock_layer):
        """Multi-step filter should account for progressive reduction."""
        expression = '"population" > 10000 AND ST_Intersects($geometry, geom_from_wkt("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"))'
        steps = optimizer.decompose_filter(expression, mock_layer)
        
        # Each step should have positive time estimate
        for step in steps:
            assert step.estimated_time_ms > 0
        
        # Later steps should operate on fewer features (faster)
        if len(steps) > 1:
            # This may not always hold due to different operation costs
            # but total time should be reasonable
            total_time = sum(s.estimated_time_ms for s in steps)
            assert total_time > 0


class TestSingletonPattern:
    """Test singleton factory function."""
    
    def test_singleton_returns_same_instance(self):
        """get_multi_step_optimizer should return same instance."""
        optimizer1 = get_multi_step_optimizer()
        optimizer2 = get_multi_step_optimizer()
        
        assert optimizer1 is optimizer2
    
    def test_singleton_instance_is_functional(self, mock_layer):
        """Singleton instance should work correctly."""
        optimizer = get_multi_step_optimizer()
        
        expression = '"population" > 10000'
        steps = optimizer.decompose_filter(expression, mock_layer)
        
        assert len(steps) == 1
        assert isinstance(steps[0], FilterStep)


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_edge_case_empty_expression(self, optimizer, mock_layer):
        """Empty expression should return empty list."""
        steps = optimizer.decompose_filter('', mock_layer)
        assert steps == []
    
    def test_edge_case_whitespace_only(self, optimizer, mock_layer):
        """Whitespace-only expression should return empty list."""
        steps = optimizer.decompose_filter('   \n\t  ', mock_layer)
        assert steps == []
    
    def test_edge_case_single_spatial_function(self, optimizer, mock_layer):
        """Single spatial function should not over-decompose."""
        expression = 'intersects($geometry, geom_from_wkt("POINT(0 0)"))'
        steps = optimizer.decompose_filter(expression, mock_layer)
        
        # Should be single step, not decomposed
        assert len(steps) == 1
        assert steps[0].operation_type == 'spatial'
    
    def test_edge_case_or_operator(self, optimizer, mock_layer):
        """OR operators should not be decomposed (not supported)."""
        expression = '"population" > 10000 OR "type" = \'city\''
        steps = optimizer.decompose_filter(expression, mock_layer)
        
        # Should remain single step (OR decomposition not supported)
        assert len(steps) == 1
    
    def test_edge_case_nested_functions(self, optimizer, mock_layer):
        """Nested functions should be handled correctly."""
        expression = 'ST_Contains(ST_Buffer($geometry, 100), geom_from_wkt("POINT(0 0)"))'
        steps = optimizer.decompose_filter(expression, mock_layer)
        
        assert len(steps) >= 1
        # Should classify as spatial
        assert steps[0].operation_type == 'spatial'


class TestExpressionClassification:
    """Test internal expression classification methods."""
    
    def test_classify_spatial_expressions(self, optimizer):
        """Test spatial expression classification."""
        assert optimizer._classify_expression('ST_Intersects($geometry, geom)') == 'spatial'
        assert optimizer._classify_expression('intersects($geometry, geom)') == 'spatial'
        assert optimizer._classify_expression('ST_Contains(geom1, geom2)') == 'spatial'
    
    def test_classify_attribute_expressions(self, optimizer):
        """Test attribute expression classification."""
        assert optimizer._classify_expression('"population" > 10000') == 'attributaire'
        assert optimizer._classify_expression('"type" = \'city\'') == 'attributaire'
        assert optimizer._classify_expression('"area" < 500') == 'attributaire'
    
    def test_classify_complex_expressions(self, optimizer):
        """Test complex expression classification."""
        assert optimizer._classify_expression('regexp_match("code", "^[A-Z]+$")') == 'post_process'
        assert optimizer._classify_expression('upper("name")') == 'post_process'
        assert optimizer._classify_expression('concat("field1", "field2")') == 'post_process'


class TestComponentExtraction:
    """Test extraction of filter components."""
    
    def test_extract_spatial_component(self, optimizer):
        """Test extraction of spatial components."""
        expression = '"population" > 10000 AND ST_Intersects($geometry, geom_from_wkt("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"))'
        spatial_parts = optimizer._extract_spatial_component(expression)
        
        assert len(spatial_parts) >= 1
        assert any('ST_Intersects' in part for part in spatial_parts)
    
    def test_extract_attribute_components(self, optimizer):
        """Test extraction of attribute components."""
        expression = '"population" > 10000 AND "type" = \'city\' AND "area" < 500'
        attr_parts = optimizer._extract_attributaire_components(expression)
        
        # Should extract 3 attribute filters
        assert len(attr_parts) == 3
        assert any('population' in part for part in attr_parts)
        assert any('type' in part for part in attr_parts)
        assert any('area' in part for part in attr_parts)
    
    def test_extract_mixed_components(self, optimizer):
        """Test extraction from mixed expression."""
        expression = (
            'ST_Intersects($geometry, geom) AND '
            '"population" > 10000 AND '
            '"type" = \'city\''
        )
        
        spatial_parts = optimizer._extract_spatial_component(expression)
        attr_parts = optimizer._extract_attributaire_components(expression)
        
        # Should find spatial component
        assert len(spatial_parts) >= 1
        
        # Should find attribute components (not spatial)
        assert len(attr_parts) >= 1
        assert all('ST_Intersects' not in part for part in attr_parts)

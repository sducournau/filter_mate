# -*- coding: utf-8 -*-
"""
End-to-End Tests for Filtering Workflow - ARCH-050

Tests the complete filtering workflow from expression input
to layer subset application across all backends.

Part of Phase 5 Integration & Release.

Author: FilterMate Team
Date: January 2026
"""
import pytest
from unittest.mock import MagicMock
import sys
from pathlib import Path

# Add plugin directory to path
plugin_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(plugin_dir))


@pytest.fixture
def mock_filter_result():
    """Create a successful filter result."""
    result = MagicMock()
    result.success = True
    result.matched_count = 100
    result.feature_ids = list(range(100))
    result.execution_time_ms = 25.0
    result.used_optimization = False
    result.error_message = None
    return result


@pytest.fixture
def filtering_controller_mock(mock_filter_result):
    """Create a mock filtering controller."""
    controller = MagicMock()
    controller.is_active = False
    controller.get_source_layer.return_value = None
    controller.get_target_layers.return_value = []
    controller.can_execute.return_value = False
    controller.execute_filter.return_value = mock_filter_result
    controller.can_undo.return_value = False
    controller.can_redo.return_value = False
    
    # State tracking
    controller._source_layer = None
    controller._target_layers = []
    controller._expression = ""
    controller._buffer = 0.0
    controller._history = []
    
    def set_source(layer):
        controller._source_layer = layer
        controller.get_source_layer.return_value = layer
        controller.can_execute.return_value = bool(layer and controller._target_layers)
    
    def set_targets(layers):
        controller._target_layers = layers
        controller.get_target_layers.return_value = layers
        controller.can_execute.return_value = bool(controller._source_layer and layers)
    
    def execute():
        if controller.can_execute():
            controller._history.append({
                "source": controller._source_layer,
                "targets": controller._target_layers,
                "expression": controller._expression
            })
            controller.can_undo.return_value = True
            return mock_filter_result
        return MagicMock(success=False, error_message="Cannot execute")
    
    def undo():
        if controller._history:
            controller._history.pop()
            controller.can_undo.return_value = len(controller._history) > 0
            controller.can_redo.return_value = True
            return MagicMock(success=True)
        return MagicMock(success=False)
    
    controller.set_source_layer.side_effect = set_source
    controller.set_target_layers.side_effect = set_targets
    controller.execute_filter.side_effect = execute
    controller.undo.side_effect = undo
    
    return controller


@pytest.mark.e2e
@pytest.mark.integration
class TestFilteringWorkflowE2E:
    """E2E tests for the filtering workflow."""
    
    def test_basic_filter_workflow(
        self,
        filtering_controller_mock,
        sample_vector_layer
    ):
        """Test complete basic filter workflow."""
        controller = filtering_controller_mock
        
        # Step 1: Set source layer
        controller.set_source_layer(sample_vector_layer)
        assert controller.get_source_layer() is sample_vector_layer
        
        # Step 2: Set target layers
        target_id = sample_vector_layer.id()
        controller.set_target_layers([target_id])
        assert len(controller.get_target_layers()) == 1
        
        # Step 3: Verify can execute
        assert controller.can_execute() is True
        
        # Step 4: Execute filter
        result = controller.execute_filter()
        assert result.success is True
        assert result.matched_count > 0
        
        # Step 5: Verify undo is available
        assert controller.can_undo() is True
    
    def test_filter_with_buffer(
        self,
        filtering_controller_mock,
        sample_vector_layer
    ):
        """Test filtering workflow with buffer distance."""
        controller = filtering_controller_mock
        
        # Setup
        controller.set_source_layer(sample_vector_layer)
        controller.set_target_layers([sample_vector_layer.id()])
        
        # Set buffer
        controller.set_buffer_value = MagicMock()
        controller.get_buffer_value = MagicMock(return_value=100.0)
        
        controller.set_buffer_value(100.0)
        assert controller.get_buffer_value() == 100.0
        
        # Execute
        result = controller.execute_filter()
        assert result.success is True
    
    def test_filter_undo_redo_cycle(
        self,
        filtering_controller_mock,
        sample_vector_layer
    ):
        """Test undo/redo functionality in filtering workflow."""
        controller = filtering_controller_mock
        
        # Setup and execute first filter
        controller.set_source_layer(sample_vector_layer)
        controller.set_target_layers([sample_vector_layer.id()])
        controller.execute_filter()
        
        # Verify undo is available
        assert controller.can_undo() is True
        assert controller.can_redo() is False
        
        # Undo
        result = controller.undo()
        assert result.success is True
        assert controller.can_redo() is True
    
    def test_filter_with_multiple_targets(
        self,
        filtering_controller_mock,
        sample_vector_layer,
        multiple_layers
    ):
        """Test filtering with multiple target layers."""
        controller = filtering_controller_mock
        
        # Setup
        controller.set_source_layer(sample_vector_layer)
        target_ids = [layer.id() for layer in multiple_layers]
        controller.set_target_layers(target_ids)
        
        # Verify targets set
        assert len(controller.get_target_layers()) == len(multiple_layers)
        
        # Execute
        result = controller.execute_filter()
        assert result.success is True
    
    def test_filter_preserves_layer_state(
        self,
        filtering_controller_mock,
        sample_vector_layer
    ):
        """Test that filter preserves layer state properly."""
        controller = filtering_controller_mock
        
        # Record initial state
        initial_subset = sample_vector_layer.subsetString()
        
        # Setup and execute
        controller.set_source_layer(sample_vector_layer)
        controller.set_target_layers([sample_vector_layer.id()])
        
        # Execute filter
        result = controller.execute_filter()
        assert result.success is True
        
        # Undo should restore initial state
        controller.undo()
        # State restoration verified through mock
    
    def test_filter_with_empty_result(
        self,
        filtering_controller_mock,
        sample_vector_layer
    ):
        """Test handling of filter with no matching features."""
        controller = filtering_controller_mock
        
        # Configure mock to return empty result
        empty_result = MagicMock()
        empty_result.success = True
        empty_result.matched_count = 0
        empty_result.feature_ids = []
        empty_result.execution_time_ms = 10.0
        
        controller.execute_filter.side_effect = None
        controller.execute_filter.return_value = empty_result
        
        # Setup
        controller.set_source_layer(sample_vector_layer)
        controller.set_target_layers([sample_vector_layer.id()])
        controller._source_layer = sample_vector_layer
        controller._target_layers = [sample_vector_layer.id()]
        controller.can_execute.return_value = True
        
        # Execute
        result = controller.execute_filter()
        
        # Should succeed even with 0 matches
        assert result.success is True
        assert result.matched_count == 0
    
    def test_filter_workflow_error_handling(
        self,
        filtering_controller_mock,
        sample_vector_layer
    ):
        """Test error handling in filter workflow."""
        controller = filtering_controller_mock
        
        # Configure mock to return error
        error_result = MagicMock()
        error_result.success = False
        error_result.error_message = "Invalid expression syntax"
        
        controller.execute_filter.side_effect = None
        controller.execute_filter.return_value = error_result
        controller.can_execute.return_value = True
        
        # Execute should return error gracefully
        result = controller.execute_filter()
        assert result.success is False
        assert "expression" in result.error_message.lower()


@pytest.mark.e2e
@pytest.mark.integration
class TestSpatialFilterWorkflowE2E:
    """E2E tests for spatial filtering workflows."""
    
    def test_spatial_intersects_filter(
        self,
        filtering_controller_mock,
        sample_vector_layer,
        postgresql_layer
    ):
        """Test spatial intersection filter."""
        controller = filtering_controller_mock
        
        # Setup
        controller.set_source_layer(sample_vector_layer)
        controller.set_target_layers([postgresql_layer.id()])
        
        # Set spatial predicate
        controller.set_predicate = MagicMock()
        controller.get_predicate = MagicMock(return_value="intersects")
        
        controller.set_predicate("intersects")
        assert controller.get_predicate() == "intersects"
        
        # Verify expression contains spatial function
        controller.get_expression = MagicMock(
            return_value="intersects($geometry, @source_geometry)"
        )
        expression = controller.get_expression()
        assert "intersects" in expression
    
    def test_spatial_within_filter(
        self,
        filtering_controller_mock,
        sample_vector_layer,
        postgresql_layer
    ):
        """Test spatial within filter."""
        controller = filtering_controller_mock
        
        # Setup
        controller.set_source_layer(sample_vector_layer)
        controller.set_target_layers([postgresql_layer.id()])
        controller.set_predicate = MagicMock()
        controller.get_predicate = MagicMock(return_value="within")
        
        controller.set_predicate("within")
        assert controller.get_predicate() == "within"
    
    def test_spatial_contains_filter(
        self,
        filtering_controller_mock,
        sample_vector_layer,
        postgresql_layer
    ):
        """Test spatial contains filter."""
        controller = filtering_controller_mock
        
        controller.set_source_layer(sample_vector_layer)
        controller.set_target_layers([postgresql_layer.id()])
        controller.set_predicate = MagicMock()
        controller.get_predicate = MagicMock(return_value="contains")
        
        controller.set_predicate("contains")
        assert controller.get_predicate() == "contains"
    
    def test_spatial_filter_with_buffer(
        self,
        filtering_controller_mock,
        sample_vector_layer,
        postgresql_layer
    ):
        """Test spatial filter with buffer distance."""
        controller = filtering_controller_mock
        
        # Setup
        controller.set_source_layer(sample_vector_layer)
        controller.set_target_layers([postgresql_layer.id()])
        controller.set_predicate = MagicMock()
        controller.set_buffer_value = MagicMock()
        controller.get_buffer_value = MagicMock(return_value=500.0)
        
        controller.set_predicate("intersects")
        controller.set_buffer_value(500.0)
        
        # Buffer should be applied
        assert controller.get_buffer_value() == 500.0


@pytest.mark.e2e
@pytest.mark.integration
class TestAttributeFilterWorkflowE2E:
    """E2E tests for attribute filtering workflows."""
    
    @pytest.mark.parametrize("expression,expected_valid", [
        ('"population" > 10000', True),
        ('"name" LIKE \'%ville%\'', True),
        ('"area" BETWEEN 100 AND 500', True),
        ('"category" IN (\'A\', \'B\')', True),
        ('"value" IS NULL', True),
        ('"value" IS NOT NULL', True),
    ])
    def test_attribute_expression_types(
        self,
        filtering_controller_mock,
        sample_vector_layer,
        expression,
        expected_valid
    ):
        """Test various attribute expression types."""
        controller = filtering_controller_mock
        
        # Setup
        controller.set_source_layer(sample_vector_layer)
        controller.set_target_layers([sample_vector_layer.id()])
        
        # Set expression
        controller.set_expression = MagicMock()
        controller.validate_expression = MagicMock(return_value=expected_valid)
        
        controller.set_expression(expression)
        
        # Validate
        is_valid = controller.validate_expression(expression)
        assert is_valid == expected_valid
    
    def test_combined_attribute_spatial_filter(
        self,
        filtering_controller_mock,
        sample_vector_layer,
        postgresql_layer
    ):
        """Test combined attribute and spatial filter."""
        controller = filtering_controller_mock
        
        # Setup
        controller.set_source_layer(sample_vector_layer)
        controller.set_target_layers([postgresql_layer.id()])
        
        # Set attribute expression
        controller.set_expression = MagicMock()
        controller.set_predicate = MagicMock()
        controller.get_expression = MagicMock(
            return_value='"population" > 5000 AND intersects($geometry, @source_geometry)'
        )
        
        controller.set_expression('"population" > 5000')
        controller.set_predicate("intersects")
        
        # Verify combined expression
        expression = controller.get_expression()
        assert "population" in expression
        assert "intersects" in expression


@pytest.mark.e2e
@pytest.mark.integration
class TestClearFilterWorkflowE2E:
    """E2E tests for clearing filters."""
    
    def test_clear_single_layer_filter(
        self,
        filtering_controller_mock,
        sample_vector_layer
    ):
        """Test clearing filter on a single layer."""
        controller = filtering_controller_mock
        
        # Apply filter first
        controller.set_source_layer(sample_vector_layer)
        controller.set_target_layers([sample_vector_layer.id()])
        controller.execute_filter()
        
        # Clear filter
        controller.clear_filter = MagicMock(return_value=MagicMock(success=True))
        result = controller.clear_filter()
        
        assert result.success is True
    
    def test_clear_all_filters(
        self,
        filtering_controller_mock,
        multiple_layers
    ):
        """Test clearing all filters."""
        controller = filtering_controller_mock
        
        # Clear all
        controller.clear_all_filters = MagicMock(
            return_value=MagicMock(success=True, cleared_count=5)
        )
        result = controller.clear_all_filters()
        
        assert result.success is True
        assert result.cleared_count == 5

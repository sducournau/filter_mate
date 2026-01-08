# -*- coding: utf-8 -*-
"""
Unit tests for FilterOptimizer port interfaces and domain types.

Tests the pure Python components without QGIS dependencies.
"""

import pytest
from core.ports.filter_optimizer import (
    FilterStrategy,
    FilterPlan,
    FilterStep,
    LayerStatistics,
    PlanBuilderConfig,
)


class TestFilterStrategy:
    """Tests for FilterStrategy enum."""
    
    def test_all_strategies_exist(self):
        """Verify all expected strategies are defined."""
        assert FilterStrategy.DIRECT.value == "direct"
        assert FilterStrategy.ATTRIBUTE_FIRST.value == "attribute_first"
        assert FilterStrategy.BBOX_THEN_EXACT.value == "bbox_then_exact"
        assert FilterStrategy.PROGRESSIVE_CHUNKS.value == "progressive_chunks"
        assert FilterStrategy.HYBRID.value == "hybrid"
    
    def test_strategy_from_value(self):
        """Test creating strategy from value string."""
        strategy = FilterStrategy("attribute_first")
        assert strategy == FilterStrategy.ATTRIBUTE_FIRST


class TestLayerStatistics:
    """Tests for LayerStatistics dataclass."""
    
    def test_default_values(self):
        """Test default values."""
        stats = LayerStatistics(feature_count=1000)
        
        assert stats.feature_count == 1000
        assert stats.extent_area == 0.0
        assert stats.extent_bounds is None
        assert stats.has_spatial_index is False
        assert stats.geometry_type == 0
        assert stats.avg_vertices_per_feature == 0.0
        assert stats.estimated_complexity == 1.0
    
    def test_all_values(self):
        """Test with all values specified."""
        stats = LayerStatistics(
            feature_count=50000,
            extent_area=1000000.0,
            extent_bounds=(0.0, 0.0, 1000.0, 1000.0),
            has_spatial_index=True,
            geometry_type=2,  # Polygon
            avg_vertices_per_feature=50.0,
            estimated_complexity=5.0
        )
        
        assert stats.feature_count == 50000
        assert stats.extent_area == 1000000.0
        assert stats.extent_bounds == (0.0, 0.0, 1000.0, 1000.0)
        assert stats.has_spatial_index is True
    
    def test_is_large_dataset_false(self):
        """Test small dataset is not flagged as large."""
        stats = LayerStatistics(feature_count=10000)
        assert stats.is_large_dataset is False
    
    def test_is_large_dataset_true(self):
        """Test large dataset is correctly flagged."""
        stats = LayerStatistics(feature_count=100000)
        assert stats.is_large_dataset is True
    
    def test_is_very_large_dataset_false(self):
        """Test medium dataset is not very large."""
        stats = LayerStatistics(feature_count=100000)
        assert stats.is_very_large_dataset is False
    
    def test_is_very_large_dataset_true(self):
        """Test very large dataset is correctly flagged."""
        stats = LayerStatistics(feature_count=500000)
        assert stats.is_very_large_dataset is True


class TestFilterStep:
    """Tests for FilterStep dataclass."""
    
    def test_minimal_step(self):
        """Test step with minimal info."""
        step = FilterStep(step_type="attribute")
        
        assert step.step_type == "attribute"
        assert step.expression is None
        assert step.estimated_output == 0
        assert step.metadata == {}
    
    def test_full_step(self):
        """Test step with all info."""
        step = FilterStep(
            step_type="attribute",
            expression="population > 10000",
            estimated_output=500,
            metadata={"selectivity": 0.1}
        )
        
        assert step.step_type == "attribute"
        assert step.expression == "population > 10000"
        assert step.estimated_output == 500
        assert step.metadata["selectivity"] == 0.1


class TestFilterPlan:
    """Tests for FilterPlan dataclass."""
    
    def test_minimal_plan(self):
        """Test plan with minimal values."""
        plan = FilterPlan(
            strategy=FilterStrategy.DIRECT,
            estimated_selectivity=1.0,
            estimated_cost=1.0
        )
        
        assert plan.strategy == FilterStrategy.DIRECT
        assert plan.estimated_selectivity == 1.0
        assert plan.estimated_cost == 1.0
        assert plan.steps == []
        assert plan.chunk_size == 10000
        assert plan.use_spatial_index is True
        assert plan.attribute_filter is None
    
    def test_plan_with_steps(self):
        """Test plan with filter steps."""
        steps = [
            FilterStep(
                step_type="attribute",
                expression="category = 'A'",
                estimated_output=1000
            ),
            FilterStep(
                step_type="spatial",
                estimated_output=200
            )
        ]
        
        plan = FilterPlan(
            strategy=FilterStrategy.ATTRIBUTE_FIRST,
            estimated_selectivity=0.02,
            estimated_cost=2.5,
            steps=steps,
            attribute_filter="category = 'A'"
        )
        
        assert len(plan.steps) == 2
        assert plan.steps[0].step_type == "attribute"
        assert plan.steps[1].step_type == "spatial"
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        steps = [
            FilterStep(
                step_type="attribute",
                expression="name LIKE 'Test%'",
                estimated_output=500
            )
        ]
        
        plan = FilterPlan(
            strategy=FilterStrategy.ATTRIBUTE_FIRST,
            estimated_selectivity=0.1,
            estimated_cost=2.0,
            steps=steps,
            chunk_size=5000,
            use_spatial_index=False,
            attribute_filter="name LIKE 'Test%'"
        )
        
        data = plan.to_dict()
        
        assert data["strategy"] == "attribute_first"
        assert data["estimated_selectivity"] == 0.1
        assert data["estimated_cost"] == 2.0
        assert len(data["steps"]) == 1
        assert data["steps"][0]["type"] == "attribute"
        assert data["steps"][0]["expression"] == "name LIKE 'Test%'"
        assert data["chunk_size"] == 5000
        assert data["use_spatial_index"] is False
        assert data["attribute_filter"] == "name LIKE 'Test%'"
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "strategy": "progressive_chunks",
            "estimated_selectivity": 0.5,
            "estimated_cost": 5.0,
            "steps": [
                {"type": "bbox_filter", "estimated_output": 10000},
                {"type": "exact_spatial", "estimated_output": 5000}
            ],
            "chunk_size": 2000,
            "use_spatial_index": True,
            "attribute_filter": None
        }
        
        plan = FilterPlan.from_dict(data)
        
        assert plan.strategy == FilterStrategy.PROGRESSIVE_CHUNKS
        assert plan.estimated_selectivity == 0.5
        assert plan.estimated_cost == 5.0
        assert len(plan.steps) == 2
        assert plan.steps[0].step_type == "bbox_filter"
        assert plan.steps[1].step_type == "exact_spatial"
        assert plan.chunk_size == 2000
    
    def test_roundtrip_serialization(self):
        """Test to_dict -> from_dict preserves data."""
        original = FilterPlan(
            strategy=FilterStrategy.HYBRID,
            estimated_selectivity=0.3,
            estimated_cost=2.5,
            steps=[
                FilterStep("attribute", "type = 'X'", 1000),
                FilterStep("spatial", None, 200, {"predicate": "intersects"})
            ],
            chunk_size=8000,
            use_spatial_index=True,
            attribute_filter="type = 'X'"
        )
        
        data = original.to_dict()
        restored = FilterPlan.from_dict(data)
        
        assert restored.strategy == original.strategy
        assert restored.estimated_selectivity == original.estimated_selectivity
        assert restored.estimated_cost == original.estimated_cost
        assert len(restored.steps) == len(original.steps)
        assert restored.chunk_size == original.chunk_size


class TestPlanBuilderConfig:
    """Tests for PlanBuilderConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = PlanBuilderConfig()
        
        assert config.small_dataset_threshold == 1000
        assert config.medium_dataset_threshold == 50000
        assert config.large_dataset_threshold == 200000
        assert config.very_large_threshold == 1000000
        assert config.attribute_first_selectivity_threshold == 0.3
        assert config.bbox_prefilter_threshold == 0.5
        assert config.base_chunk_size == 10000
        assert config.min_chunk_size == 1000
        assert config.max_chunk_size == 50000
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = PlanBuilderConfig(
            small_dataset_threshold=500,
            base_chunk_size=5000
        )
        
        assert config.small_dataset_threshold == 500
        assert config.base_chunk_size == 5000
        # Other values remain default
        assert config.medium_dataset_threshold == 50000
    
    def test_calculate_chunk_size_normal(self):
        """Test chunk size for normal dataset."""
        config = PlanBuilderConfig()
        
        chunk = config.calculate_chunk_size(100000, 1.0)
        
        assert chunk == 10000  # Base chunk size
    
    def test_calculate_chunk_size_very_large(self):
        """Test chunk size for very large dataset."""
        config = PlanBuilderConfig()
        
        chunk = config.calculate_chunk_size(2000000, 1.0)
        
        assert chunk == 5000  # Reduced for very large
    
    def test_calculate_chunk_size_complex_geometry(self):
        """Test chunk size for complex geometries."""
        config = PlanBuilderConfig()
        
        chunk = config.calculate_chunk_size(100000, 10.0)  # High complexity
        
        # Should be reduced due to complexity
        assert chunk < 10000
        assert chunk >= config.min_chunk_size
    
    def test_calculate_chunk_size_bounds(self):
        """Test chunk size respects bounds."""
        config = PlanBuilderConfig()
        
        # Very low complexity shouldn't exceed max
        chunk_high = config.calculate_chunk_size(100000, 0.1)
        assert chunk_high <= config.max_chunk_size
        
        # Very high complexity shouldn't go below min
        chunk_low = config.calculate_chunk_size(100000, 100.0)
        assert chunk_low >= config.min_chunk_size

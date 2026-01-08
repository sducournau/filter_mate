# -*- coding: utf-8 -*-
"""
Unit tests for Auto-Optimizer.

Tests optimization logic without QGIS dependencies.
"""
import pytest
from typing import Optional

from core.domain.filter_expression import ProviderType
from core.domain.layer_info import LayerInfo, GeometryType
from core.services.auto_optimizer import (
    AutoOptimizer,
    OptimizerConfig,
    OptimizationType,
    LayerAnalysis,
    OptimizationRecommendation,
    OptimizationPlan,
    get_auto_optimizer,
    create_auto_optimizer,
    recommend_optimizations,
)


class TestLayerAnalysis:
    """Tests for LayerAnalysis class."""

    @pytest.fixture
    def large_pg_layer(self):
        """Create a large PostgreSQL layer info."""
        return LayerInfo(
            layer_id="large_pg",
            name="large_pg_layer",
            provider_type=ProviderType.POSTGRESQL,
            feature_count=100000,
            geometry_type=GeometryType.POLYGON,
            crs_auth_id="EPSG:4326",
            has_spatial_index=True
        )

    @pytest.fixture
    def small_memory_layer(self):
        """Create a small memory layer info."""
        return LayerInfo(
            layer_id="small_mem",
            name="small_memory_layer",
            provider_type=ProviderType.MEMORY,
            feature_count=100,
            geometry_type=GeometryType.POINT,
            crs_auth_id="EPSG:4326"
        )

    def test_from_layer_info_postgresql(self, large_pg_layer):
        """Test creating analysis from PostgreSQL layer."""
        analysis = LayerAnalysis.from_layer_info(large_pg_layer)

        assert analysis.layer_id == "large_pg"
        assert analysis.provider_type == ProviderType.POSTGRESQL
        assert analysis.is_large is True
        assert analysis.feature_count == 100000

    def test_from_layer_info_memory(self, small_memory_layer):
        """Test creating analysis from memory layer."""
        analysis = LayerAnalysis.from_layer_info(small_memory_layer)

        assert analysis.layer_id == "small_mem"
        assert analysis.provider_type == ProviderType.MEMORY
        assert analysis.is_large is False
        assert analysis.feature_count == 100


class TestOptimizerConfig:
    """Tests for OptimizerConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = OptimizerConfig()

        assert config.enabled is True
        assert config.auto_centroid_for_distant is True
        assert config.auto_simplify_geometry is False
        assert config.centroid_threshold_distant == 5000

    def test_from_dict(self):
        """Test creating config from dictionary."""
        config_dict = {
            'enabled': False,
            'auto_centroid_for_distant': False,
            'centroid_threshold_distant': 10000
        }

        config = OptimizerConfig.from_dict(config_dict)

        assert config.enabled is False
        assert config.auto_centroid_for_distant is False
        assert config.centroid_threshold_distant == 10000

    def test_from_dict_with_nested_values(self):
        """Test creating config from v2.0 format with nested values."""
        config_dict = {
            'enabled': {'value': True, 'description': 'Enable optimizer'},
            'centroid_threshold_distant': {'value': 7500}
        }

        config = OptimizerConfig.from_dict(config_dict)

        assert config.enabled is True
        assert config.centroid_threshold_distant == 7500


class TestOptimizationRecommendation:
    """Tests for OptimizationRecommendation class."""

    def test_to_dict(self):
        """Test converting recommendation to dictionary."""
        rec = OptimizationRecommendation(
            optimization_type=OptimizationType.USE_CENTROID_DISTANT,
            priority=1,
            estimated_speedup=3.0,
            reason="Large distant layer",
            auto_applicable=True,
            parameters={'mode': 'point_on_surface'}
        )

        result = rec.to_dict()

        assert result['optimization_type'] == 'use_centroid_distant'
        assert result['priority'] == 1
        assert result['estimated_speedup'] == 3.0
        assert result['auto_applicable'] is True


class TestAutoOptimizer:
    """Tests for AutoOptimizer class."""

    @pytest.fixture
    def optimizer(self):
        """Create optimizer with default config."""
        return AutoOptimizer()

    @pytest.fixture
    def disabled_optimizer(self):
        """Create disabled optimizer."""
        config = OptimizerConfig(enabled=False)
        return AutoOptimizer(config)

    @pytest.fixture
    def large_polygon_layer(self):
        """Create large polygon layer."""
        return LayerInfo(
            layer_id="large_poly",
            name="large_polygons",
            provider_type=ProviderType.POSTGRESQL,
            feature_count=75000,
            geometry_type=GeometryType.POLYGON,
            crs_auth_id="EPSG:4326"
        )

    @pytest.fixture
    def small_point_layer(self):
        """Create small point layer."""
        return LayerInfo(
            layer_id="small_point",
            name="small_points",
            provider_type=ProviderType.OGR,
            feature_count=500,
            geometry_type=GeometryType.POINT,
            crs_auth_id="EPSG:4326"
        )

    def test_is_enabled(self, optimizer, disabled_optimizer):
        """Test enabled property."""
        assert optimizer.is_enabled is True
        assert disabled_optimizer.is_enabled is False

    def test_analyze_layer(self, optimizer, large_polygon_layer):
        """Test layer analysis."""
        analysis = optimizer.analyze_layer(large_polygon_layer)

        assert analysis.layer_id == "large_poly"
        assert analysis.feature_count == 75000
        assert analysis.is_large is True

    def test_analyze_layer_caching(self, optimizer, large_polygon_layer):
        """Test that analysis is cached."""
        analysis1 = optimizer.analyze_layer(large_polygon_layer)
        analysis2 = optimizer.analyze_layer(large_polygon_layer)

        # Should be same object (cached)
        assert analysis1 is analysis2

    def test_analyze_layer_force_refresh(self, optimizer, large_polygon_layer):
        """Test force refresh bypasses cache."""
        analysis1 = optimizer.analyze_layer(large_polygon_layer)
        analysis2 = optimizer.analyze_layer(large_polygon_layer, force_refresh=True)

        # Should be different objects
        assert analysis1 is not analysis2

    def test_create_optimization_plan_large_layer(self, optimizer, large_polygon_layer):
        """Test creating plan for large layer."""
        plan = optimizer.create_optimization_plan(large_polygon_layer)

        assert isinstance(plan, OptimizationPlan)
        assert plan.layer_analysis.layer_id == "large_poly"
        # Should have centroid recommendation for large polygon layer
        assert plan.has_recommendations is True

    def test_create_optimization_plan_small_layer(self, optimizer, small_point_layer):
        """Test creating plan for small layer (fewer recommendations)."""
        plan = optimizer.create_optimization_plan(small_point_layer)

        assert isinstance(plan, OptimizationPlan)
        # Small point layer shouldn't need centroid optimization
        centroid_recs = [
            r for r in plan.recommendations
            if r.optimization_type == OptimizationType.USE_CENTROID_DISTANT
        ]
        assert len(centroid_recs) == 0

    def test_centroid_optimization_for_polygon(self, optimizer, large_polygon_layer):
        """Test centroid optimization is recommended for large polygons."""
        plan = optimizer.create_optimization_plan(large_polygon_layer)

        centroid_recs = [
            r for r in plan.recommendations
            if r.optimization_type == OptimizationType.USE_CENTROID_DISTANT
        ]

        assert len(centroid_recs) == 1
        assert centroid_recs[0].estimated_speedup > 1.0

    def test_no_centroid_for_points(self, optimizer):
        """Test no centroid optimization for point layers."""
        point_layer = LayerInfo(
            layer_id="pts",
            name="points",
            provider_type=ProviderType.POSTGRESQL,
            feature_count=100000,
            geometry_type=GeometryType.POINT,
            crs_auth_id="EPSG:4326"
        )

        plan = optimizer.create_optimization_plan(point_layer)

        centroid_recs = [
            r for r in plan.recommendations
            if r.optimization_type == OptimizationType.USE_CENTROID_DISTANT
        ]

        assert len(centroid_recs) == 0

    def test_buffer_optimization(self, optimizer, large_polygon_layer):
        """Test buffer optimization recommendations."""
        plan = optimizer.create_optimization_plan(
            large_polygon_layer,
            has_buffer=True,
            buffer_value=100.0
        )

        buffer_recs = [
            r for r in plan.recommendations
            if r.optimization_type in (
                OptimizationType.SIMPLIFY_BEFORE_BUFFER,
                OptimizationType.REDUCE_BUFFER_SEGMENTS
            )
        ]

        assert len(buffer_recs) > 0

    def test_attribute_first_strategy(self, optimizer, large_polygon_layer):
        """Test attribute-first strategy recommendation."""
        plan = optimizer.create_optimization_plan(
            large_polygon_layer,
            attribute_filter="type = 'residential'"
        )

        strategy_recs = [
            r for r in plan.recommendations
            if r.optimization_type == OptimizationType.ATTRIBUTE_FIRST
        ]

        assert len(strategy_recs) == 1
        assert plan.final_strategy == "attribute_first"

    def test_statistics(self, optimizer, large_polygon_layer):
        """Test optimizer statistics."""
        # Create a few plans
        optimizer.create_optimization_plan(large_polygon_layer)
        optimizer.create_optimization_plan(large_polygon_layer)

        stats = optimizer.get_statistics()

        assert stats['plans_created'] == 2
        assert 'total_estimated_speedup' in stats

    def test_reset_statistics(self, optimizer, large_polygon_layer):
        """Test resetting statistics."""
        optimizer.create_optimization_plan(large_polygon_layer)
        optimizer.reset_statistics()

        stats = optimizer.get_statistics()
        assert stats['plans_created'] == 0

    def test_clear_cache(self, optimizer, large_polygon_layer):
        """Test clearing analysis cache."""
        # Clear first to ensure clean state
        optimizer.clear_cache()
        
        optimizer.analyze_layer(large_polygon_layer)
        cleared = optimizer.clear_cache()

        assert cleared >= 1
        assert len(optimizer._analysis_cache) == 0


class TestFactoryFunctions:
    """Tests for module-level factory functions."""

    def test_get_auto_optimizer_singleton(self):
        """Test get_auto_optimizer returns singleton."""
        # Reset singleton
        import core.services.auto_optimizer as mod
        mod._optimizer_instance = None

        opt1 = get_auto_optimizer()
        opt2 = get_auto_optimizer()

        assert opt1 is opt2

    def test_create_auto_optimizer_new_instance(self):
        """Test create_auto_optimizer creates new instance."""
        opt1 = create_auto_optimizer()
        opt2 = create_auto_optimizer()

        assert opt1 is not opt2

    def test_recommend_optimizations(self):
        """Test quick recommendation function."""
        layer = LayerInfo(
            layer_id="test",
            name="test_layer",
            provider_type=ProviderType.POSTGRESQL,
            feature_count=80000,
            geometry_type=GeometryType.POLYGON,
            crs_auth_id="EPSG:4326"
        )

        recommendations = recommend_optimizations(layer)

        assert isinstance(recommendations, list)
        # Should have at least centroid recommendation
        assert len(recommendations) > 0

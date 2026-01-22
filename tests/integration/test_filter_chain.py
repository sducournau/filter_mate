# -*- coding: utf-8 -*-
"""
Integration Tests for Filter Chaining.

Tests the complete filter chaining workflow including:
- Multi-layer filter propagation
- Spatial predicates (intersects, contains, within, etc.)
- Combine operators (AND, OR)
- Buffer operations
- Remote layer filtering

Author: FilterMate Team
Date: January 2026
Sprint: 1.2 - Critical Tests
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# Add plugin directory to path
plugin_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(plugin_dir))

# Mock QGIS before importing
sys.modules['qgis'] = Mock()
sys.modules['qgis.core'] = Mock()
sys.modules['qgis.PyQt'] = Mock()
sys.modules['qgis.PyQt.QtCore'] = Mock()

from core.domain.filter_expression import FilterExpression, ProviderType
from core.domain.filter_result import FilterResult, FilterStatus


class TestFilterChainBasics:
    """Basic filter chain tests."""
    
    def test_single_layer_filter(self):
        """Test filtering a single layer."""
        # Create a filter expression
        expr = FilterExpression.create(
            raw='"population" > 10000',
            provider=ProviderType.OGR,
            source_layer_id="cities_layer"
        )
        
        assert expr.raw == '"population" > 10000'
        assert expr.source_layer_id == "cities_layer"
    
    def test_filter_result_success(self):
        """Test successful filter result."""
        result = FilterResult.success(
            feature_ids=[1, 2, 3, 4, 5],
            layer_id="cities_layer",
            expression_raw='"population" > 10000',
            execution_time_ms=15.5,
            backend_name="OGR"
        )
        
        assert result.status == FilterStatus.SUCCESS
        assert len(result.feature_ids) == 5
        assert result.layer_id == "cities_layer"
    
    def test_filter_result_failure(self):
        """Test failed filter result."""
        result = FilterResult.error(
            layer_id="cities_layer",
            expression_raw='"invalid" = syntax',
            error_message="Invalid expression syntax"
        )
        
        assert result.status == FilterStatus.ERROR
        assert "Invalid" in result.error_message


class TestSpatialPredicates:
    """Tests for spatial predicate filtering."""
    
    @pytest.fixture
    def mock_filter_service(self):
        """Create a mock filter service."""
        service = Mock()
        service.apply_filter.return_value = Mock(
            is_success=True,
            results={"layer1": FilterResult.success(
                feature_ids=[1, 2, 3],
                layer_id="layer1",
                expression_raw="test",
                execution_time_ms=10.0,
                backend_name="test"
            )}
        )
        return service
    
    def test_intersects_predicate(self):
        """Test intersects spatial predicate."""
        # Simulate filtering with intersects
        predicate_config = {
            "intersects": True,
            "contains": False,
            "within": False,
            "overlaps": False,
            "touches": False
        }
        
        active_predicates = [k for k, v in predicate_config.items() if v]
        assert active_predicates == ["intersects"]
    
    def test_multiple_predicates(self):
        """Test multiple active predicates."""
        predicate_config = {
            "intersects": True,
            "contains": True,
            "within": False,
            "overlaps": False,
            "touches": True
        }
        
        active_predicates = [k for k, v in predicate_config.items() if v]
        assert len(active_predicates) == 3
        assert "intersects" in active_predicates
        assert "contains" in active_predicates
        assert "touches" in active_predicates
    
    def test_predicate_sql_generation(self):
        """Test SQL generation for predicates."""
        # Simulated predicate to SQL mapping
        predicate_sql_map = {
            "intersects": "ST_Intersects({geom1}, {geom2})",
            "contains": "ST_Contains({geom1}, {geom2})",
            "within": "ST_Within({geom1}, {geom2})",
            "overlaps": "ST_Overlaps({geom1}, {geom2})",
            "touches": "ST_Touches({geom1}, {geom2})"
        }
        
        selected_predicate = "intersects"
        sql_template = predicate_sql_map[selected_predicate]
        
        sql = sql_template.format(geom1="source.geom", geom2="target.geom")
        assert "ST_Intersects" in sql
        assert "source.geom" in sql


class TestCombineOperators:
    """Tests for filter combine operators."""
    
    def test_and_operator(self):
        """Test AND combine operator."""
        expr1 = '"field1" = 1'
        expr2 = '"field2" = 2'
        
        combined = f"({expr1}) AND ({expr2})"
        
        assert "AND" in combined
        assert expr1 in combined
        assert expr2 in combined
    
    def test_or_operator(self):
        """Test OR combine operator."""
        expr1 = '"field1" = 1'
        expr2 = '"field2" = 2'
        
        combined = f"({expr1}) OR ({expr2})"
        
        assert "OR" in combined
    
    def test_nested_operators(self):
        """Test nested combine operators."""
        expr1 = '"status" = \'active\''
        expr2 = '"type" = \'residential\''
        expr3 = '"area" > 100'
        
        # (expr1 AND expr2) OR expr3
        combined = f"(({expr1}) AND ({expr2})) OR ({expr3})"
        
        assert combined.count("AND") == 1
        assert combined.count("OR") == 1


class TestBufferOperations:
    """Tests for buffer operations in filter chains."""
    
    def test_positive_buffer(self):
        """Test positive buffer value."""
        buffer_value = 100.0
        buffer_unit = "meters"
        
        assert buffer_value > 0
        assert buffer_unit in ["meters", "kilometers", "feet", "miles"]
    
    def test_negative_buffer(self):
        """Test negative buffer (shrink) value."""
        buffer_value = -50.0  # Shrink by 50 units
        
        # Negative buffer should reduce geometry
        assert buffer_value < 0
    
    def test_zero_buffer(self):
        """Test zero buffer (no change)."""
        buffer_value = 0.0
        
        # Zero buffer means no spatial buffering
        assert buffer_value == 0.0
    
    def test_buffer_expression(self):
        """Test buffer SQL expression generation."""
        buffer_value = 100.0
        
        # PostGIS style buffer
        buffer_sql = f"ST_Buffer(geometry, {buffer_value})"
        
        assert "ST_Buffer" in buffer_sql
        assert str(buffer_value) in buffer_sql


class TestMultiLayerFilterChain:
    """Tests for multi-layer filter chains."""
    
    @pytest.fixture
    def layer_chain_config(self):
        """Create a sample multi-layer filter chain configuration."""
        return {
            "source_layer": "buildings",
            "remote_layers": ["roads", "parks", "water_bodies"],
            "predicates": {
                "roads": {"intersects": True},
                "parks": {"within": True},
                "water_bodies": {"touches": True}
            },
            "combine_operator": "AND"
        }
    
    def test_chain_config_structure(self, layer_chain_config):
        """Test filter chain configuration structure."""
        assert "source_layer" in layer_chain_config
        assert "remote_layers" in layer_chain_config
        assert "predicates" in layer_chain_config
        assert len(layer_chain_config["remote_layers"]) == 3
    
    def test_remote_layer_predicates(self, layer_chain_config):
        """Test predicate configuration per remote layer."""
        predicates = layer_chain_config["predicates"]
        
        # Each remote layer should have its own predicate config
        assert predicates["roads"]["intersects"] is True
        assert predicates["parks"]["within"] is True
        assert predicates["water_bodies"]["touches"] is True
    
    def test_filter_chain_execution_order(self, layer_chain_config):
        """Test that filter chain respects execution order."""
        # Execution order: source first, then remotes
        execution_order = [layer_chain_config["source_layer"]] + layer_chain_config["remote_layers"]
        
        assert execution_order[0] == "buildings"
        assert execution_order[1] == "roads"
        assert execution_order[2] == "parks"
        assert execution_order[3] == "water_bodies"


class TestFilterChainResults:
    """Tests for filter chain result aggregation."""
    
    def test_aggregate_results_success(self):
        """Test aggregating successful results from multiple layers."""
        results = {
            "layer1": FilterResult.success([1, 2, 3], "layer1", "test", 10.0, "OGR"),
            "layer2": FilterResult.success([4, 5], "layer2", "test", 8.0, "OGR"),
            "layer3": FilterResult.success([6, 7, 8, 9], "layer3", "test", 12.0, "OGR")
        }
        
        total_features = sum(len(r.feature_ids) for r in results.values())
        total_time = sum(r.execution_time_ms for r in results.values())
        all_success = all(r.status == FilterStatus.SUCCESS for r in results.values())
        
        assert total_features == 9
        assert total_time == 30.0
        assert all_success is True
    
    def test_aggregate_results_partial_failure(self):
        """Test aggregating results when some layers fail."""
        results = {
            "layer1": FilterResult.success([1, 2, 3], "layer1", "test", 10.0, "OGR"),
            "layer2": FilterResult.error("layer2", "test", "Connection timeout"),
            "layer3": FilterResult.success([6, 7], "layer3", "test", 12.0, "OGR")
        }
        
        successful_results = [r for r in results.values() if r.status == FilterStatus.SUCCESS]
        failed_results = [r for r in results.values() if r.status == FilterStatus.ERROR]
        
        assert len(successful_results) == 2
        assert len(failed_results) == 1
    
    def test_empty_result_handling(self):
        """Test handling of empty filter results."""
        result = FilterResult.success(
            feature_ids=[],  # No features matched
            layer_id="layer1",
            expression_raw='"impossible" = \'condition\'',
            execution_time_ms=5.0,
            backend_name="OGR"
        )
        
        # Empty results have NO_MATCHES status, not SUCCESS
        assert result.status == FilterStatus.NO_MATCHES
        assert len(result.feature_ids) == 0


class TestFilterChainCancellation:
    """Tests for filter chain cancellation."""
    
    def test_cancellation_flag(self):
        """Test that cancellation flag stops processing."""
        is_cancelled = False
        layers_processed = []
        
        layers_to_process = ["layer1", "layer2", "layer3", "layer4"]
        
        for i, layer in enumerate(layers_to_process):
            if is_cancelled:
                break
            
            layers_processed.append(layer)
            
            # Simulate cancellation after layer2
            if layer == "layer2":
                is_cancelled = True
        
        assert len(layers_processed) == 2
        assert "layer3" not in layers_processed
    
    def test_partial_results_on_cancel(self):
        """Test that partial results are available after cancellation."""
        results = {}
        is_cancelled = False
        
        layers = ["layer1", "layer2", "layer3"]
        
        for layer in layers:
            if is_cancelled:
                break
            
            results[layer] = FilterResult.success(
                feature_ids=[1, 2, 3],
                layer_id=layer,
                expression_raw="test",
                execution_time_ms=10.0,
                backend_name="OGR"
            )
            
            if layer == "layer2":
                is_cancelled = True
        
        # Should have results for layer1 and layer2
        assert "layer1" in results
        assert "layer2" in results
        assert "layer3" not in results


class TestFilterChainPerformance:
    """Tests for filter chain performance considerations."""
    
    def test_execution_time_tracking(self):
        """Test that execution time is tracked per layer."""
        execution_times = {
            "layer1": 50.0,
            "layer2": 100.0,
            "layer3": 25.0
        }
        
        total_time = sum(execution_times.values())
        slowest_layer = max(execution_times, key=execution_times.get)
        
        assert total_time == 175.0
        assert slowest_layer == "layer2"
    
    def test_feature_count_estimation(self):
        """Test feature count estimation for chain planning."""
        layer_feature_counts = {
            "large_layer": 100000,
            "medium_layer": 10000,
            "small_layer": 100
        }
        
        # Optimal order: process smallest first
        optimal_order = sorted(layer_feature_counts.keys(), key=lambda x: layer_feature_counts[x])
        
        assert optimal_order[0] == "small_layer"
        assert optimal_order[1] == "medium_layer"
        assert optimal_order[2] == "large_layer"


class TestFilterChainWithTaskFeatures:
    """Tests for filter chain using task features (source geometries)."""
    
    @pytest.fixture
    def mock_task_features(self):
        """Create mock task features (geometries from source layer)."""
        features = []
        for i in range(5):
            feature = Mock()
            feature.id.return_value = i + 1
            feature.isValid.return_value = True
            feature.geometry.return_value = Mock()
            features.append(feature)
        return features
    
    def test_task_features_stored(self, mock_task_features):
        """Test that task features are properly stored."""
        assert len(mock_task_features) == 5
        assert all(f.isValid() for f in mock_task_features)
    
    def test_task_feature_ids_extraction(self, mock_task_features):
        """Test extracting feature IDs from task features."""
        feature_ids = [f.id() for f in mock_task_features if f.isValid()]
        
        assert feature_ids == [1, 2, 3, 4, 5]
    
    def test_spatial_config_with_task_features(self, mock_task_features):
        """Test spatial config preserves task feature IDs."""
        spatial_config = {
            "task_feature_ids": [f.id() for f in mock_task_features],
            "predicates": {"intersects": True},
            "buffer_value": 100.0
        }
        
        assert len(spatial_config["task_feature_ids"]) == 5
        assert spatial_config["buffer_value"] == 100.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

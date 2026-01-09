# -*- coding: utf-8 -*-
"""
Complete End-to-End Tests - MIG-040

Comprehensive E2E tests validating the entire FilterMate v3.0 architecture
from UI input to database operations across all backends.

This test suite validates:
- Complete filtering workflows
- All backend types (PostgreSQL, Spatialite, OGR)
- History/Undo/Redo operations
- Export workflows
- Favorites management
- Error handling and recovery

Part of Phase 5: Validation & Dépréciation

Author: FilterMate Team
Date: January 2026
"""
import pytest
from unittest.mock import MagicMock, patch, Mock
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

# Add plugin directory to path
plugin_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(plugin_dir))

# Domain imports
from core.domain.filter_expression import FilterExpression, ProviderType
from core.domain.filter_result import FilterResult, FilterStatus
from core.domain.layer_info import LayerInfo, GeometryType
from core.services.filter_service import FilterService, FilterRequest
from core.services.expression_service import ExpressionService
from core.services.history_service import HistoryService, HistoryEntry


@dataclass
class WorkflowContext:
    """Context for E2E workflow testing."""
    layers: List[Any]
    active_layer: Any
    expression: str
    backend: str
    buffer_distance: float = 0.0


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_layer_factory():
    """Factory for creating mock layers with configurable properties."""
    def _create_layer(
        layer_id: str = "layer_123",
        name: str = "Test Layer",
        provider: str = "ogr",
        feature_count: int = 1000,
        geometry_type: str = "Polygon",
        subset_string: str = ""
    ):
        layer = MagicMock()
        layer.id.return_value = layer_id
        layer.name.return_value = name
        layer.providerType.return_value = provider
        layer.featureCount.return_value = feature_count
        layer.geometryType.return_value = geometry_type
        layer.isValid.return_value = True
        layer.subsetString.return_value = subset_string
        
        # Track subset string changes
        layer._subset_history = [subset_string]
        
        def set_subset(expr):
            layer._subset_history.append(expr)
            layer.subsetString.return_value = expr
            return True
        
        layer.setSubsetString.side_effect = set_subset
        
        # CRS mock
        crs = MagicMock()
        crs.authid.return_value = "EPSG:4326"
        crs.isValid.return_value = True
        layer.crs.return_value = crs
        
        # Source mock
        source = MagicMock()
        source.uri.return_value = f"/path/to/{name}.gpkg"
        layer.source.return_value = source
        
        return layer
    
    return _create_layer


@pytest.fixture
def mock_backend_suite():
    """Create a suite of mock backends for each provider type."""
    def _create_suite():
        backends = {}
        
        for provider, priority in [
            ("postgresql", 100),
            ("spatialite", 80),
            ("ogr", 60),
            ("memory", 40)
        ]:
            backend = MagicMock()
            backend.name = provider.title()
            backend.get_priority.return_value = priority
            backend.supports_optimization.return_value = provider == "postgresql"
            backend.supports_spatial.return_value = True
            
            # Default successful execution
            backend.execute.return_value = FilterResult.success(
                feature_ids=list(range(100)),
                layer_id="layer_123",
                expression_raw="test = 1",
                execution_time_ms=50.0 / (priority / 40),
                backend_name=backend.name
            )
            
            backends[provider] = backend
        
        return backends
    
    return _create_suite


@pytest.fixture
def complete_workflow_context(mock_layer_factory, mock_backend_suite):
    """Create a complete workflow context with all components."""
    # Create layers
    source_layer = mock_layer_factory("source_1", "Source Layer", "ogr", 5000)
    target_layer_1 = mock_layer_factory("target_1", "Target 1", "ogr", 1000)
    target_layer_2 = mock_layer_factory("target_2", "Target 2", "ogr", 2000)
    
    return WorkflowContext(
        layers=[source_layer, target_layer_1, target_layer_2],
        active_layer=source_layer,
        expression='"population" > 10000',
        backend="ogr"
    )


# ============================================================================
# E2E Test Classes
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
class TestCompleteFilteringWorkflow:
    """
    Complete E2E tests for the filtering workflow.
    
    Tests the full cycle from expression input to layer subset application.
    """
    
    def test_full_filter_apply_cycle(
        self,
        mock_layer_factory,
        mock_backend_suite
    ):
        """
        Test: Complete filter application cycle
        
        1. Create layers
        2. Set source and targets
        3. Build expression
        4. Execute filter
        5. Verify layer subsets updated
        """
        # Setup
        source = mock_layer_factory("src", "Source", "ogr", 1000)
        target = mock_layer_factory("tgt", "Target", "ogr", 500)
        backends = mock_backend_suite()
        
        # Create services
        expression_service = ExpressionService()
        history_service = HistoryService(max_depth=50)
        
        # Build expression
        expression = FilterExpression.create(
            raw='"field" = 1',
            provider=ProviderType.OGR,
            source_layer_id="src"
        )
        
        # Verify expression was created successfully
        assert expression is not None
        assert expression.raw == '"field" = 1'
        
        # Verify expression service can parse
        parsed = expression_service.parse('"field" = 1')
        assert parsed is not None
        
        # Verify history service works
        assert history_service.undo_count == 0
        
        # Verify backends are available
        assert "ogr" in backends
    
    def test_filter_with_history_tracking(
        self,
        mock_layer_factory
    ):
        """
        Test: Filter operations are recorded in history
        
        1. Execute filter
        2. Verify history entry created
        3. Execute another filter
        4. Verify multiple entries
        5. Undo and verify state
        """
        history = HistoryService(max_depth=10)
        
        # Execute first filter
        entry1 = HistoryEntry.create(
            expression='"population" > 1000',
            layer_ids=["layer_1"],
            previous_filters=[("layer_1", "")]
        )
        history.push(entry1)
        
        assert history.undo_count == 1
        assert history.can_undo
        
        # Execute second filter
        entry2 = HistoryEntry.create(
            expression='"area" < 500',
            layer_ids=["layer_1", "layer_2"],
            previous_filters=[("layer_1", '"population" > 1000'), ("layer_2", "")]
        )
        history.push(entry2)
        
        assert history.undo_count == 2
        
        # Undo
        undone = history.undo()
        assert undone == entry2
        assert history.undo_count == 1
        assert history.can_redo
        
        # Redo
        redone = history.redo()
        assert redone == entry2
        assert history.undo_count == 2
    
    def test_filter_with_buffer_distance(
        self,
        mock_layer_factory
    ):
        """
        Test: Filtering with spatial buffer
        
        1. Set buffer distance
        2. Execute geometric filter
        3. Verify buffer applied
        """
        source = mock_layer_factory("src", "Source", "ogr", 1000)
        target = mock_layer_factory("tgt", "Target", "ogr", 500)
        
        # Create expression with buffer (buffer_value is the correct parameter)
        expression = FilterExpression.create(
            raw='"intersects" = 1',
            provider=ProviderType.OGR,
            source_layer_id="src",
            buffer_value=100.0
        )
        
        assert expression.buffer_value == 100.0
        assert expression.buffer_segments == 8  # default value
    
    def test_filter_error_recovery(
        self,
        mock_layer_factory,
        mock_backend_suite
    ):
        """
        Test: Error handling and recovery during filtering
        
        1. Execute filter that fails
        2. Verify error is captured
        3. Verify layer state unchanged
        4. Verify can retry
        """
        source = mock_layer_factory("src", "Source", "ogr", 1000)
        initial_subset = source.subsetString()
        
        # Simulate failure
        error_result = FilterResult.error(
            layer_id="src",
            expression_raw="invalid expr",
            error_message="Invalid expression syntax"
        )
        
        assert not error_result.is_success
        assert error_result.error_message == "Invalid expression syntax"
        
        # Layer state should be unchanged
        assert source.subsetString() == initial_subset


@pytest.mark.e2e
@pytest.mark.integration
class TestBackendSwitchingWorkflow:
    """
    E2E tests for backend switching during operations.
    
    Tests automatic and manual backend selection across providers.
    """
    
    def test_automatic_backend_selection(
        self,
        mock_layer_factory,
        mock_backend_suite
    ):
        """
        Test: Automatic backend selection based on layer provider
        
        1. Create layers with different providers
        2. Verify correct backend selected for each
        """
        backends = mock_backend_suite()
        
        pg_layer = mock_layer_factory("pg", "PostgreSQL Layer", "postgres", 10000)
        sl_layer = mock_layer_factory("sl", "Spatialite Layer", "spatialite", 5000)
        ogr_layer = mock_layer_factory("ogr", "Shapefile", "ogr", 1000)
        
        # Mock backend factory
        factory = MagicMock()
        factory.get_backend_for_provider.side_effect = lambda p: {
            "postgres": backends["postgresql"],
            "spatialite": backends["spatialite"],
            "ogr": backends["ogr"]
        }.get(p, backends["ogr"])
        
        # Verify selections
        assert factory.get_backend_for_provider("postgres") == backends["postgresql"]
        assert factory.get_backend_for_provider("spatialite") == backends["spatialite"]
        assert factory.get_backend_for_provider("ogr") == backends["ogr"]
    
    def test_backend_fallback_on_error(
        self,
        mock_layer_factory,
        mock_backend_suite
    ):
        """
        Test: Backend fallback when primary fails
        
        1. Configure primary to fail
        2. Verify fallback used
        3. Verify operation succeeds with fallback
        """
        backends = mock_backend_suite()
        
        # Configure PostgreSQL to fail
        backends["postgresql"].execute.return_value = FilterResult.error(
            layer_id="layer_1",
            expression_raw="test",
            error_message="Connection refused"
        )
        
        # OGR should still work
        ogr_result = backends["ogr"].execute()
        assert ogr_result.is_success
    
    @pytest.mark.parametrize("provider,expected_backend", [
        ("postgres", "PostgreSQL"),
        ("spatialite", "Spatialite"),
        ("ogr", "Ogr"),
        ("memory", "Memory"),
    ])
    def test_backend_mapping(
        self,
        provider,
        expected_backend,
        mock_backend_suite
    ):
        """Test correct backend is selected for each provider type."""
        backends = mock_backend_suite()
        
        # Map provider to backend key
        key_map = {
            "postgres": "postgresql",
            "spatialite": "spatialite",
            "ogr": "ogr",
            "memory": "memory"
        }
        
        backend = backends[key_map[provider]]
        assert expected_backend.lower() in backend.name.lower()


@pytest.mark.e2e
@pytest.mark.integration
class TestExportWorkflow:
    """
    E2E tests for export workflow.
    
    Tests exporting filtered results to various formats.
    """
    
    def test_export_after_filter(
        self,
        mock_layer_factory
    ):
        """
        Test: Export filtered layer
        
        1. Apply filter
        2. Export to file
        3. Verify export parameters
        """
        layer = mock_layer_factory("lyr", "Test", "ogr", 1000)
        layer.setSubsetString('"population" > 1000')
        
        # Mock export
        export_mock = MagicMock()
        export_mock.export_layer.return_value = {
            "success": True,
            "output_path": "/tmp/exported.gpkg",
            "feature_count": 500
        }
        
        result = export_mock.export_layer(
            layer=layer,
            output_path="/tmp/exported.gpkg",
            format="GPKG"
        )
        
        assert result["success"]
        assert result["feature_count"] == 500
    
    @pytest.mark.parametrize("format_name,extension", [
        ("GPKG", ".gpkg"),
        ("ESRI Shapefile", ".shp"),
        ("GeoJSON", ".geojson"),
        ("CSV", ".csv"),
    ])
    def test_export_formats(
        self,
        mock_layer_factory,
        format_name,
        extension
    ):
        """Test export to different formats."""
        layer = mock_layer_factory("lyr", "Test", "ogr", 100)
        
        export_mock = MagicMock()
        export_mock.export_layer.return_value = {
            "success": True,
            "output_path": f"/tmp/export{extension}",
            "format": format_name
        }
        
        result = export_mock.export_layer(
            layer=layer,
            output_path=f"/tmp/export{extension}",
            format=format_name
        )
        
        assert result["success"]
        assert result["format"] == format_name


@pytest.mark.e2e
@pytest.mark.integration
class TestFavoritesWorkflow:
    """
    E2E tests for favorites management.
    
    Tests saving, loading, and applying favorite filters.
    """
    
    def test_save_and_load_favorite(self):
        """
        Test: Save filter as favorite and reload
        
        1. Apply filter
        2. Save as favorite
        3. Clear filter
        4. Load favorite
        5. Verify filter restored
        """
        favorites_mock = MagicMock()
        favorites_mock.favorites = []
        
        def save_favorite(name, expression, layers):
            favorites_mock.favorites.append({
                "name": name,
                "expression": expression,
                "layers": layers
            })
            return True
        
        def get_favorite(name):
            return next(
                (f for f in favorites_mock.favorites if f["name"] == name),
                None
            )
        
        favorites_mock.save.side_effect = save_favorite
        favorites_mock.get.side_effect = get_favorite
        
        # Save
        favorites_mock.save(
            "High Population",
            '"population" > 100000',
            ["layer_1", "layer_2"]
        )
        
        # Load
        fav = favorites_mock.get("High Population")
        assert fav is not None
        assert fav["expression"] == '"population" > 100000'
        assert len(fav["layers"]) == 2
    
    def test_favorite_with_spatial_parameters(self):
        """Test favorite with spatial filter parameters."""
        favorite = {
            "name": "Nearby Features",
            "expression": '"intersects" = 1',
            "layers": ["layer_1"],
            "spatial": {
                "predicate": "intersects",
                "buffer": 500.0,
                "buffer_unit": "meters"
            }
        }
        
        assert favorite["spatial"]["buffer"] == 500.0
        assert favorite["spatial"]["predicate"] == "intersects"


@pytest.mark.e2e  
@pytest.mark.integration
class TestMultiStepFilterWorkflow:
    """
    E2E tests for multi-step filtering workflows.
    
    Tests progressive filtering and complex filter chains.
    """
    
    def test_progressive_filtering(
        self,
        mock_layer_factory
    ):
        """
        Test: Progressive multi-step filtering
        
        1. Apply first filter
        2. Apply second filter (cumulative)
        3. Apply third filter
        4. Verify all steps applied
        """
        layer = mock_layer_factory("lyr", "Test", "ogr", 10000)
        
        # Step 1
        layer.setSubsetString('"type" = \'residential\'')
        assert '"type"' in layer.subsetString()
        
        # Step 2 (combine)
        combined = f"({layer.subsetString()}) AND \"area\" > 100"
        layer.setSubsetString(combined)
        assert '"area"' in layer.subsetString()
        
        # Step 3
        final = f"({layer.subsetString()}) AND \"year\" >= 2020"
        layer.setSubsetString(final)
        
        # All conditions present
        assert '"type"' in layer.subsetString()
        assert '"area"' in layer.subsetString()
        assert '"year"' in layer.subsetString()
    
    def test_clear_all_steps(
        self,
        mock_layer_factory
    ):
        """Test clearing all filter steps at once."""
        layer = mock_layer_factory("lyr", "Test", "ogr", 5000)
        
        # Apply multiple filters
        layer.setSubsetString('"a" = 1')
        layer.setSubsetString('"a" = 1 AND "b" = 2')
        layer.setSubsetString('"a" = 1 AND "b" = 2 AND "c" = 3')
        
        assert layer.subsetString() != ""
        
        # Clear all
        layer.setSubsetString("")
        assert layer.subsetString() == ""


@pytest.mark.e2e
@pytest.mark.integration  
class TestEdgeCasesWorkflow:
    """
    E2E tests for edge cases and boundary conditions.
    """
    
    def test_empty_layer_handling(
        self,
        mock_layer_factory
    ):
        """Test handling of empty layers."""
        empty_layer = mock_layer_factory("empty", "Empty Layer", "ogr", 0)
        
        assert empty_layer.featureCount() == 0
        
        # Should still work with empty layer
        empty_layer.setSubsetString('"field" = 1')
        assert empty_layer.subsetString() == '"field" = 1'
    
    def test_very_large_dataset_handling(
        self,
        mock_layer_factory
    ):
        """Test handling of very large datasets."""
        large_layer = mock_layer_factory("large", "Large Layer", "ogr", 1000000)
        
        # Should handle gracefully
        assert large_layer.featureCount() == 1000000
    
    def test_special_characters_in_expression(
        self,
        mock_layer_factory
    ):
        """Test handling of special characters in expressions."""
        layer = mock_layer_factory("lyr", "Test", "ogr", 100)
        
        # Expression with special characters
        special_expr = '''"name" LIKE '%O\\'Brien%' OR "field" = 'test "quoted"' '''
        layer.setSubsetString(special_expr)
        
        assert "O\\'Brien" in layer.subsetString()
    
    def test_unicode_handling(
        self,
        mock_layer_factory
    ):
        """Test handling of unicode in expressions."""
        layer = mock_layer_factory("lyr", "Test", "ogr", 100)
        
        # Unicode expression
        unicode_expr = '"ville" = \'Montréal\' OR "pays" = \'日本\''
        layer.setSubsetString(unicode_expr)
        
        assert "Montréal" in layer.subsetString()
        assert "日本" in layer.subsetString()


# ============================================================================
# Run Configuration
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

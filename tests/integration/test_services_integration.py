# -*- coding: utf-8 -*-
"""
Integration Tests for Core Services.

Tests the integration between core services (FilterService, HistoryService, etc.)
without QGIS dependencies using mocks.

Author: FilterMate Team
Date: January 2026
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime

# Add plugin directory to path
plugin_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(plugin_dir))

from core.domain.filter_expression import FilterExpression, ProviderType
from core.domain.filter_result import FilterResult, FilterStatus
from core.domain.layer_info import LayerInfo, GeometryType
from core.domain.optimization_config import OptimizationConfig
from core.services.filter_service import FilterService, FilterRequest, FilterResponse
from core.services.expression_service import ExpressionService
from core.services.history_service import HistoryService, HistoryEntry


class TestFilterServiceIntegration:
    """Integration tests for FilterService."""
    
    @pytest.fixture
    def mock_backend_factory(self):
        """Create a mock backend factory."""
        factory = MagicMock()
        
        # Create mock backend
        mock_backend = MagicMock()
        mock_backend.execute.return_value = FilterResult.success(
            feature_ids=[1, 2, 3, 4, 5],
            layer_id="layer_123",
            expression_raw="test",
            execution_time_ms=10.0,
            backend_name="MockBackend"
        )
        mock_backend.get_info.return_value = MagicMock(name="MockBackend")
        
        factory.get_backend.return_value = mock_backend
        factory.get_backend_for_provider.return_value = mock_backend
        factory.select_provider_type.return_value = ProviderType.OGR
        
        return factory
    
    @pytest.fixture
    def expression_service(self):
        """Create expression service."""
        return ExpressionService()
    
    @pytest.fixture
    def filter_service(self, mock_backend_factory, expression_service):
        """Create filter service with mocks."""
        return FilterService(
            backend_factory=mock_backend_factory,
            expression_service=expression_service,
            cache=None
        )
    
    @pytest.fixture
    def sample_layer_info(self):
        """Create a sample layer info."""
        return LayerInfo(
            layer_id="layer_123",
            name="Test Layer",
            provider_type=ProviderType.OGR,
            feature_count=1000,
            geometry_type=GeometryType.POLYGON,
            crs_auth_id="EPSG:4326"
        )
    
    @pytest.fixture
    def sample_expression(self):
        """Create a sample expression."""
        return FilterExpression.create(
            raw='"field" = 1',
            provider=ProviderType.OGR,
            source_layer_id="layer_123"
        )
    
    def test_apply_filter_success(
        self, 
        filter_service, 
        sample_expression, 
        sample_layer_info
    ):
        """Test successful filter application."""
        request = FilterRequest(
            expression=sample_expression,
            source_layer_id="layer_123",
            target_layer_ids=["layer_123"]
        )
        
        # We need to mock the layer repository or skip this test
        # since FilterService needs to resolve layer IDs to LayerInfo
        with patch.object(filter_service, '_get_layer_info') as mock_get:
            mock_get.return_value = sample_layer_info
            
            response = filter_service.apply_filter(request)
            
            assert response.is_success
            assert response.total_matches > 0
    
    def test_filter_service_validates_expression(
        self,
        filter_service,
        sample_layer_info
    ):
        """Test that service validates expressions."""
        # Empty expression should fail validation
        with pytest.raises(ValueError):
            FilterExpression.create(
                raw="",
                provider=ProviderType.OGR,
                source_layer_id="layer_123"
            )
    
    def test_filter_service_with_cache(self):
        """Test filter service with cache."""
        mock_factory = MagicMock()
        mock_backend = MagicMock()
        mock_backend.execute.return_value = FilterResult.success(
            feature_ids=[1, 2],
            layer_id="layer_1",
            expression_raw="test"
        )
        mock_factory.get_backend.return_value = mock_backend
        mock_factory.select_provider_type.return_value = ProviderType.MEMORY
        
        mock_cache = MagicMock()
        mock_cache.get.return_value = None  # Cache miss
        
        service = FilterService(
            backend_factory=mock_factory,
            expression_service=ExpressionService(),
            cache=mock_cache
        )
        
        # Service should use cache
        assert service._cache is mock_cache


class TestHistoryServiceIntegration:
    """Integration tests for HistoryService."""
    
    @pytest.fixture
    def history_service(self):
        """Create history service."""
        return HistoryService(max_depth=10)
    
    def test_full_undo_redo_cycle(self, history_service):
        """Test complete undo/redo cycle."""
        # Push multiple entries
        for i in range(5):
            entry = HistoryEntry.create(
                expression=f"expr_{i}",
                layer_ids=[f"layer_{i}"],
                previous_filters=[(f"layer_{i}", f"old_{i}")]
            )
            history_service.push(entry)
        
        assert history_service.undo_count == 5
        
        # Undo all
        undone = []
        while history_service.can_undo:
            undone.append(history_service.undo())
        
        assert len(undone) == 5
        assert history_service.redo_count == 5
        
        # Redo all
        redone = []
        while history_service.can_redo:
            redone.append(history_service.redo())
        
        assert len(redone) == 5
        assert history_service.undo_count == 5
    
    def test_new_action_clears_redo(self, history_service):
        """Test that new action clears redo stack."""
        # Setup
        entry1 = HistoryEntry.create(
            expression="first",
            layer_ids=["layer_1"],
            previous_filters=[]
        )
        entry2 = HistoryEntry.create(
            expression="second",
            layer_ids=["layer_1"],
            previous_filters=[]
        )
        
        history_service.push(entry1)
        history_service.push(entry2)
        
        # Undo one
        history_service.undo()
        assert history_service.can_redo
        
        # New action should clear redo
        entry3 = HistoryEntry.create(
            expression="third",
            layer_ids=["layer_1"],
            previous_filters=[]
        )
        history_service.push(entry3)
        
        assert not history_service.can_redo
    
    def test_history_callback(self, history_service):
        """Test history change callback."""
        callback_count = [0]
        
        def on_change(state):
            callback_count[0] += 1
        
        service = HistoryService(max_depth=10, on_change=on_change)
        
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_1"],
            previous_filters=[]
        )
        
        service.push(entry)  # Callback 1
        service.undo()  # Callback 2
        service.redo()  # Callback 3
        
        assert callback_count[0] == 3


class TestExpressionServiceIntegration:
    """Integration tests for ExpressionService."""
    
    @pytest.fixture
    def expression_service(self):
        """Create expression service."""
        return ExpressionService()
    
    def test_validate_and_parse_workflow(self, expression_service):
        """Test validation followed by parsing."""
        expr = '"name" LIKE \'%test%\' AND "value" > 100'
        
        # Validate
        result = expression_service.validate(expr)
        assert result.is_valid
        
        # Parse
        parsed = expression_service.parse(expr)
        assert "name" in parsed.fields
        assert "value" in parsed.fields
        assert "AND" in parsed.operators
        assert "LIKE" in parsed.operators
    
    def test_validate_parse_convert_workflow(self, expression_service):
        """Test full validation -> parse -> SQL conversion."""
        expr = '"population" > 10000'
        
        # Validate
        validation = expression_service.validate(expr)
        assert validation.is_valid
        
        # Parse
        parsed = expression_service.parse(expr)
        assert "population" in parsed.fields
        assert not parsed.is_spatial
        
        # Convert to SQL
        sql = expression_service.to_sql(expr, ProviderType.POSTGRESQL)
        assert "population" in sql
        assert "10000" in sql
    
    def test_spatial_expression_workflow(self, expression_service):
        """Test spatial expression handling."""
        expr = 'intersects($geometry, @selected_geometry)'
        
        # Validate
        validation = expression_service.validate(expr)
        assert validation.is_valid
        
        # Parse
        parsed = expression_service.parse(expr)
        assert parsed.is_spatial
        assert parsed.has_geometry_reference
        assert parsed.has_layer_reference


class TestServicesEndToEnd:
    """End-to-end tests combining multiple services."""
    
    def test_filter_then_history(self):
        """Test filtering followed by history management."""
        # Create services
        history = HistoryService(max_depth=10)
        expr_service = ExpressionService()
        
        # Validate expression
        expression = '"type" = \'residential\''
        validation = expr_service.validate(expression)
        assert validation.is_valid
        
        # Parse for analysis
        parsed = expr_service.parse(expression)
        assert "type" in parsed.fields
        
        # Record in history (simulating filter execution)
        entry = HistoryEntry.create(
            expression=expression,
            layer_ids=["buildings_layer"],
            previous_filters=[("buildings_layer", "")],
            description=f"Filter: {expression[:30]}"
        )
        history.push(entry)
        
        # Verify history state
        assert history.can_undo
        state = history.get_state()
        assert "Filter:" in state.undo_description
        
        # Undo
        undone = history.undo()
        assert undone.expression == expression
        
        # Get previous filter to restore
        previous = undone.get_previous_filter("buildings_layer")
        assert previous == ""
    
    def test_complex_filter_workflow(self):
        """Test complex filtering workflow with multiple layers."""
        history = HistoryService(max_depth=10)
        expr_service = ExpressionService()
        
        # First filter
        expr1 = '"category" IN (\'A\', \'B\', \'C\')'
        validation = expr_service.validate(expr1)
        assert validation.is_valid
        
        entry1 = HistoryEntry.create(
            expression=expr1,
            layer_ids=["layer_1", "layer_2"],
            previous_filters=[
                ("layer_1", ""),
                ("layer_2", '"old" = 1')
            ]
        )
        history.push(entry1)
        
        # Second filter
        expr2 = '"status" = \'active\''
        entry2 = HistoryEntry.create(
            expression=expr2,
            layer_ids=["layer_1"],
            previous_filters=[("layer_1", expr1)]
        )
        history.push(entry2)
        
        # Undo second filter
        undone2 = history.undo()
        assert undone2.expression == expr2
        
        # Verify previous filter
        prev = undone2.get_previous_filter("layer_1")
        assert prev == expr1
        
        # Redo
        redone = history.redo()
        assert redone.expression == expr2

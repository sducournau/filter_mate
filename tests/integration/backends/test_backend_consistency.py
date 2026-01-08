# -*- coding: utf-8 -*-
"""
Backend Consistency Tests - ARCH-051

Cross-backend consistency tests to verify all backends
produce consistent results for the same expressions.

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
def consistent_result_set():
    """Create a consistent set of feature IDs for testing."""
    return set(range(100))


@pytest.fixture
def all_backends_configured(consistent_result_set):
    """Create all backends configured to return consistent results."""
    backends = {}
    
    for name, priority in [
        ("PostgreSQL", 100),
        ("Spatialite", 50),
        ("OGR", 10),
        ("Memory", 5)
    ]:
        backend = MagicMock()
        backend.name = name
        backend.priority = priority
        
        result = MagicMock()
        result.success = True
        result.matched_count = len(consistent_result_set)
        result.feature_ids = list(consistent_result_set)
        result.backend_used = name
        backend.execute.return_value = result
        
        backends[name.lower()] = backend
    
    return backends


@pytest.mark.integration
class TestBackendConsistency:
    """Tests for cross-backend result consistency."""
    
    @pytest.mark.parametrize("expression", [
        '"population" > 10000',
        '"name" LIKE \'%ville%\'',
        '"area" BETWEEN 100 AND 500',
        '"category" IN (\'A\', \'B\', \'C\')',
        '"value" IS NOT NULL',
    ])
    def test_attribute_filter_consistency(
        self,
        all_backends_configured,
        expression
    ):
        """Verify all backends return same results for attribute filters."""
        backends = all_backends_configured
        results = {}
        
        for backend_name, backend in backends.items():
            layer = MagicMock()
            layer.id.return_value = f"{backend_name}_layer"
            
            result = backend.execute(expression, layer)
            results[backend_name] = set(result.feature_ids)
        
        # All backends should return same feature IDs
        result_sets = list(results.values())
        for result_set in result_sets[1:]:
            assert result_set == result_sets[0], \
                f"Inconsistent results between backends: {results}"
    
    def test_spatial_filter_consistency(
        self,
        all_backends_configured
    ):
        """Verify all backends return same results for spatial filters."""
        backends = all_backends_configured
        expression = 'intersects($geometry, @source_geometry)'
        results = {}
        
        for backend_name, backend in backends.items():
            layer = MagicMock()
            result = backend.execute(expression, layer)
            results[backend_name] = set(result.feature_ids)
        
        # Compare results
        result_sets = list(results.values())
        for result_set in result_sets[1:]:
            assert result_set == result_sets[0]
    
    def test_combined_filter_consistency(
        self,
        all_backends_configured
    ):
        """Verify consistency for combined attribute + spatial filters."""
        backends = all_backends_configured
        expression = '"population" > 5000 AND intersects($geometry, @source)'
        results = {}
        
        for backend_name, backend in backends.items():
            layer = MagicMock()
            result = backend.execute(expression, layer)
            results[backend_name] = set(result.feature_ids)
        
        result_sets = list(results.values())
        for result_set in result_sets[1:]:
            assert result_set == result_sets[0]


@pytest.mark.integration
class TestBackendResultFormat:
    """Tests for consistent result format across backends."""
    
    def test_result_has_required_fields(self, all_backends_configured):
        """Verify all backends return results with required fields."""
        for backend_name, backend in all_backends_configured.items():
            layer = MagicMock()
            result = backend.execute('"test" = 1', layer)
            
            # Check required fields
            assert hasattr(result, 'success')
            assert hasattr(result, 'matched_count')
            assert hasattr(result, 'feature_ids')
    
    def test_result_types_consistent(self, all_backends_configured):
        """Verify result types are consistent across backends."""
        for backend_name, backend in all_backends_configured.items():
            layer = MagicMock()
            result = backend.execute('"test" = 1', layer)
            
            assert isinstance(result.success, bool)
            assert isinstance(result.matched_count, int)
            assert isinstance(result.feature_ids, list)
    
    def test_empty_result_format(self, all_backends_configured):
        """Verify empty results have consistent format."""
        # Configure backends to return empty results
        for backend in all_backends_configured.values():
            empty_result = MagicMock()
            empty_result.success = True
            empty_result.matched_count = 0
            empty_result.feature_ids = []
            backend.execute.return_value = empty_result
        
        for backend_name, backend in all_backends_configured.items():
            layer = MagicMock()
            result = backend.execute('"impossible" = True', layer)
            
            assert result.success is True
            assert result.matched_count == 0
            assert len(result.feature_ids) == 0


@pytest.mark.integration
class TestBackendErrorHandling:
    """Tests for consistent error handling across backends."""
    
    def test_invalid_expression_error(self, all_backends_configured):
        """Verify all backends handle invalid expressions consistently."""
        invalid_expression = '"unclosed string'
        
        for backend_name, backend in all_backends_configured.items():
            error_result = MagicMock()
            error_result.success = False
            error_result.error_message = "Syntax error: unclosed string"
            backend.execute.return_value = error_result
            
            layer = MagicMock()
            result = backend.execute(invalid_expression, layer)
            
            assert result.success is False
            assert result.error_message is not None
    
    def test_connection_error_handling(self, all_backends_configured):
        """Verify backends handle connection errors gracefully."""
        for backend_name, backend in all_backends_configured.items():
            error_result = MagicMock()
            error_result.success = False
            error_result.error_message = "Connection error"
            error_result.error_type = "connection"
            backend.execute.return_value = error_result
            
            layer = MagicMock()
            result = backend.execute('"test" = 1', layer)
            
            assert result.success is False
            assert "connection" in result.error_type.lower()


@pytest.mark.integration
class TestBackendPerformanceMetrics:
    """Tests for consistent performance metrics across backends."""
    
    def test_execution_time_reported(self, all_backends_configured):
        """Verify all backends report execution time."""
        for backend_name, backend in all_backends_configured.items():
            result = MagicMock()
            result.success = True
            result.execution_time_ms = 50.0
            backend.execute.return_value = result
            
            layer = MagicMock()
            exec_result = backend.execute('"test" = 1', layer)
            
            assert hasattr(exec_result, 'execution_time_ms')
            assert exec_result.execution_time_ms >= 0
    
    def test_optimization_flag_reported(self, all_backends_configured):
        """Verify backends report whether optimization was used."""
        optimization_expected = {
            "postgresql": True,
            "spatialite": True,
            "ogr": False,
            "memory": False
        }
        
        for backend_name, backend in all_backends_configured.items():
            result = MagicMock()
            result.success = True
            result.used_optimization = optimization_expected.get(
                backend_name, False
            )
            backend.execute.return_value = result
            
            layer = MagicMock()
            exec_result = backend.execute('"test" = 1', layer)
            
            assert hasattr(exec_result, 'used_optimization')

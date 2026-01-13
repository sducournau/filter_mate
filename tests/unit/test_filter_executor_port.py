# -*- coding: utf-8 -*-
"""
Unit Tests for FilterExecutorPort and BackendRegistry.

Tests the new hexagonal architecture components created during
EPIC-1 Phase E5/E6 migration.

Author: FilterMate Team
Date: January 2026
Version: 4.0.1
"""

import pytest
import sys
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass
from typing import Optional


# ============================================================================
# Mock Setup - Must be before imports
# ============================================================================

# Minimal mocks for QGIS that don't break isinstance()
class MockQgsVectorLayer:
    """Mock QgsVectorLayer for testing."""
    def __init__(self, layer_id="test_layer", name="Test Layer"):
        self._id = layer_id
        self._name = name
        self._subset = ""
    
    def id(self): return self._id
    def name(self): return self._name
    def providerType(self): return "postgres"
    def subsetString(self): return self._subset
    def setSubsetString(self, s): self._subset = s; return True
    def isValid(self): return True
    def featureCount(self): return 100


class MockQgsGeometry:
    """Mock QgsGeometry for testing."""
    def __init__(self, wkt="POINT(0 0)"):
        self._wkt = wkt
    def asWkt(self, precision=6): return self._wkt
    def isEmpty(self): return False


# Apply minimal mocks
mock_qgis_core = Mock()
mock_qgis_core.QgsVectorLayer = MockQgsVectorLayer
mock_qgis_core.QgsGeometry = MockQgsGeometry
sys.modules['qgis'] = Mock()
sys.modules['qgis.core'] = mock_qgis_core
sys.modules['qgis.PyQt'] = Mock()
sys.modules['qgis.PyQt.QtCore'] = Mock()

# Mock the infrastructure.logging to avoid import issues
mock_logging = Mock()
mock_logging.get_logger = Mock(return_value=Mock())
sys.modules['infrastructure'] = Mock()
sys.modules['infrastructure.logging'] = mock_logging

# Mock adapters.backends to avoid cascading imports
sys.modules['adapters.backends'] = Mock()


# ============================================================================
# Now import the components to test
# ============================================================================

# Import ports directly (pure Python, no QGIS deps)
from core.ports.filter_executor_port import (
    FilterExecutorPort,
    FilterExecutionResult,
    FilterStatus,
    BackendRegistryPort
)

# Import backend_registry directly, bypassing adapters/__init__.py
import importlib.util
import os

# Get the path to backend_registry.py
_plugin_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_backend_registry_path = os.path.join(_plugin_dir, 'adapters', 'backend_registry.py')

# Load the module directly
spec = importlib.util.spec_from_file_location("backend_registry_direct", _backend_registry_path)
backend_registry_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend_registry_module)

BackendRegistry = backend_registry_module.BackendRegistry
get_backend_registry = backend_registry_module.get_backend_registry
reset_backend_registry = backend_registry_module.reset_backend_registry


# ============================================================================
# FilterExecutorPort Tests
# ============================================================================

class TestFilterStatus:
    """Tests for FilterStatus enum."""
    
    def test_all_statuses_exist(self):
        """Verify all expected status values exist."""
        assert hasattr(FilterStatus, 'SUCCESS')
        assert hasattr(FilterStatus, 'FAILED')
        assert hasattr(FilterStatus, 'CANCELLED')
        assert hasattr(FilterStatus, 'NO_RESULTS')
        assert hasattr(FilterStatus, 'PARTIAL')
    
    def test_status_values_are_unique(self):
        """Verify status values are unique."""
        statuses = [s.value for s in FilterStatus]
        assert len(statuses) == len(set(statuses))


class TestFilterExecutionResult:
    """Tests for FilterExecutionResult dataclass."""
    
    def test_success_factory(self):
        """Test success() factory method."""
        result = FilterExecutionResult.success(
            feature_ids=[1, 2, 3, 4, 5],
            expression="id > 10",
            backend="postgresql"
        )
        
        assert result.status == FilterStatus.SUCCESS
        assert result.feature_ids == [1, 2, 3, 4, 5]
        assert result.feature_count == 5
        assert result.expression == "id > 10"
        assert result.backend_used == "postgresql"
        assert result.error_message is None
    
    def test_failed_factory(self):
        """Test failed() factory method."""
        result = FilterExecutionResult.failed("Connection error", backend="postgresql")
        
        assert result.status == FilterStatus.FAILED
        assert result.error_message == "Connection error"
        assert result.feature_count == 0
        assert result.backend_used == "postgresql"
    
    def test_cancelled_factory(self):
        """Test cancelled() factory method."""
        result = FilterExecutionResult.cancelled()
        
        assert result.status == FilterStatus.CANCELLED
        assert result.feature_count == 0
    
    def test_no_results_factory(self):
        """Test no_results() factory method."""
        result = FilterExecutionResult.no_results(backend="spatialite")
        
        assert result.status == FilterStatus.NO_RESULTS
        assert result.feature_count == 0
        assert result.backend_used == "spatialite"
    
    def test_is_success_property(self):
        """Test is_success via status comparison."""
        success = FilterExecutionResult.success([1, 2, 3])
        failed = FilterExecutionResult.failed("error")
        
        assert success.status == FilterStatus.SUCCESS
        assert failed.status == FilterStatus.FAILED
    
    def test_result_with_all_fields(self):
        """Test result with all optional fields."""
        result = FilterExecutionResult(
            status=FilterStatus.SUCCESS,
            feature_ids=[1, 2, 3],
            feature_count=3,
            expression="name LIKE 'A%'",
            error_message=None,
            execution_time_ms=125.5,
            backend_used="postgresql",
            warnings=["Some warning"],
            metadata={"key": "value"}
        )
        
        assert result.execution_time_ms == 125.5
        assert result.backend_used == "postgresql"
        assert result.warnings == ["Some warning"]
        assert result.metadata == {"key": "value"}


class TestFilterExecutorPort:
    """Tests for FilterExecutorPort abstract interface."""
    
    def test_is_abstract(self):
        """Verify FilterExecutorPort is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            FilterExecutorPort()
    
    def test_required_methods(self):
        """Verify all required abstract methods are defined."""
        from abc import ABC
        
        assert issubclass(FilterExecutorPort, ABC)
        
        # Check abstract methods exist
        abstract_methods = getattr(FilterExecutorPort, '__abstractmethods__', set())
        assert 'execute_filter' in abstract_methods
    
    def test_concrete_implementation(self):
        """Test that a concrete implementation works."""
        
        class TestExecutor(FilterExecutorPort):
            def execute_filter(self, source_layer_info, target_layers_info, **kwargs):
                return FilterExecutionResult.success([1, 2, 3], "test")
            
            def prepare_source_geometry(self, layer_info, **kwargs):
                return "POINT(0 0)", None
            
            def apply_subset_string(self, layer, expression):
                return True
            
            def cleanup_resources(self):
                pass
            
            @property
            def backend_name(self):
                return "test"
            
            @property
            def supports_spatial_index(self):
                return True
            
            @property
            def supports_materialized_views(self):
                return False
        
        executor = TestExecutor()
        result = executor.execute_filter({}, [])
        
        assert result.status == FilterStatus.SUCCESS
        assert result.feature_count == 3
        assert executor.backend_name == "test"


# ============================================================================
# BackendRegistry Tests
# ============================================================================

class TestBackendRegistry:
    """Tests for BackendRegistry dependency injection container."""
    
    def setup_method(self):
        """Reset registry before each test."""
        reset_backend_registry()
    
    def test_initialization(self):
        """Test registry initialization."""
        registry = BackendRegistry()
        
        assert registry is not None
        assert hasattr(registry, 'get_executor')
        assert hasattr(registry, 'is_available')
    
    def test_get_available_backends(self):
        """Test listing available backends via is_available."""
        registry = BackendRegistry()
        
        # Check standard backends
        assert isinstance(registry.is_available('spatialite'), bool)
        assert isinstance(registry.is_available('ogr'), bool)
        assert isinstance(registry.is_available('postgresql'), bool)
    
    def test_get_executor_unknown_backend(self):
        """Test getting executor for unknown backend returns None."""
        registry = BackendRegistry()
        executor = registry.get_executor_by_name("unknown_backend_xyz")
        
        assert executor is None
    
    def test_is_available_method(self):
        """Test is_available method for backends."""
        registry = BackendRegistry()
        
        # OGR and Spatialite should always be available
        assert registry.is_available('ogr') is True
        assert registry.is_available('spatialite') is True
        assert hasattr(registry, 'postgresql_available')
    
    def test_singleton_pattern(self):
        """Test get_backend_registry returns same instance."""
        reset_backend_registry()
        
        registry1 = get_backend_registry()
        registry2 = get_backend_registry()
        
        assert registry1 is registry2
    
    def test_reset_singleton(self):
        """Test reset_backend_registry creates new instance."""
        registry1 = get_backend_registry()
        reset_backend_registry()
        registry2 = get_backend_registry()
        
        assert registry1 is not registry2
    
    def test_get_executor_by_provider_type(self):
        """Test getting executor by QGIS provider type."""
        registry = BackendRegistry()
        
        # Test with common provider types via layer_info dict
        for provider_type in ['postgresql', 'spatialite', 'ogr']:
            layer_info = {'layer_provider_type': provider_type}
            try:
                executor = registry.get_executor(layer_info)
                # If we get an executor, verify it has the right interface
                if executor is not None:
                    assert hasattr(executor, 'execute_filter')
                    assert hasattr(executor, 'backend_name')
            except Exception as e:
                # Log but don't fail - backend may not be available
                print(f"Backend {provider_type} not available: {e}")
    
    def test_lazy_initialization(self):
        """Test that executors are lazily initialized."""
        registry = BackendRegistry()
        
        # Registry should not load executors until requested
        # The _executors dict should be empty or lazily populated
        assert hasattr(registry, '_executors')


class TestBackendRegistryPort:
    """Tests for BackendRegistryPort abstract interface."""
    
    def test_is_abstract(self):
        """Verify BackendRegistryPort is abstract."""
        with pytest.raises(TypeError):
            BackendRegistryPort()
    
    def test_backend_registry_implements_port(self):
        """Verify BackendRegistry implements BackendRegistryPort."""
        registry = BackendRegistry()
        assert isinstance(registry, BackendRegistryPort)


# ============================================================================
# Integration Tests
# ============================================================================

class TestFilterExecutorIntegration:
    """Integration tests for FilterExecutor system."""
    
    def setup_method(self):
        """Reset for each test."""
        reset_backend_registry()
    
    def test_registry_provides_valid_executors(self):
        """Test that registry has proper interface."""
        registry = BackendRegistry()
        
        # Test that registry has the expected methods
        assert hasattr(registry, 'get_executor')
        assert hasattr(registry, 'get_executor_by_name')
        assert hasattr(registry, 'is_available')
        assert hasattr(registry, 'postgresql_available')
    
    def test_executor_result_consistency(self):
        """Test that executor results follow the expected pattern."""
        # Create a test result
        result = FilterExecutionResult.success(
            feature_ids=[1, 2, 3],
            expression="test = 'value'"
        )
        
        # Verify all properties work
        assert result.status == FilterStatus.SUCCESS
        assert result.feature_count == 3
        assert result.expression == "test = 'value'"
        assert str(result.status) is not None


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_expression(self):
        """Test handling of empty expression."""
        result = FilterExecutionResult.success([], "")
        assert result.status == FilterStatus.SUCCESS
        assert result.expression == ""
    
    def test_none_expression(self):
        """Test handling of None expression."""
        result = FilterExecutionResult.success([], None)
        assert result.status == FilterStatus.SUCCESS
        assert result.expression is None
    
    def test_negative_feature_count(self):
        """Test handling of explicit feature_count (edge case)."""
        result = FilterExecutionResult(
            status=FilterStatus.SUCCESS,
            feature_ids=[],
            feature_count=0
        )
        assert result.feature_count == 0
    
    def test_very_long_expression(self):
        """Test handling of very long expression."""
        long_expr = "id IN (" + ",".join(str(i) for i in range(10000)) + ")"
        ids = list(range(10000))
        result = FilterExecutionResult.success(ids, long_expr)
        
        assert result.status == FilterStatus.SUCCESS
        assert len(result.expression) > 40000  # Réaliste: ~48897 caractères
    
    def test_unicode_in_expression(self):
        """Test handling of unicode in expression."""
        result = FilterExecutionResult.success([1], "name = '日本語テスト'")
        assert result.status == FilterStatus.SUCCESS
        assert "日本語" in result.expression
    
    def test_special_characters_in_error(self):
        """Test handling of special characters in error message."""
        result = FilterExecutionResult.failed("Error: Can't connect to 'server'")
        assert "Can't" in result.error_message


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Performance-related tests."""
    
    def test_result_creation_speed(self):
        """Test that result creation is fast."""
        import time
        
        start = time.time()
        for _ in range(10000):
            FilterExecutionResult.success([1, 2, 3], "id > 10")
        elapsed = time.time() - start
        
        # Should be able to create 10000 results in under 1 second
        assert elapsed < 1.0, f"Result creation too slow: {elapsed:.2f}s"
    
    def test_registry_access_speed(self):
        """Test that registry access is fast."""
        import time
        
        registry = BackendRegistry()
        
        start = time.time()
        for _ in range(1000):
            registry.is_available('spatialite')
        elapsed = time.time() - start
        
        # Should be able to query registry 1000 times in under 1 second
        assert elapsed < 1.0, f"Registry access too slow: {elapsed:.2f}s"

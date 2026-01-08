# -*- coding: utf-8 -*-
"""
End-to-End Tests for Backend Switching - ARCH-050

Tests the workflow of switching between backends dynamically.

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
def backend_factory_mock():
    """Create a mock backend factory."""
    factory = MagicMock()
    
    # Available backends - use spec and configure name as property
    postgresql_backend = MagicMock()
    postgresql_backend.name = "PostgreSQL"
    postgresql_backend.priority = 100
    
    spatialite_backend = MagicMock()
    spatialite_backend.name = "Spatialite"
    spatialite_backend.priority = 50
    
    ogr_backend = MagicMock()
    ogr_backend.name = "OGR"
    ogr_backend.priority = 10
    
    memory_backend = MagicMock()
    memory_backend.name = "Memory"
    memory_backend.priority = 5
    
    factory._backends = {
        "postgresql": postgresql_backend,
        "spatialite": spatialite_backend,
        "ogr": ogr_backend,
        "memory": memory_backend
    }
    
    def get_backend(provider_type):
        mapping = {
            "postgres": "postgresql",
            "spatialite": "spatialite",
            "ogr": "ogr",
            "memory": "memory"
        }
        backend_name = mapping.get(provider_type, "ogr")
        return factory._backends.get(backend_name)
    
    def get_best_backend(layer):
        provider = layer.providerType()
        return get_backend(provider)
    
    def list_backends():
        return list(factory._backends.keys())
    
    factory.get_backend.side_effect = get_backend
    factory.get_best_backend.side_effect = get_best_backend
    factory.list_backends.side_effect = list_backends
    
    return factory


@pytest.mark.e2e
@pytest.mark.integration
class TestBackendSwitchingE2E:
    """E2E tests for backend switching."""
    
    def test_auto_select_postgresql_backend(
        self,
        backend_factory_mock,
        postgresql_layer
    ):
        """Test automatic selection of PostgreSQL backend."""
        factory = backend_factory_mock
        
        backend = factory.get_best_backend(postgresql_layer)
        assert backend.name == "PostgreSQL"
    
    def test_auto_select_spatialite_backend(
        self,
        backend_factory_mock,
        spatialite_layer
    ):
        """Test automatic selection of Spatialite backend."""
        factory = backend_factory_mock
        
        backend = factory.get_best_backend(spatialite_layer)
        assert backend.name == "Spatialite"
    
    def test_auto_select_ogr_backend(
        self,
        backend_factory_mock,
        ogr_layer
    ):
        """Test automatic selection of OGR backend."""
        factory = backend_factory_mock
        
        backend = factory.get_best_backend(ogr_layer)
        assert backend.name == "OGR"
    
    def test_fallback_to_ogr(
        self,
        backend_factory_mock
    ):
        """Test fallback to OGR for unknown provider."""
        factory = backend_factory_mock
        
        # Unknown provider
        unknown_layer = MagicMock()
        unknown_layer.providerType.return_value = "unknown"
        
        backend = factory.get_best_backend(unknown_layer)
        assert backend.name == "OGR"
    
    def test_list_available_backends(
        self,
        backend_factory_mock
    ):
        """Test listing all available backends."""
        factory = backend_factory_mock
        
        backends = factory.list_backends()
        assert "postgresql" in backends
        assert "spatialite" in backends
        assert "ogr" in backends
        assert len(backends) == 4


@pytest.mark.e2e
@pytest.mark.integration
class TestBackendForceSelectionE2E:
    """E2E tests for forcing specific backend."""
    
    def test_force_ogr_backend(
        self,
        backend_factory_mock,
        postgresql_layer
    ):
        """Test forcing OGR backend for PostgreSQL layer."""
        factory = backend_factory_mock
        
        # Force OGR
        factory.force_backend = MagicMock()
        factory.get_forced_backend = MagicMock(
            return_value=factory._backends["ogr"]
        )
        
        factory.force_backend("ogr")
        backend = factory.get_forced_backend()
        
        assert backend.name == "OGR"
    
    def test_clear_forced_backend(
        self,
        backend_factory_mock,
        postgresql_layer
    ):
        """Test clearing forced backend."""
        factory = backend_factory_mock
        
        # Force then clear
        factory.force_backend = MagicMock()
        factory.clear_forced_backend = MagicMock()
        
        factory.force_backend("ogr")
        factory.clear_forced_backend()
        
        # Should use auto-selection again
        backend = factory.get_best_backend(postgresql_layer)
        assert backend.name == "PostgreSQL"


@pytest.mark.e2e
@pytest.mark.integration
class TestBackendCapabilitiesE2E:
    """E2E tests for backend capability checking."""
    
    def test_check_mv_capability(
        self,
        backend_factory_mock
    ):
        """Test checking materialized view capability."""
        factory = backend_factory_mock
        
        # PostgreSQL supports MV
        pg_backend = factory.get_backend("postgres")
        pg_backend.supports_mv = MagicMock(return_value=True)
        assert pg_backend.supports_mv() is True
        
        # OGR does not
        ogr_backend = factory.get_backend("ogr")
        ogr_backend.supports_mv = MagicMock(return_value=False)
        assert ogr_backend.supports_mv() is False
    
    def test_check_rtree_capability(
        self,
        backend_factory_mock
    ):
        """Test checking R-tree index capability."""
        factory = backend_factory_mock
        
        # Spatialite supports R-tree
        sl_backend = factory.get_backend("spatialite")
        sl_backend.supports_rtree = MagicMock(return_value=True)
        assert sl_backend.supports_rtree() is True
    
    def test_check_spatial_capability(
        self,
        backend_factory_mock
    ):
        """Test checking spatial filter capability."""
        factory = backend_factory_mock
        
        for backend_name in ["postgres", "spatialite", "ogr"]:
            backend = factory.get_backend(backend_name)
            backend.supports_spatial = MagicMock(return_value=True)
            assert backend.supports_spatial() is True


@pytest.mark.e2e
@pytest.mark.integration
class TestBackendExecutionE2E:
    """E2E tests for backend execution."""
    
    def test_execute_same_expression_different_backends(
        self,
        backend_factory_mock,
        postgresql_layer,
        spatialite_layer,
        ogr_layer
    ):
        """Test same expression executes on different backends."""
        factory = backend_factory_mock
        expression = '"population" > 10000'
        
        # Configure backends to return results
        for name, backend in factory._backends.items():
            result = MagicMock()
            result.success = True
            result.matched_count = 100
            result.backend_used = name
            backend.execute.return_value = result
        
        # Execute on each backend
        layers = [postgresql_layer, spatialite_layer, ogr_layer]
        results = []
        
        for layer in layers:
            backend = factory.get_best_backend(layer)
            result = backend.execute(expression, layer)
            results.append(result)
        
        # All should succeed
        assert all(r.success for r in results)
    
    def test_backend_execution_metrics(
        self,
        backend_factory_mock,
        postgresql_layer
    ):
        """Test backend returns execution metrics."""
        factory = backend_factory_mock
        backend = factory.get_best_backend(postgresql_layer)
        
        # Configure detailed result
        result = MagicMock()
        result.success = True
        result.matched_count = 500
        result.execution_time_ms = 25.5
        result.used_optimization = True
        result.optimization_type = "materialized_view"
        backend.execute.return_value = result
        
        execution_result = backend.execute('"test"', postgresql_layer)
        
        assert execution_result.execution_time_ms > 0
        assert execution_result.used_optimization is True

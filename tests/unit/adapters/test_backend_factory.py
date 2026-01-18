# -*- coding: utf-8 -*-
"""
Unit tests for Backend Factory.

Tests backend selection logic without QGIS dependencies.
"""
import pytest
from unittest.mock import Mock, patch

from core.domain.filter_expression import ProviderType
from core.domain.layer_info import LayerInfo, GeometryType


class TestBackendSelector:
    """Tests for BackendSelector class."""
    
    @pytest.fixture
    def layer_info_postgresql(self):
        """Create a PostgreSQL layer info."""
        return LayerInfo(
            layer_id="pg_layer_1",
            name="test_pg_layer",
            provider_type=ProviderType.POSTGRESQL,
            feature_count=10000,
            geometry_type=GeometryType.POINT,
            crs_auth_id="EPSG:4326",
            schema_name="public",
            table_name="test_table"
        )
    
    @pytest.fixture
    def layer_info_spatialite(self):
        """Create a Spatialite layer info."""
        return LayerInfo(
            layer_id="sl_layer_1",
            name="test_sl_layer",
            provider_type=ProviderType.SPATIALITE,
            feature_count=5000,
            geometry_type=GeometryType.POLYGON,
            crs_auth_id="EPSG:4326"
        )
    
    @pytest.fixture
    def layer_info_memory(self):
        """Create a memory layer info."""
        return LayerInfo(
            layer_id="mem_layer_1",
            name="test_mem_layer",
            provider_type=ProviderType.MEMORY,
            feature_count=100,
            geometry_type=GeometryType.LINE,
            crs_auth_id="EPSG:4326"
        )
    
    @pytest.fixture
    def layer_info_ogr(self):
        """Create an OGR layer info."""
        return LayerInfo(
            layer_id="ogr_layer_1",
            name="test_ogr_layer",
            provider_type=ProviderType.OGR,
            feature_count=2000,
            geometry_type=GeometryType.POINT,
            crs_auth_id="EPSG:4326"
        )
    
    def test_select_memory_for_memory_layer(self, layer_info_memory):
        """Test that memory layer uses Memory backend."""
        from adapters.backends.factory import BackendSelector
        
        selector = BackendSelector(postgresql_available=True)
        result = selector.select_provider_type(layer_info_memory)
        
        assert result == ProviderType.MEMORY
    
    def test_select_postgresql_when_available(self, layer_info_postgresql):
        """Test PostgreSQL selection when psycopg2 available."""
        from adapters.backends.factory import BackendSelector
        
        selector = BackendSelector(postgresql_available=True)
        result = selector.select_provider_type(layer_info_postgresql)
        
        assert result == ProviderType.POSTGRESQL
    
    def test_fallback_to_ogr_when_postgresql_unavailable(self, layer_info_postgresql):
        """Test fallback to OGR when PostgreSQL not available."""
        from adapters.backends.factory import BackendSelector
        
        selector = BackendSelector(postgresql_available=False)
        result = selector.select_provider_type(layer_info_postgresql)
        
        assert result == ProviderType.OGR
    
    def test_select_spatialite_for_spatialite_layer(self, layer_info_spatialite):
        """Test Spatialite layer uses Spatialite backend."""
        from adapters.backends.factory import BackendSelector
        
        selector = BackendSelector(postgresql_available=True)
        result = selector.select_provider_type(layer_info_spatialite)
        
        assert result == ProviderType.SPATIALITE
    
    def test_select_ogr_for_ogr_layer(self, layer_info_ogr):
        """Test OGR layer uses OGR backend."""
        from adapters.backends.factory import BackendSelector
        
        selector = BackendSelector(postgresql_available=True)
        result = selector.select_provider_type(layer_info_ogr)
        
        assert result == ProviderType.OGR
    
    def test_forced_backend_overrides_selection(self, layer_info_postgresql):
        """Test that forced backend overrides auto-selection."""
        from adapters.backends.factory import BackendSelector
        
        selector = BackendSelector(postgresql_available=True)
        result = selector.select_provider_type(
            layer_info_postgresql,
            forced_backend='ogr'
        )
        
        assert result == ProviderType.OGR
    
    def test_forced_backend_postgresql_alias(self, layer_info_ogr):
        """Test postgres alias for forced backend."""
        from adapters.backends.factory import BackendSelector
        
        selector = BackendSelector(postgresql_available=True)
        result = selector.select_provider_type(
            layer_info_ogr,
            forced_backend='postgres'
        )
        
        assert result == ProviderType.POSTGRESQL
    
    def test_small_dataset_optimization(self, layer_info_postgresql):
        """Test small dataset optimization for PostgreSQL."""
        from adapters.backends.factory import BackendSelector
        
        # Create layer with small feature count
        small_layer = LayerInfo(
            layer_id="small_pg",
            name="small_pg_layer",
            provider_type=ProviderType.POSTGRESQL,
            feature_count=100,  # Below threshold
            geometry_type=GeometryType.POINT,
            crs_auth_id="EPSG:4326"
        )
        
        selector = BackendSelector(
            postgresql_available=True,
            small_dataset_optimization=True,
            small_dataset_threshold=5000
        )
        result = selector.select_provider_type(small_layer)
        
        assert result == ProviderType.MEMORY
    
    def test_small_dataset_disabled_uses_postgresql(self, layer_info_postgresql):
        """Test that disabled optimization uses PostgreSQL."""
        from adapters.backends.factory import BackendSelector
        
        small_layer = LayerInfo(
            layer_id="small_pg",
            name="small_pg_layer",
            provider_type=ProviderType.POSTGRESQL,
            feature_count=100,
            geometry_type=GeometryType.POINT,
            crs_auth_id="EPSG:4326"
        )
        
        selector = BackendSelector(
            postgresql_available=True,
            small_dataset_optimization=False  # Disabled
        )
        result = selector.select_provider_type(small_layer)
        
        assert result == ProviderType.POSTGRESQL
    
    def test_prefer_native_for_postgresql_project(self, layer_info_postgresql):
        """Test that prefer_native_backend uses PostgreSQL even for small datasets.
        
        When all project layers are PostgreSQL, we want consistent backend usage.
        v4.1.1: Added prefer_native_backend option.
        """
        from adapters.backends.factory import BackendSelector
        
        small_layer = LayerInfo(
            layer_id="small_pg",
            name="small_pg_layer",
            provider_type=ProviderType.POSTGRESQL,
            feature_count=100,  # Below threshold
            geometry_type=GeometryType.POINT,
            crs_auth_id="EPSG:4326"
        )
        
        # With prefer_native_backend=True, even small datasets use PostgreSQL
        selector = BackendSelector(
            postgresql_available=True,
            small_dataset_optimization=True,
            small_dataset_threshold=5000,
            prefer_native_backend=True  # NEW: Force native backend
        )
        result = selector.select_provider_type(small_layer)
        
        assert result == ProviderType.POSTGRESQL
    
    def test_unknown_provider_fallback(self):
        """Test unknown provider falls back to OGR."""
        from adapters.backends.factory import BackendSelector
        
        unknown_layer = LayerInfo(
            layer_id="unknown_1",
            name="unknown_layer",
            provider_type=ProviderType.UNKNOWN,
            feature_count=100,
            geometry_type=GeometryType.POINT,
            crs_auth_id="EPSG:4326"
        )
        
        selector = BackendSelector(postgresql_available=True)
        result = selector.select_provider_type(unknown_layer)
        
        assert result == ProviderType.OGR


class TestBackendFactory:
    """Tests for BackendFactory class."""
    
    @pytest.fixture
    def mock_container(self):
        """Create a mock DI container."""
        return Mock()
    
    @pytest.fixture
    def layer_info(self):
        """Create a test layer info."""
        return LayerInfo(
            layer_id="test_layer",
            name="test_layer",
            provider_type=ProviderType.OGR,
            feature_count=1000,
            geometry_type=GeometryType.POINT,
            crs_auth_id="EPSG:4326"
        )
    
    @patch('adapters.backends.factory.BackendFactory._check_postgresql_available')
    def test_factory_initialization(self, mock_pg_check):
        """Test factory initialization."""
        from adapters.backends.factory import BackendFactory
        
        mock_pg_check.return_value = True
        factory = BackendFactory()
        
        assert factory.postgresql_available is True
    
    @patch('adapters.backends.factory.BackendFactory._check_postgresql_available')
    @patch('adapters.backends.ogr.backend.OGRBackend')
    def test_get_backend_ogr(self, mock_ogr_class, mock_pg_check, layer_info):
        """Test getting OGR backend."""
        from adapters.backends.factory import BackendFactory
        
        mock_pg_check.return_value = False
        mock_backend = Mock()
        mock_ogr_class.return_value = mock_backend
        
        factory = BackendFactory()
        
        with patch('adapters.backends.factory.BackendFactory._create_backend') as mock_create:
            mock_create.return_value = mock_backend
            backend = factory.get_backend(layer_info)
            assert backend is mock_backend
    
    @patch('adapters.backends.factory.BackendFactory._check_postgresql_available')
    def test_backend_caching(self, mock_pg_check, layer_info):
        """Test that backends are cached."""
        from adapters.backends.factory import BackendFactory
        
        mock_pg_check.return_value = False
        factory = BackendFactory()
        
        # Create mock backend
        mock_backend = Mock()
        factory._backends[ProviderType.OGR] = mock_backend
        
        # Should return cached backend
        backend = factory.get_backend_for_provider(ProviderType.OGR)
        
        assert backend is mock_backend
    
    @patch('adapters.backends.factory.BackendFactory._check_postgresql_available')
    def test_cleanup_calls_backend_cleanup(self, mock_pg_check):
        """Test that cleanup calls cleanup on all backends."""
        from adapters.backends.factory import BackendFactory
        
        mock_pg_check.return_value = False
        factory = BackendFactory()
        
        # Add mock backends
        mock_backend1 = Mock()
        mock_backend2 = Mock()
        factory._backends = {
            ProviderType.OGR: mock_backend1,
            ProviderType.MEMORY: mock_backend2,
        }
        
        factory.cleanup()
        
        mock_backend1.cleanup.assert_called_once()
        mock_backend2.cleanup.assert_called_once()
        assert len(factory._backends) == 0
    
    @patch('adapters.backends.factory.BackendFactory._check_postgresql_available')
    def test_available_backends_without_postgresql(self, mock_pg_check):
        """Test available backends when PostgreSQL not available."""
        from adapters.backends.factory import BackendFactory
        
        mock_pg_check.return_value = False
        factory = BackendFactory()
        
        available = factory.available_backends
        
        assert ProviderType.OGR in available
        assert ProviderType.MEMORY in available
        assert ProviderType.SPATIALITE in available
        assert ProviderType.POSTGRESQL not in available
    
    @patch('adapters.backends.factory.BackendFactory._check_postgresql_available')
    def test_available_backends_with_postgresql(self, mock_pg_check):
        """Test available backends when PostgreSQL available."""
        from adapters.backends.factory import BackendFactory
        
        mock_pg_check.return_value = True
        factory = BackendFactory()
        
        available = factory.available_backends
        
        assert ProviderType.POSTGRESQL in available


class TestCreateBackendFactory:
    """Tests for create_backend_factory function."""
    
    @patch('adapters.backends.factory.BackendFactory._check_postgresql_available')
    def test_create_with_config(self, mock_pg_check):
        """Test creating factory with configuration."""
        from adapters.backends.factory import create_backend_factory
        
        mock_pg_check.return_value = True
        
        config = {
            'small_dataset_optimization': {
                'enabled': True,
                'threshold': 1000
            }
        }
        
        factory = create_backend_factory(config=config)
        
        assert factory is not None
        assert factory._selector._small_dataset_optimization is True
        assert factory._selector._small_dataset_threshold == 1000

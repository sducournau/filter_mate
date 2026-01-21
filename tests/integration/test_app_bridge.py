# -*- coding: utf-8 -*-
"""
Integration Tests for Application Bridge.

Tests the bridge between legacy FilterMateApp and new hexagonal architecture.

Author: FilterMate Team
Date: January 2026
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add plugin directory to path
plugin_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(plugin_dir))


@pytest.fixture(autouse=True)
def reset_services():
    """Reset services before each test."""
    from adapters import app_bridge
    app_bridge.cleanup_services()
    yield
    app_bridge.cleanup_services()


class TestServiceInitialization:
    """Tests for service initialization."""
    
    def test_initialize_services_default(self):
        """Test default initialization."""
        from adapters.app_bridge import initialize_services, is_initialized
        
        initialize_services()
        
        assert is_initialized()
    
    def test_initialize_services_with_config(self):
        """Test initialization with custom config."""
        from adapters.app_bridge import initialize_services, is_initialized
        
        config = {
            'history': {'max_depth': 100},
            'backends': {'small_dataset_optimization': {'enabled': True}}
        }
        
        initialize_services(config)
        
        assert is_initialized()
    
    def test_double_initialization_is_safe(self):
        """Test that calling initialize twice is safe."""
        from adapters.app_bridge import initialize_services, is_initialized
        
        initialize_services()
        initialize_services()  # Should not raise
        
        assert is_initialized()
    
    def test_cleanup_services(self):
        """Test service cleanup."""
        from adapters.app_bridge import (
            initialize_services, 
            cleanup_services, 
            is_initialized
        )
        
        initialize_services()
        assert is_initialized()
        
        cleanup_services()
        assert not is_initialized()


class TestServiceAccessors:
    """Tests for service accessor functions."""
    
    def test_get_filter_service_not_initialized_raises(self):
        """Test getting service before init raises."""
        from adapters.app_bridge import get_filter_service
        
        with pytest.raises(RuntimeError, match="not initialized"):
            get_filter_service()
    
    def test_get_filter_service_after_init(self):
        """Test getting service after init works."""
        from adapters.app_bridge import initialize_services, get_filter_service
        from core.services.filter_service import FilterService
        
        initialize_services()
        
        service = get_filter_service()
        assert isinstance(service, FilterService)
    
    def test_get_history_service(self):
        """Test getting history service."""
        from adapters.app_bridge import initialize_services, get_history_service
        from core.services.history_service import HistoryService
        
        initialize_services()
        
        service = get_history_service()
        assert isinstance(service, HistoryService)
    
    def test_get_expression_service(self):
        """Test getting expression service."""
        from adapters.app_bridge import initialize_services, get_expression_service
        from core.services.expression_service import ExpressionService
        
        initialize_services()
        
        service = get_expression_service()
        assert isinstance(service, ExpressionService)
    
    def test_get_backend_factory(self):
        """Test getting backend factory."""
        from adapters.app_bridge import initialize_services, get_backend_factory
        from adapters.backends.factory import BackendFactory
        
        initialize_services()
        
        factory = get_backend_factory()
        assert isinstance(factory, BackendFactory)


class TestExpressionBridge:
    """Tests for expression validation/parsing bridge."""
    
    def test_validate_expression_valid(self):
        """Test validating a valid expression."""
        from adapters.app_bridge import initialize_services, validate_expression
        
        initialize_services()
        
        is_valid, error, warnings = validate_expression('"field" = 1')
        
        assert is_valid
        assert error is None
    
    def test_validate_expression_invalid(self):
        """Test validating an invalid expression."""
        from adapters.app_bridge import initialize_services, validate_expression
        
        initialize_services()
        
        is_valid, error, warnings = validate_expression('')
        
        assert not is_valid
        assert "empty" in error.lower()
    
    def test_parse_expression_simple(self):
        """Test parsing a simple expression."""
        from adapters.app_bridge import initialize_services, parse_expression
        
        initialize_services()
        
        result = parse_expression('"name" = \'test\'')
        
        assert 'name' in result['fields']
        assert not result['is_spatial']
    
    def test_parse_expression_spatial(self):
        """Test parsing a spatial expression."""
        from adapters.app_bridge import initialize_services, parse_expression
        
        initialize_services()
        
        result = parse_expression('intersects($geometry, @layer)')
        
        assert result['is_spatial']
        assert 'intersects' in result['spatial_predicates']
        assert result['has_geometry_reference']


class TestHistoryBridge:
    """Tests for history service bridge."""
    
    def test_push_history_entry(self):
        """Test pushing a history entry."""
        from adapters.app_bridge import (
            initialize_services, 
            push_history_entry,
            can_undo
        )
        
        initialize_services()
        
        push_history_entry(
            expression='"field" = 1',
            layer_ids=['layer_123'],
            previous_filters=[('layer_123', '')]
        )
        
        assert can_undo()
    
    def test_undo_filter(self):
        """Test undoing a filter."""
        from adapters.app_bridge import (
            initialize_services,
            push_history_entry,
            undo_filter,
            can_undo,
            can_redo
        )
        
        initialize_services()
        
        push_history_entry(
            expression='"field" = 1',
            layer_ids=['layer_123'],
            previous_filters=[('layer_123', 'old_filter')]
        )
        
        assert can_undo()
        
        entry = undo_filter()
        
        assert entry is not None
        assert entry.expression == '"field" = 1'
        assert not can_undo()
        assert can_redo()
    
    def test_redo_filter(self):
        """Test redoing a filter."""
        from adapters.app_bridge import (
            initialize_services,
            push_history_entry,
            undo_filter,
            redo_filter,
            can_undo,
            can_redo
        )
        
        initialize_services()
        
        push_history_entry(
            expression='test',
            layer_ids=['layer_1'],
            previous_filters=[]
        )
        
        undo_filter()
        entry = redo_filter()
        
        assert entry is not None
        assert can_undo()
        assert not can_redo()
    
    def test_can_undo_empty(self):
        """Test can_undo on empty history."""
        from adapters.app_bridge import initialize_services, can_undo
        
        initialize_services()
        
        assert not can_undo()


class TestBackendBridge:
    """Tests for backend selection bridge."""
    
    def test_get_available_backends(self):
        """Test getting available backends."""
        from adapters.app_bridge import initialize_services, get_available_backends
        
        initialize_services()
        
        backends = get_available_backends()
        
        assert 'memory' in backends
        assert 'ogr' in backends
        assert 'spatialite' in backends


class TestLayerInfoConversion:
    """Tests for QGIS layer to LayerInfo conversion."""
    
    @pytest.fixture
    def mock_qgis_layer(self):
        """Create a mock QGIS layer."""
        layer = MagicMock()
        layer.id.return_value = "layer_123"
        layer.name.return_value = "Test Layer"
        layer.providerType.return_value = "ogr"
        layer.wkbType.return_value = 1  # Point
        layer.featureCount.return_value = 1000
        layer.isValid.return_value = True
        layer.source.return_value = "/path/to/file.shp"
        
        crs = MagicMock()
        crs.isValid.return_value = True
        crs.authid.return_value = "EPSG:4326"
        layer.crs.return_value = crs
        
        provider = MagicMock()
        provider.hasSpatialIndex.return_value = False
        provider.dataSourceUri.return_value = "path=/path/to/file.shp"
        layer.dataProvider.return_value = provider
        
        return layer
    
    def test_layer_info_from_qgis_layer(self, mock_qgis_layer):
        """Test converting QGIS layer to LayerInfo."""
        from adapters.app_bridge import layer_info_from_qgis_layer
        from core.domain.filter_expression import ProviderType
        from core.domain.layer_info import GeometryType
        
        info = layer_info_from_qgis_layer(mock_qgis_layer)
        
        assert info.layer_id == "layer_123"
        assert info.name == "Test Layer"
        assert info.provider_type == ProviderType.OGR
        assert info.geometry_type == GeometryType.POINT
        assert info.feature_count == 1000
        assert info.crs_auth_id == "EPSG:4326"
        assert info.is_valid


class TestLegacyCompatibility:
    """Tests for legacy compatibility functions."""
    
    @pytest.fixture
    def mock_layer(self):
        """Create a mock QGIS layer."""
        layer = MagicMock()
        layer.id.return_value = "layer_456"
        layer.name.return_value = "Legacy Layer"
        layer.providerType.return_value = "ogr"
        layer.wkbType.return_value = 3  # Polygon
        layer.featureCount.return_value = 500
        layer.isValid.return_value = True
        layer.source.return_value = "/path/to/data.gpkg"
        
        crs = MagicMock()
        crs.isValid.return_value = True
        crs.authid.return_value = "EPSG:2154"
        layer.crs.return_value = crs
        
        provider = MagicMock()
        provider.hasSpatialIndex.return_value = True
        provider.dataSourceUri.return_value = ""
        layer.dataProvider.return_value = provider
        
        return layer
    
    def test_create_filter_expression_from_legacy(self, mock_layer):
        """Test creating FilterExpression from legacy params."""
        from adapters.app_bridge import create_filter_expression_from_legacy
        from core.domain.filter_expression import FilterExpression
        
        expr = create_filter_expression_from_legacy(
            raw_expression='"type" = \'residential\'',
            layer=mock_layer,
            buffer_value=50.0,
            buffer_segments=5
        )
        
        assert isinstance(expr, FilterExpression)
        assert expr.raw == '"type" = \'residential\''
        assert expr.source_layer_id == "layer_456"
        assert expr.buffer_value == 50.0
        assert expr.buffer_segments == 5
    
    def test_convert_filter_result_to_legacy(self):
        """Test converting FilterResult to legacy dict."""
        from adapters.app_bridge import convert_filter_result_to_legacy
        from core.domain.filter_result import FilterResult
        
        result = FilterResult.success(
            feature_ids=[1, 2, 3, 4, 5],
            layer_id="layer_789",
            expression_raw='"field" > 10',
            execution_time_ms=25.5,
            backend_name="OGR"
        )
        
        legacy = convert_filter_result_to_legacy(result)
        
        assert legacy['success'] is True
        assert legacy['feature_count'] == 5
        assert len(legacy['feature_ids']) == 5
        assert legacy['expression'] == '"field" > 10'
        assert legacy['execution_time_ms'] == 25.5
        assert legacy['backend'] == "OGR"
        assert legacy['error'] is None

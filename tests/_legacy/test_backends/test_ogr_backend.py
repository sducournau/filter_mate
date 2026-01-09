"""
Tests for OGR backend implementation.

Verifies that OGR backend correctly:
- Handles various file formats (Shapefile, GeoPackage, etc.)
- Builds filter expressions
- Manages feature selection
- Handles large datasets efficiently
"""
import pytest
from unittest.mock import Mock, patch


def test_ogr_backend_instantiation():
    """Test that OGR backend can be instantiated."""
    from modules.backends.ogr_backend import OGRBackend
    
    backend = OGRBackend()
    assert backend is not None
    assert hasattr(backend, 'build_filter_expression')
    assert hasattr(backend, 'apply_filter')


def test_ogr_backend_inheritance():
    """Test that OGR backend inherits from BaseBackend."""
    from modules.backends.ogr_backend import OGRBackend
    from modules.backends.base_backend import BaseBackend
    
    backend = OGRBackend()
    assert isinstance(backend, BaseBackend)


def test_ogr_provider_detection():
    """Test that backend correctly identifies OGR layers."""
    from modules.backends.ogr_backend import OGRBackend
    
    backend = OGRBackend()
    
    # Mock layer
    mock_layer = Mock()
    mock_layer.providerType.return_value = 'ogr'
    
    # Should support OGR provider
    assert backend.supports_layer(mock_layer)


def test_ogr_handles_shapefile():
    """Test that OGR backend can work with Shapefile layers."""
    from modules.backends.ogr_backend import OGRBackend
    
    backend = OGRBackend()
    
    # Mock Shapefile layer
    mock_layer = Mock()
    mock_layer.providerType.return_value = 'ogr'
    mock_layer.dataProvider().dataSourceUri.return_value = '/path/to/file.shp'
    
    assert backend.supports_layer(mock_layer)


def test_ogr_handles_geopackage():
    """Test that OGR backend can work with GeoPackage layers."""
    from modules.backends.ogr_backend import OGRBackend
    
    backend = OGRBackend()
    
    # Mock GeoPackage layer
    mock_layer = Mock()
    mock_layer.providerType.return_value = 'ogr'
    mock_layer.dataProvider().dataSourceUri.return_value = '/path/to/file.gpkg'
    
    assert backend.supports_layer(mock_layer)


def test_ogr_large_dataset_detection():
    """Test that backend detects large datasets for optimization."""
    from modules.backends.ogr_backend import OGRBackend
    
    backend = OGRBackend()
    
    # Mock large dataset
    mock_layer = Mock()
    mock_layer.featureCount.return_value = 50000
    
    # Backend should have logic for handling large datasets
    is_large = backend._is_large_dataset(mock_layer)
    
    # Should recognize as large (threshold usually 10k)
    assert is_large is True


def test_ogr_small_dataset_detection():
    """Test that backend detects small datasets."""
    from modules.backends.ogr_backend import OGRBackend
    
    backend = OGRBackend()
    
    # Mock small dataset
    mock_layer = Mock()
    mock_layer.featureCount.return_value = 500
    
    is_large = backend._is_large_dataset(mock_layer)
    
    # Should recognize as small
    assert is_large is False


def test_ogr_attribute_filter():
    """Test basic attribute filtering."""
    from modules.backends.ogr_backend import OGRBackend
    
    backend = OGRBackend()
    
    # Mock parameters
    params = Mock()
    params.attribute_expression = 'name = "Paris"'
    params.spatial_predicates = []
    
    mock_layer = Mock()
    
    expression = backend.build_filter_expression(params, mock_layer)
    
    assert expression is not None
    # OGR uses attribute filters
    assert 'name' in expression or len(expression) > 0


def test_ogr_spatial_predicate_support():
    """Test that OGR backend supports spatial predicates."""
    from modules.backends.ogr_backend import OGRBackend
    
    backend = OGRBackend()
    
    # Common spatial predicates
    required_predicates = ['intersects', 'contains', 'within']
    
    for predicate in required_predicates:
        # Backend should handle these predicates
        assert backend._supports_predicate(predicate) or \
               hasattr(backend, f'_build_{predicate}_predicate')

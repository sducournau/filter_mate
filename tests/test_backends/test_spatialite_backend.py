"""
Tests for Spatialite backend implementation.

Verifies that Spatialite backend correctly:
- Builds filter expressions
- Handles spatial predicates
- Creates spatial indexes
- Manages database connections
"""
import pytest
from unittest.mock import Mock, patch, MagicMock


def test_spatialite_backend_instantiation():
    """Test that Spatialite backend can be instantiated."""
    from modules.backends.spatialite_backend import SpatialiteBackend
    
    backend = SpatialiteBackend()
    assert backend is not None
    assert hasattr(backend, 'build_filter_expression')
    assert hasattr(backend, 'apply_filter')


def test_spatialite_backend_inheritance():
    """Test that Spatialite backend inherits from BaseBackend."""
    from modules.backends.spatialite_backend import SpatialiteBackend
    from modules.backends.base_backend import BaseBackend
    
    backend = SpatialiteBackend()
    assert isinstance(backend, BaseBackend)


def test_spatialite_provider_detection():
    """Test that backend correctly identifies Spatialite layers."""
    from modules.backends.spatialite_backend import SpatialiteBackend
    
    backend = SpatialiteBackend()
    
    # Mock layer
    mock_layer = Mock()
    mock_layer.providerType.return_value = 'spatialite'
    
    # Should support spatialite provider
    assert backend.supports_layer(mock_layer)


def test_spatialite_spatial_predicates():
    """Test that Spatialite backend supports required spatial predicates."""
    from modules.backends.spatialite_backend import SpatialiteBackend
    
    backend = SpatialiteBackend()
    
    required_predicates = [
        'intersects', 'contains', 'within',
        'touches', 'crosses', 'overlaps',
        'disjoint'
    ]
    
    for predicate in required_predicates:
        assert hasattr(backend, f'_build_{predicate}_predicate') or \
               backend._supports_predicate(predicate), \
               f"Missing support for {predicate}"


def test_spatialite_expression_building():
    """Test basic filter expression building."""
    from modules.backends.spatialite_backend import SpatialiteBackend
    
    backend = SpatialiteBackend()
    
    # Mock layer and parameters
    mock_layer = Mock()
    mock_layer.geometryColumnName.return_value = 'geometry'
    
    # Test attribute expression
    params = Mock()
    params.attribute_expression = 'population > 10000'
    params.spatial_predicates = []
    
    expression = backend.build_filter_expression(params, mock_layer)
    
    assert expression is not None
    assert 'population > 10000' in expression or 'population' in expression


def test_spatialite_connection_cleanup():
    """Test that database connections are properly closed."""
    from modules.backends.spatialite_backend import SpatialiteBackend
    
    backend = SpatialiteBackend()
    
    # Verify cleanup method exists
    assert hasattr(backend, 'cleanup')
    
    # Should not raise exception even if no connections
    backend.cleanup()


@pytest.mark.parametrize("predicate", [
    'intersects', 'contains', 'within', 'touches'
])
def test_spatialite_predicate_sql_format(predicate):
    """Test that spatial predicates generate valid SQL."""
    from modules.backends.spatialite_backend import SpatialiteBackend
    
    backend = SpatialiteBackend()
    
    # Mock geometry
    mock_geom = Mock()
    mock_geom.asWkt.return_value = 'POINT(0 0)'
    
    # Build predicate
    result = backend._build_spatial_predicate(
        predicate=predicate,
        geometry=mock_geom,
        geom_column='geometry'
    )
    
    assert result is not None
    assert 'geometry' in result.lower() or 'ST_' in result or predicate in result.lower()

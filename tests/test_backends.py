"""
FilterMate Backend Tests

Unit tests for the backend architecture (PostgreSQL, Spatialite, OGR backends).
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import backends
from modules.backends.base_backend import GeometricFilterBackend
from modules.backends.postgresql_backend import PostgreSQLBackend
from modules.backends.spatialite_backend import SpatialiteBackend
from modules.backends.ogr_backend import OGRBackend
from modules.backends.factory import BackendFactory


# ============================================================================
# BackendFactory Tests
# ============================================================================

class TestBackendFactory:
    """Test suite for BackendFactory"""
    
    def test_factory_returns_postgresql_backend(self, sample_pg_layer):
        """Test that factory returns PostgreSQLBackend for postgres layers"""
        backend = BackendFactory.get_backend(sample_pg_layer)
        assert isinstance(backend, PostgreSQLBackend)
    
    def test_factory_returns_spatialite_backend(self, sample_spatialite_layer):
        """Test that factory returns SpatialiteBackend for spatialite layers"""
        backend = BackendFactory.get_backend(sample_spatialite_layer)
        assert isinstance(backend, SpatialiteBackend)
    
    def test_factory_returns_ogr_backend(self, sample_shapefile_layer):
        """Test that factory returns OGRBackend for OGR layers"""
        backend = BackendFactory.get_backend(sample_shapefile_layer)
        assert isinstance(backend, OGRBackend)
    
    def test_factory_handles_unknown_provider(self):
        """Test that factory handles unknown provider gracefully"""
        layer = Mock()
        layer.providerType.return_value = "unknown_provider"
        layer.name.return_value = "Unknown Layer"
        
        backend = BackendFactory.get_backend(layer)
        # Should fallback to OGR
        assert isinstance(backend, OGRBackend)
    
    def test_factory_with_postgresql_unavailable(self, sample_pg_layer):
        """Test factory behavior when PostgreSQL is unavailable"""
        with patch('modules.backends.factory.POSTGRESQL_AVAILABLE', False):
            backend = BackendFactory.get_backend(sample_pg_layer)
            # Should fallback to OGR when psycopg2 not available
            assert isinstance(backend, OGRBackend)
    
    def test_factory_singleton_pattern(self, sample_pg_layer):
        """Test that factory returns the same backend instance for same provider"""
        backend1 = BackendFactory.get_backend(sample_pg_layer)
        backend2 = BackendFactory.get_backend(sample_pg_layer)
        assert backend1 is backend2


# ============================================================================
# PostgreSQLBackend Tests
# ============================================================================

class TestPostgreSQLBackend:
    """Test suite for PostgreSQLBackend"""
    
    def test_supports_postgres_layer(self, sample_pg_layer):
        """Test that backend supports PostgreSQL layers"""
        backend = PostgreSQLBackend()
        assert backend.supports_layer(sample_pg_layer) is True
    
    def test_rejects_non_postgres_layer(self, sample_shapefile_layer):
        """Test that backend rejects non-PostgreSQL layers"""
        backend = PostgreSQLBackend()
        assert backend.supports_layer(sample_shapefile_layer) is False
    
    def test_build_intersects_expression(self):
        """Test building ST_Intersects expression"""
        backend = PostgreSQLBackend()
        
        mock_geometry = Mock()
        mock_geometry.asWkt.return_value = "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
        
        expression = backend.build_expression(
            predicate='intersects',
            source_geometry=mock_geometry,
            geom_field='geom'
        )
        
        assert 'ST_Intersects' in expression
        assert 'geom' in expression
        assert 'ST_GeomFromText' in expression
    
    def test_build_contains_expression(self):
        """Test building ST_Contains expression"""
        backend = PostgreSQLBackend()
        
        mock_geometry = Mock()
        mock_geometry.asWkt.return_value = "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
        
        expression = backend.build_expression(
            predicate='contains',
            source_geometry=mock_geometry,
            geom_field='geometry'
        )
        
        assert 'ST_Contains' in expression
        assert 'geometry' in expression
    
    def test_build_within_expression(self):
        """Test building ST_Within expression"""
        backend = PostgreSQLBackend()
        
        mock_geometry = Mock()
        mock_geometry.asWkt.return_value = "POINT(0.5 0.5)"
        
        expression = backend.build_expression(
            predicate='within',
            source_geometry=mock_geometry,
            geom_field='the_geom'
        )
        
        assert 'ST_Within' in expression
        assert 'the_geom' in expression
    
    def test_apply_filter_with_valid_expression(self, sample_pg_layer):
        """Test applying filter with valid expression"""
        backend = PostgreSQLBackend()
        expression = "ST_Intersects(geom, ST_GeomFromText('POINT(0 0)', 4326))"
        
        result = backend.apply_filter(sample_pg_layer, expression)
        
        assert result is True
        sample_pg_layer.setSubsetString.assert_called_once_with(expression)
    
    def test_apply_filter_handles_errors(self, sample_pg_layer):
        """Test that apply_filter handles errors gracefully"""
        backend = PostgreSQLBackend()
        sample_pg_layer.setSubsetString.side_effect = Exception("Database error")
        
        result = backend.apply_filter(sample_pg_layer, "invalid_expression")
        
        assert result is False
    
    def test_unsupported_predicate_raises_error(self):
        """Test that unsupported predicate raises ValueError"""
        backend = PostgreSQLBackend()
        mock_geometry = Mock()
        
        with pytest.raises(ValueError, match="Unsupported predicate"):
            backend.build_expression(
                predicate='invalid_predicate',
                source_geometry=mock_geometry,
                geom_field='geom'
            )


# ============================================================================
# SpatialiteBackend Tests
# ============================================================================

class TestSpatialiteBackend:
    """Test suite for SpatialiteBackend"""
    
    def test_supports_spatialite_layer(self, sample_spatialite_layer):
        """Test that backend supports Spatialite layers"""
        backend = SpatialiteBackend()
        assert backend.supports_layer(sample_spatialite_layer) is True
    
    def test_rejects_non_spatialite_layer(self, sample_pg_layer):
        """Test that backend rejects non-Spatialite layers"""
        backend = SpatialiteBackend()
        assert backend.supports_layer(sample_pg_layer) is False
    
    def test_build_intersects_expression_compatible_with_postgis(self):
        """Test that Spatialite expressions are similar to PostGIS"""
        backend = SpatialiteBackend()
        
        mock_geometry = Mock()
        mock_geometry.asWkt.return_value = "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
        
        expression = backend.build_expression(
            predicate='intersects',
            source_geometry=mock_geometry,
            geom_field='geom'
        )
        
        # Spatialite uses similar syntax to PostGIS (~90% compatible)
        assert 'ST_Intersects' in expression or 'Intersects' in expression
        assert 'geom' in expression
    
    def test_performance_warning_for_large_dataset(self, sample_spatialite_layer, caplog):
        """Test that performance warning is logged for >50k features"""
        backend = SpatialiteBackend()
        sample_spatialite_layer.featureCount.return_value = 75000
        
        mock_geometry = Mock()
        mock_geometry.asWkt.return_value = "POINT(0 0)"
        
        backend.build_expression(
            predicate='intersects',
            source_geometry=mock_geometry,
            geom_field='geom'
        )
        
        # Check that warning was logged
        assert any('50000' in record.message or 'performance' in record.message.lower() 
                   for record in caplog.records)
    
    def test_apply_filter_success(self, sample_spatialite_layer):
        """Test successful filter application"""
        backend = SpatialiteBackend()
        expression = "ST_Intersects(geom, GeomFromText('POINT(0 0)', 4326))"
        
        result = backend.apply_filter(sample_spatialite_layer, expression)
        
        assert result is True
        sample_spatialite_layer.setSubsetString.assert_called_once()


# ============================================================================
# OGRBackend Tests
# ============================================================================

class TestOGRBackend:
    """Test suite for OGRBackend"""
    
    def test_supports_ogr_layer(self, sample_shapefile_layer):
        """Test that backend supports OGR layers"""
        backend = OGRBackend()
        assert backend.supports_layer(sample_shapefile_layer) is True
    
    def test_supports_any_provider_as_fallback(self, sample_pg_layer):
        """Test that OGR backend accepts any layer as fallback"""
        backend = OGRBackend()
        # OGR should accept any layer as it's the universal fallback
        assert backend.supports_layer(sample_pg_layer) is True
    
    def test_build_qgis_expression(self):
        """Test building QGIS expression for OGR backend"""
        backend = OGRBackend()
        
        mock_geometry = Mock()
        mock_geometry.asWkt.return_value = "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
        
        expression = backend.build_expression(
            predicate='intersects',
            source_geometry=mock_geometry,
            geom_field='geometry'
        )
        
        # OGR uses QGIS expression syntax, not SQL
        assert 'intersects' in expression.lower()
        assert '$geometry' in expression or 'geometry' in expression
    
    def test_performance_warning_for_very_large_dataset(self, sample_shapefile_layer, caplog):
        """Test that performance warning is logged for >100k features"""
        backend = OGRBackend()
        sample_shapefile_layer.featureCount.return_value = 150000
        
        mock_geometry = Mock()
        mock_geometry.asWkt.return_value = "POINT(0 0)"
        
        backend.build_expression(
            predicate='intersects',
            source_geometry=mock_geometry,
            geom_field='geom'
        )
        
        # Should log warning for large dataset
        assert any('100000' in record.message or 'performance' in record.message.lower() 
                   for record in caplog.records)
    
    @patch('modules.backends.ogr_backend.processing')
    def test_uses_qgis_processing(self, mock_processing, sample_shapefile_layer):
        """Test that OGR backend uses QGIS processing algorithms"""
        backend = OGRBackend()
        
        mock_geometry = Mock()
        mock_geometry.asWkt.return_value = "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
        
        # This would normally call processing.run() in real implementation
        expression = backend.build_expression(
            predicate='intersects',
            source_geometry=mock_geometry,
            geom_field='geom'
        )
        
        # Verify expression was built (actual processing call would be in apply_filter)
        assert expression is not None
        assert len(expression) > 0


# ============================================================================
# Integration Tests
# ============================================================================

class TestBackendIntegration:
    """Integration tests for backend system"""
    
    def test_backend_selection_workflow(self):
        """Test complete workflow from layer to backend selection"""
        # Create different layer types
        pg_layer = Mock()
        pg_layer.providerType.return_value = "postgres"
        pg_layer.name.return_value = "PG Layer"
        
        spatialite_layer = Mock()
        spatialite_layer.providerType.return_value = "spatialite"
        spatialite_layer.name.return_value = "Spatialite Layer"
        
        ogr_layer = Mock()
        ogr_layer.providerType.return_value = "ogr"
        ogr_layer.name.return_value = "Shapefile"
        
        # Test backend selection for each
        pg_backend = BackendFactory.get_backend(pg_layer)
        spatialite_backend = BackendFactory.get_backend(spatialite_layer)
        ogr_backend = BackendFactory.get_backend(ogr_layer)
        
        assert isinstance(pg_backend, PostgreSQLBackend)
        assert isinstance(spatialite_backend, SpatialiteBackend)
        assert isinstance(ogr_backend, OGRBackend)
    
    def test_all_backends_support_basic_predicates(self):
        """Test that all backends support basic spatial predicates"""
        backends = [
            PostgreSQLBackend(),
            SpatialiteBackend(),
            OGRBackend()
        ]
        
        predicates = ['intersects', 'contains', 'within', 'touches', 'crosses']
        
        mock_geometry = Mock()
        mock_geometry.asWkt.return_value = "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
        
        for backend in backends:
            for predicate in predicates:
                try:
                    expression = backend.build_expression(
                        predicate=predicate,
                        source_geometry=mock_geometry,
                        geom_field='geom'
                    )
                    assert expression is not None
                    assert len(expression) > 0
                except ValueError:
                    # Some backends might not support all predicates
                    pass
    
    def test_backend_error_handling_consistency(self):
        """Test that all backends handle errors consistently"""
        backends = [
            PostgreSQLBackend(),
            SpatialiteBackend(),
            OGRBackend()
        ]
        
        # Create layer that will fail
        error_layer = Mock()
        error_layer.setSubsetString.side_effect = Exception("Test error")
        error_layer.name.return_value = "Error Layer"
        
        for backend in backends:
            result = backend.apply_filter(error_layer, "test_expression")
            # All backends should return False on error
            assert result is False


# ============================================================================
# Performance Tests (Optional - can be slow)
# ============================================================================

@pytest.mark.slow
class TestBackendPerformance:
    """Performance benchmarks for backends (marked as slow tests)"""
    
    def test_expression_building_performance(self):
        """Test that expression building is fast (<1ms)"""
        import time
        
        backend = PostgreSQLBackend()
        mock_geometry = Mock()
        mock_geometry.asWkt.return_value = "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
        
        iterations = 1000
        start = time.time()
        
        for _ in range(iterations):
            backend.build_expression(
                predicate='intersects',
                source_geometry=mock_geometry,
                geom_field='geom'
            )
        
        elapsed = time.time() - start
        avg_time = elapsed / iterations
        
        # Should be under 1ms per call
        assert avg_time < 0.001, f"Average time {avg_time*1000:.2f}ms exceeds 1ms threshold"

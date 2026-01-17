"""
Tests for Auto Backend Selector
Phase 2 (v4.1.0-beta.2): Unit tests for backend recommendation logic.
"""

import pytest
from unittest.mock import Mock, MagicMock
from core.optimization.auto_backend_selector import (
    AutoBackendSelector,
    BackendRecommendation,
    BackendType,
    get_auto_backend_selector
)


@pytest.fixture
def selector():
    """Create fresh AutoBackendSelector for each test."""
    return AutoBackendSelector()


@pytest.fixture
def mock_layer():
    """Create mock QgsVectorLayer."""
    layer = Mock()
    layer.name.return_value = "test_layer"
    layer.id.return_value = "layer_123abc"
    return layer


class TestBackendRecommendation:
    """Test BackendRecommendation dataclass."""
    
    def test_recommendation_creation(self):
        """Test creating recommendation with all fields."""
        rec = BackendRecommendation(
            backend_type='postgresql',
            confidence=0.95,
            reason="Test reason",
            estimated_time_ms=450,
            fallback_backend='spatialite'
        )
        
        assert rec.backend_type == 'postgresql'
        assert rec.confidence == 0.95
        assert rec.reason == "Test reason"
        assert rec.estimated_time_ms == 450
        assert rec.fallback_backend == 'spatialite'
    
    def test_recommendation_without_fallback(self):
        """Test recommendation without fallback backend."""
        rec = BackendRecommendation(
            backend_type='ogr',
            confidence=0.75,
            reason="OGR fallback",
            estimated_time_ms=1000
        )
        
        assert rec.fallback_backend is None


class TestPostgreSQLRecommendations:
    """Test PostgreSQL backend recommendations."""
    
    def test_postgresql_large_dataset(self, selector, mock_layer):
        """PostgreSQL MV recommended for large datasets (>= 10k features)."""
        mock_layer.featureCount.return_value = 15000
        mock_layer.providerType.return_value = 'postgres'
        
        rec = selector.recommend_backend(
            layer=mock_layer,
            filter_params={'expression': '"population" > 10000'},
            available_backends=['postgresql', 'spatialite', 'ogr']
        )
        
        assert rec.backend_type == 'postgresql'
        assert rec.confidence >= 0.90
        assert 'MV optimal' in rec.reason
        assert rec.estimated_time_ms > 0
        assert rec.fallback_backend in ['spatialite', 'ogr']
    
    def test_postgresql_small_dataset(self, selector, mock_layer):
        """PostgreSQL direct subset for small datasets (< 10k features)."""
        mock_layer.featureCount.return_value = 500
        mock_layer.providerType.return_value = 'postgres'
        
        rec = selector.recommend_backend(
            layer=mock_layer,
            filter_params={'expression': '"name" = \'Paris\''},
            available_backends=['postgresql', 'spatialite', 'ogr']
        )
        
        assert rec.backend_type == 'postgresql'
        assert rec.confidence >= 0.80
        assert 'direct subset' in rec.reason or 'small dataset' in rec.reason
    
    def test_postgresql_spatial_filter(self, selector, mock_layer):
        """PostgreSQL with spatial filter has higher estimated time."""
        mock_layer.featureCount.return_value = 10000
        mock_layer.providerType.return_value = 'postgres'
        
        # Simple filter
        rec_simple = selector.recommend_backend(
            layer=mock_layer,
            filter_params={'expression': '"id" > 100'},
            available_backends=['postgresql']
        )
        
        # Spatial filter
        rec_spatial = selector.recommend_backend(
            layer=mock_layer,
            filter_params={
                'expression': 'ST_Intersects($geometry, geom_from_wkt(...))',
                'spatial_op': 'intersects'
            },
            available_backends=['postgresql']
        )
        
        assert rec_spatial.estimated_time_ms > rec_simple.estimated_time_ms


class TestSpatialiteRecommendations:
    """Test Spatialite backend recommendations."""
    
    def test_spatialite_optimal_range(self, selector, mock_layer):
        """Spatialite recommended for sweet spot (100-50k features)."""
        mock_layer.featureCount.return_value = 25000
        mock_layer.providerType.return_value = 'spatialite'
        
        rec = selector.recommend_backend(
            layer=mock_layer,
            filter_params={'expression': '"status" = \'active\''},
            available_backends=['spatialite', 'ogr']
        )
        
        assert rec.backend_type == 'spatialite'
        assert rec.confidence >= 0.85
        assert 'optimal' in rec.reason or 'sweet spot' in rec.reason
        assert rec.fallback_backend == 'ogr'
    
    def test_spatialite_large_dataset_fallback_ogr(self, selector, mock_layer):
        """OGR recommended for very large Spatialite (> 100k features)."""
        mock_layer.featureCount.return_value = 150000
        mock_layer.providerType.return_value = 'spatialite'
        
        rec = selector.recommend_backend(
            layer=mock_layer,
            filter_params={'expression': '"year" > 2020'},
            available_backends=['spatialite', 'ogr']
        )
        
        assert rec.backend_type == 'ogr'
        assert 'large' in rec.reason or '100k' in rec.reason
        assert rec.fallback_backend == 'spatialite'
    
    def test_spatialite_small_dataset(self, selector, mock_layer):
        """Spatialite used even for small datasets if in provider."""
        mock_layer.featureCount.return_value = 50
        mock_layer.providerType.return_value = 'spatialite'
        
        rec = selector.recommend_backend(
            layer=mock_layer,
            filter_params={'expression': 'TRUE'},
            available_backends=['spatialite', 'ogr']
        )
        
        # Either spatialite or ogr acceptable for small datasets
        assert rec.backend_type in ['spatialite', 'ogr']


class TestOGRRecommendations:
    """Test OGR backend recommendations."""
    
    def test_ogr_universal_fallback(self, selector, mock_layer):
        """OGR recommended as universal fallback."""
        mock_layer.featureCount.return_value = 5000
        mock_layer.providerType.return_value = 'ogr'
        
        rec = selector.recommend_backend(
            layer=mock_layer,
            filter_params={'expression': '"category" IN (1, 2, 3)'},
            available_backends=['ogr']
        )
        
        assert rec.backend_type == 'ogr'
        assert rec.confidence >= 0.70
        assert rec.fallback_backend is None  # OGR is last resort
    
    def test_ogr_shapefile_provider(self, selector, mock_layer):
        """OGR recommended for Shapefile provider."""
        mock_layer.featureCount.return_value = 1000
        mock_layer.providerType.return_value = 'ogr'
        
        rec = selector.recommend_backend(
            layer=mock_layer,
            filter_params={'expression': '"field1" IS NOT NULL'},
            available_backends=['ogr', 'spatialite']
        )
        
        assert rec.backend_type == 'ogr'


class TestPerformanceHistory:
    """Test performance tracking and learning."""
    
    def test_record_performance(self, selector):
        """Test recording performance history."""
        selector.record_performance('postgresql', 'layer_abc', 450)
        selector.record_performance('postgresql', 'layer_abc', 480)
        selector.record_performance('postgresql', 'layer_abc', 430)
        
        history = selector.performance_history['postgresql']['layer_abc']
        assert len(history) == 3
        assert 450 in history
        assert 480 in history
        assert 430 in history
    
    def test_performance_rolling_window(self, selector):
        """Test performance history keeps last 10 measurements."""
        for i in range(15):
            selector.record_performance('spatialite', 'layer_xyz', 100 + i)
        
        history = selector.performance_history['spatialite']['layer_xyz']
        assert len(history) == 10
        # Should have last 10 values (105-114)
        assert 105 in history
        assert 114 in history
        assert 100 not in history  # First 5 dropped
    
    def test_average_performance_calculation(self, selector):
        """Test average performance calculation."""
        selector.record_performance('postgresql', 'layer_123', 400)
        selector.record_performance('postgresql', 'layer_123', 500)
        selector.record_performance('postgresql', 'layer_123', 600)
        
        avg = selector._get_average_performance('postgresql', 'layer_123')
        assert avg == 500  # (400 + 500 + 600) / 3


class TestComplexityAnalysis:
    """Test filter complexity detection."""
    
    def test_spatial_predicates_detection(self, selector):
        """Test detection of spatial predicates."""
        assert selector._has_spatial_predicates('ST_Intersects($geometry, other)')
        assert selector._has_spatial_predicates('intersects($geometry, buffer)')
        assert selector._has_spatial_predicates('ST_Contains(geom1, geom2)')
        assert not selector._has_spatial_predicates('"name" = \'test\'')
        assert not selector._has_spatial_predicates('"id" > 100 AND "status" = 1')
    
    def test_complexity_multiplier_simple(self, selector):
        """Simple filter has multiplier 1.0."""
        multiplier = selector._get_complexity_multiplier('"id" = 5', has_spatial=False)
        assert multiplier == 1.0
    
    def test_complexity_multiplier_spatial(self, selector):
        """Spatial filter has multiplier 2.5."""
        multiplier = selector._get_complexity_multiplier('ST_Intersects(...)', has_spatial=True)
        assert multiplier == 2.5
    
    def test_complexity_multiplier_complex(self, selector):
        """Complex filter with multiple AND/OR has multiplier 5.0."""
        expression = '"a" = 1 AND "b" = 2 AND "c" = 3 AND "d" = 4 AND "e" = 5'
        multiplier = selector._get_complexity_multiplier(expression, has_spatial=False)
        assert multiplier == 5.0


class TestSingletonPattern:
    """Test singleton factory function."""
    
    def test_singleton_returns_same_instance(self):
        """get_auto_backend_selector returns same instance."""
        instance1 = get_auto_backend_selector()
        instance2 = get_auto_backend_selector()
        
        assert instance1 is instance2
    
    def test_singleton_shared_state(self):
        """Singleton instances share performance history."""
        instance1 = get_auto_backend_selector()
        instance1.record_performance('postgresql', 'layer_shared', 300)
        
        instance2 = get_auto_backend_selector()
        history = instance2.performance_history['postgresql'].get('layer_shared')
        
        assert history is not None
        assert 300 in history


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_available_backends(self, selector, mock_layer):
        """Handles empty available_backends list."""
        mock_layer.featureCount.return_value = 1000
        mock_layer.providerType.return_value = 'postgres'
        
        rec = selector.recommend_backend(
            layer=mock_layer,
            filter_params={'expression': 'TRUE'},
            available_backends=[]
        )
        
        assert rec.backend_type == 'ogr'  # Default fallback
        assert rec.confidence <= 0.60
    
    def test_unknown_provider_type(self, selector, mock_layer):
        """Handles unknown provider types."""
        mock_layer.featureCount.return_value = 500
        mock_layer.providerType.return_value = 'wfs'  # Unknown provider
        
        rec = selector.recommend_backend(
            layer=mock_layer,
            filter_params={'expression': '"field" = 1'},
            available_backends=['ogr']
        )
        
        assert rec.backend_type == 'ogr'
    
    def test_zero_features(self, selector, mock_layer):
        """Handles layers with zero features."""
        mock_layer.featureCount.return_value = 0
        mock_layer.providerType.return_value = 'spatialite'
        
        rec = selector.recommend_backend(
            layer=mock_layer,
            filter_params={'expression': 'FALSE'},
            available_backends=['spatialite', 'ogr']
        )
        
        # Should still return valid recommendation
        assert rec.backend_type in ['spatialite', 'ogr']
        assert rec.estimated_time_ms >= 0

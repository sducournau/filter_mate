"""
Tests for BackendService.

Story: MIG-075
Phase: 6 - God Class DockWidget Migration
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Add plugin path for imports
plugin_path = Path(__file__).parents[4]
if str(plugin_path) not in sys.path:
    sys.path.insert(0, str(plugin_path))


class TestBackendService:
    """Tests for BackendService class."""

    @pytest.fixture
    def service(self):
        """Create BackendService instance."""
        from core.services.backend_service import BackendService
        return BackendService()

    @pytest.fixture
    def mock_layer(self):
        """Create mock QgsVectorLayer."""
        layer = Mock()
        layer.id = Mock(return_value="layer_123")
        layer.name = Mock(return_value="Test Layer")
        layer.isValid = Mock(return_value=True)
        layer.providerType = Mock(return_value="ogr")
        layer.source = Mock(return_value="/path/to/file.shp")
        layer.featureCount = Mock(return_value=1000)
        return layer

    def test_creation(self):
        """Should create service without errors."""
        from core.services.backend_service import BackendService
        service = BackendService()
        assert service is not None
        assert len(service._forced_backends) == 0

    def test_get_available_backends(self, service):
        """Should return list of available backends."""
        backends = service.get_available_backends()
        
        assert len(backends) >= 2  # At least Spatialite and OGR
        
        # Check backend types
        types = [b.type.value for b in backends]
        assert "spatialite" in types
        assert "ogr" in types


class TestBackendDetection:
    """Tests for backend detection."""

    @pytest.fixture
    def service(self):
        """Create BackendService instance."""
        from core.services.backend_service import BackendService
        return BackendService()

    @pytest.fixture
    def mock_layer(self):
        """Create mock QgsVectorLayer."""
        layer = Mock()
        layer.id = Mock(return_value="layer_123")
        layer.name = Mock(return_value="Test Layer")
        layer.isValid = Mock(return_value=True)
        layer.providerType = Mock(return_value="ogr")
        layer.source = Mock(return_value="/path/to/file.shp")
        return layer

    def test_detect_ogr_layer(self, service, mock_layer):
        """Should detect OGR backend for OGR layer."""
        from core.services.backend_service import BackendType
        
        mock_layer.providerType.return_value = "ogr"
        
        detected = service.detect_backend(mock_layer)
        
        assert detected == BackendType.OGR

    def test_detect_spatialite_layer(self, service, mock_layer):
        """Should detect Spatialite backend for Spatialite layer."""
        from core.services.backend_service import BackendType
        
        mock_layer.providerType.return_value = "spatialite"
        
        detected = service.detect_backend(mock_layer)
        
        assert detected == BackendType.SPATIALITE

    @patch('core.services.backend_service.BackendService.is_postgresql_available', True)
    def test_detect_postgres_layer(self, service, mock_layer):
        """Should detect PostgreSQL backend for postgres layer when available."""
        from core.services.backend_service import BackendType
        
        mock_layer.providerType.return_value = "postgres"
        service._postgresql_available = True
        
        detected = service.detect_backend(mock_layer)
        
        assert detected == BackendType.POSTGRESQL

    def test_detect_invalid_layer(self, service):
        """Should return OGR for invalid layer."""
        from core.services.backend_service import BackendType
        
        mock_layer = Mock()
        mock_layer.isValid.return_value = False
        
        detected = service.detect_backend(mock_layer)
        
        assert detected == BackendType.OGR

    def test_detect_none_layer(self, service):
        """Should return OGR for None layer."""
        from core.services.backend_service import BackendType
        
        detected = service.detect_backend(None)
        
        assert detected == BackendType.OGR


class TestBackendForcing:
    """Tests for backend forcing."""

    @pytest.fixture
    def service(self):
        """Create BackendService instance."""
        from core.services.backend_service import BackendService
        return BackendService()

    @pytest.fixture
    def mock_layer(self):
        """Create mock QgsVectorLayer."""
        layer = Mock()
        layer.id = Mock(return_value="layer_123")
        layer.name = Mock(return_value="Test Layer")
        layer.isValid = Mock(return_value=True)
        layer.providerType = Mock(return_value="ogr")
        return layer

    def test_force_backend(self, service, mock_layer):
        """Should force backend for layer."""
        from core.services.backend_service import BackendType
        
        signals_received = []
        service.backend_changed.connect(
            lambda lid, bt: signals_received.append((lid, bt))
        )
        
        service.force_backend("layer_123", BackendType.SPATIALITE)
        
        assert service.get_forced_backend("layer_123") == BackendType.SPATIALITE
        assert len(signals_received) == 1
        assert signals_received[0] == ("layer_123", "spatialite")

    def test_force_backend_string(self, service):
        """Should force backend using string type."""
        from core.services.backend_service import BackendType
        
        service.force_backend_string("layer_123", "spatialite")
        
        assert service.get_forced_backend("layer_123") == BackendType.SPATIALITE

    def test_clear_forced_backend(self, service):
        """Should clear forced backend."""
        from core.services.backend_service import BackendType
        
        service.force_backend("layer_123", BackendType.SPATIALITE)
        assert service.get_forced_backend("layer_123") is not None
        
        service.clear_forced_backend("layer_123")
        
        assert service.get_forced_backend("layer_123") is None

    def test_clear_all_forced_backends(self, service):
        """Should clear all forced backends."""
        from core.services.backend_service import BackendType
        
        service.force_backend("layer_1", BackendType.SPATIALITE)
        service.force_backend("layer_2", BackendType.OGR)
        
        service.clear_all_forced_backends()
        
        assert service.get_forced_backend("layer_1") is None
        assert service.get_forced_backend("layer_2") is None

    def test_forced_backend_overrides_detection(self, service, mock_layer):
        """Forced backend should override auto-detection."""
        from core.services.backend_service import BackendType
        
        mock_layer.providerType.return_value = "ogr"  # Would detect OGR
        
        service.force_backend("layer_123", BackendType.SPATIALITE)
        
        detected = service.detect_backend(mock_layer)
        
        assert detected == BackendType.SPATIALITE  # Forced, not detected

    def test_get_forced_backend_string(self, service):
        """Should get forced backend as string."""
        from core.services.backend_service import BackendType
        
        service.force_backend("layer_123", BackendType.SPATIALITE)
        
        result = service.get_forced_backend_string("layer_123")
        
        assert result == "spatialite"

    def test_get_forced_backend_string_none(self, service):
        """Should return None when no forced backend."""
        result = service.get_forced_backend_string("nonexistent")
        
        assert result is None


class TestBackendCompatibility:
    """Tests for backend compatibility checking."""

    @pytest.fixture
    def service(self):
        """Create BackendService instance."""
        from core.services.backend_service import BackendService
        return BackendService()

    @pytest.fixture
    def mock_layer(self):
        """Create mock QgsVectorLayer."""
        layer = Mock()
        layer.id = Mock(return_value="layer_123")
        layer.name = Mock(return_value="Test Layer")
        layer.isValid = Mock(return_value=True)
        layer.providerType = Mock(return_value="ogr")
        layer.source = Mock(return_value="/path/to/file.shp")
        return layer

    def test_ogr_compatible_with_all_layers(self, service, mock_layer):
        """OGR should be compatible with all valid layers."""
        from core.services.backend_service import BackendType
        
        is_compatible, has_warning = service._check_backend_compatibility(
            mock_layer, BackendType.OGR
        )
        
        assert is_compatible is True
        assert has_warning is False

    def test_spatialite_compatible_with_spatialite_layer(self, service, mock_layer):
        """Spatialite should be compatible with spatialite layers."""
        from core.services.backend_service import BackendType
        
        mock_layer.providerType.return_value = "spatialite"
        
        is_compatible, has_warning = service._check_backend_compatibility(
            mock_layer, BackendType.SPATIALITE
        )
        
        assert is_compatible is True
        assert has_warning is False

    def test_spatialite_compatible_with_geopackage(self, service, mock_layer):
        """Spatialite should be compatible with GeoPackage (with warning)."""
        from core.services.backend_service import BackendType
        
        mock_layer.providerType.return_value = "ogr"
        mock_layer.source.return_value = "/path/to/file.gpkg|layername=test"
        
        is_compatible, has_warning = service._check_backend_compatibility(
            mock_layer, BackendType.SPATIALITE
        )
        
        assert is_compatible is True
        assert has_warning is True  # Warning for GeoPackage

    def test_postgresql_not_compatible_with_ogr_layer(self, service, mock_layer):
        """PostgreSQL should not be compatible with OGR layers."""
        from core.services.backend_service import BackendType
        
        mock_layer.providerType.return_value = "ogr"
        service._postgresql_available = True
        
        is_compatible, has_warning = service._check_backend_compatibility(
            mock_layer, BackendType.POSTGRESQL
        )
        
        assert is_compatible is False


class TestAvailableBackendsForLayer:
    """Tests for getting available backends for a layer."""

    @pytest.fixture
    def service(self):
        """Create BackendService instance."""
        from core.services.backend_service import BackendService
        return BackendService()

    @pytest.fixture
    def mock_layer(self):
        """Create mock QgsVectorLayer."""
        layer = Mock()
        layer.id = Mock(return_value="layer_123")
        layer.name = Mock(return_value="Test Layer")
        layer.isValid = Mock(return_value=True)
        layer.providerType = Mock(return_value="ogr")
        layer.source = Mock(return_value="/path/to/file.shp")
        return layer

    def test_ogr_layer_has_ogr_backend(self, service, mock_layer):
        """OGR layer should have OGR backend available."""
        from core.services.backend_service import BackendType
        
        available = service.get_available_backends_for_layer(mock_layer)
        
        types = [b.type for b in available]
        assert BackendType.OGR in types

    def test_geopackage_layer_has_spatialite_backend(self, service, mock_layer):
        """GeoPackage layer should have Spatialite backend available."""
        from core.services.backend_service import BackendType
        
        mock_layer.source.return_value = "/path/to/file.gpkg"
        
        available = service.get_available_backends_for_layer(mock_layer)
        
        types = [b.type for b in available]
        assert BackendType.SPATIALITE in types
        assert BackendType.OGR in types

    def test_spatialite_layer_has_spatialite_backend(self, service, mock_layer):
        """Spatialite layer should have Spatialite backend available."""
        from core.services.backend_service import BackendType
        
        mock_layer.providerType.return_value = "spatialite"
        
        available = service.get_available_backends_for_layer(mock_layer)
        
        types = [b.type for b in available]
        assert BackendType.SPATIALITE in types

    def test_invalid_layer_returns_empty(self, service):
        """Invalid layer should return empty list."""
        mock_layer = Mock()
        mock_layer.isValid.return_value = False
        
        available = service.get_available_backends_for_layer(mock_layer)
        
        assert len(available) == 0

    def test_emits_backends_available_signal(self, service, mock_layer):
        """Should emit backends_available signal."""
        signals_received = []
        service.backends_available.connect(lambda b: signals_received.append(b))
        
        service.get_available_backends_for_layer(mock_layer)
        
        assert len(signals_received) == 1


class TestBackendRecommendation:
    """Tests for optimal backend recommendation."""

    @pytest.fixture
    def service(self):
        """Create BackendService instance."""
        from core.services.backend_service import BackendService
        return BackendService()

    @pytest.fixture
    def mock_layer(self):
        """Create mock QgsVectorLayer."""
        layer = Mock()
        layer.id = Mock(return_value="layer_123")
        layer.name = Mock(return_value="Test Layer")
        layer.isValid = Mock(return_value=True)
        layer.providerType = Mock(return_value="ogr")
        layer.source = Mock(return_value="/path/to/file.shp")
        layer.featureCount = Mock(return_value=1000)
        return layer

    def test_recommend_ogr_for_shapefile(self, service, mock_layer):
        """Should recommend OGR for shapefile."""
        from core.services.backend_service import BackendType
        
        recommendation = service.recommend_optimal_backend(mock_layer)
        
        assert recommendation.recommended == BackendType.OGR

    def test_recommend_spatialite_for_spatialite_layer(self, service, mock_layer):
        """Should recommend Spatialite for spatialite layer."""
        from core.services.backend_service import BackendType
        
        mock_layer.providerType.return_value = "spatialite"
        
        recommendation = service.recommend_optimal_backend(mock_layer)
        
        assert recommendation.recommended == BackendType.SPATIALITE

    def test_recommend_spatialite_for_large_geopackage(self, service, mock_layer):
        """Should recommend Spatialite for large GeoPackage dataset."""
        from core.services.backend_service import BackendType
        
        mock_layer.source.return_value = "/path/to/file.gpkg"
        mock_layer.featureCount.return_value = 100000  # Large dataset
        
        recommendation = service.recommend_optimal_backend(mock_layer)
        
        assert recommendation.recommended == BackendType.SPATIALITE

    def test_recommendation_includes_reason(self, service, mock_layer):
        """Recommendation should include reason."""
        recommendation = service.recommend_optimal_backend(mock_layer)
        
        assert recommendation.reason is not None
        assert len(recommendation.reason) > 0

    def test_recommendation_includes_feature_count(self, service, mock_layer):
        """Recommendation should include feature count."""
        mock_layer.featureCount.return_value = 5000
        
        recommendation = service.recommend_optimal_backend(mock_layer)
        
        assert recommendation.feature_count == 5000


class TestStateManagement:
    """Tests for state management."""

    @pytest.fixture
    def service(self):
        """Create BackendService instance."""
        from core.services.backend_service import BackendService
        return BackendService()

    def test_get_forced_backends_summary(self, service):
        """Should return summary of forced backends."""
        from core.services.backend_service import BackendType
        
        service.force_backend("layer_1", BackendType.SPATIALITE)
        service.force_backend("layer_2", BackendType.OGR)
        
        summary = service.get_forced_backends_summary()
        
        assert summary == {
            "layer_1": "spatialite",
            "layer_2": "ogr"
        }

    def test_set_forced_backends_from_dict(self, service):
        """Should restore forced backends from dict."""
        from core.services.backend_service import BackendType
        
        saved = {
            "layer_1": "spatialite",
            "layer_2": "ogr"
        }
        
        service.set_forced_backends_from_dict(saved)
        
        assert service.get_forced_backend("layer_1") == BackendType.SPATIALITE
        assert service.get_forced_backend("layer_2") == BackendType.OGR

    def test_cleanup_removed_layers(self, service):
        """Should remove forced backends for removed layers."""
        from core.services.backend_service import BackendType
        
        service.force_backend("layer_1", BackendType.SPATIALITE)
        service.force_backend("layer_2", BackendType.OGR)
        service.force_backend("layer_3", BackendType.OGR)
        
        # Only layer_1 still exists
        removed = service.cleanup_removed_layers(["layer_1"])
        
        assert removed == 2
        assert service.get_forced_backend("layer_1") == BackendType.SPATIALITE
        assert service.get_forced_backend("layer_2") is None
        assert service.get_forced_backend("layer_3") is None


class TestBackendHelpers:
    """Tests for backend helper methods."""

    @pytest.fixture
    def service(self):
        """Create BackendService instance."""
        from core.services.backend_service import BackendService
        return BackendService()

    def test_get_backend_display_info(self, service):
        """Should return display name and icon."""
        from core.services.backend_service import BackendType
        
        name, icon = service.get_backend_display_info(BackendType.POSTGRESQL)
        
        assert name == "PostgreSQL"
        assert icon == "🐘"

    def test_get_backend_from_string(self, service):
        """Should convert string to BackendType."""
        from core.services.backend_service import BackendType
        
        result = service.get_backend_from_string("spatialite")
        
        assert result == BackendType.SPATIALITE

    def test_get_backend_from_invalid_string(self, service):
        """Should return OGR for invalid string."""
        from core.services.backend_service import BackendType
        
        result = service.get_backend_from_string("invalid")
        
        assert result == BackendType.OGR

    def test_get_current_backend_string(self, service):
        """Should return current backend as string."""
        mock_layer = Mock()
        mock_layer.isValid.return_value = True
        mock_layer.id.return_value = "layer_123"
        mock_layer.providerType.return_value = "spatialite"
        
        result = service.get_current_backend_string(mock_layer)
        
        assert result == "spatialite"

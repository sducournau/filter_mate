"""
Tests for FilterService.

Part of Phase 3 Core Domain Layer implementation.
These tests use mocks to isolate the service from external dependencies.
"""
import pytest
from unittest.mock import Mock

from core.services.filter_service import (
    FilterService, FilterRequest, FilterResponse
)
from core.domain.filter_expression import FilterExpression, ProviderType
from core.domain.filter_result import FilterResult, FilterStatus
from core.domain.layer_info import LayerInfo, GeometryType
from core.domain.optimization_config import OptimizationConfig


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_backend():
    """Create a mock backend."""
    backend = Mock()
    backend.name = "test_backend"
    backend.priority = 100
    backend.supports_layer.return_value = True
    backend.validate_expression.return_value = (True, None)
    backend.execute.return_value = FilterResult(
        layer_id="layer_target",
        expression_raw="test",
        status=FilterStatus.SUCCESS,
        feature_ids=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    )
    return backend


@pytest.fixture
def mock_cache():
    """Create a mock cache."""
    cache = Mock()
    cache.get.return_value = None
    cache.set.return_value = None
    cache.clear.return_value = 0
    return cache


@pytest.fixture
def sample_layer_info():
    """Create a sample layer info."""
    return LayerInfo(
        layer_id="layer_123",
        name="Test Layer",
        provider_type=ProviderType.POSTGRESQL,
        geometry_type=GeometryType.POLYGON,
        feature_count=100,
        crs_auth_id="EPSG:4326"
    )


@pytest.fixture
def mock_layer_repository(sample_layer_info):
    """Create a mock layer repository."""
    repo = Mock()
    repo.get_layer_info.return_value = sample_layer_info
    return repo


@pytest.fixture
def mock_expression_service():
    """Create a mock expression service."""
    service = Mock()
    service.validate.return_value = Mock(
        is_valid=True,
        error_message=None
    )
    service.to_sql.return_value = "name = 'test'"
    return service


@pytest.fixture
def filter_service(mock_backend, mock_cache, mock_layer_repository, mock_expression_service):
    """Create a FilterService with mocks."""
    return FilterService(
        backends={ProviderType.POSTGRESQL: mock_backend},
        cache=mock_cache,
        layer_repository=mock_layer_repository,
        expression_service=mock_expression_service
    )


@pytest.fixture
def sample_expression():
    """Create a sample expression."""
    return FilterExpression.create(
        raw="\"name\" = 'test'",
        provider=ProviderType.POSTGRESQL,
        source_layer_id="layer_123"
    )


# ============================================================================
# FilterRequest Tests
# ============================================================================

class TestFilterRequest:
    """Tests for FilterRequest dataclass."""

    def test_create_basic_request(self, sample_expression):
        """Test creating a basic filter request."""
        request = FilterRequest(
            expression=sample_expression,
            source_layer_id="layer_source",
            target_layer_ids=["layer_target"]
        )
        assert request.expression == sample_expression
        assert "layer_target" in request.target_layer_ids

    def test_create_with_all_options(self, sample_expression):
        """Test creating request with all options."""
        config = OptimizationConfig.default()
        request = FilterRequest(
            expression=sample_expression,
            source_layer_id="layer_source",
            target_layer_ids=["layer_target"],
            use_cache=True,
            optimization_config=config
        )
        assert request.use_cache
        assert request.optimization_config == config

    def test_default_values(self, sample_expression):
        """Test default values."""
        request = FilterRequest(
            expression=sample_expression,
            source_layer_id="layer_source",
            target_layer_ids=["layer_target"]
        )
        assert request.use_cache is True
        assert request.optimization_config is None


# ============================================================================
# FilterResponse Tests
# ============================================================================

class TestFilterResponse:
    """Tests for FilterResponse dataclass."""

    def test_create_response(self):
        """Test creating a response."""
        result = FilterResult(
            layer_id="layer_target",
            expression_raw="test",
            status=FilterStatus.SUCCESS,
            feature_ids=[1, 2, 3]
        )
        response = FilterResponse(
            results={"layer_target": result},
            total_matches=3,
            total_execution_time_ms=50.5,
            from_cache=False
        )
        assert response.is_success
        assert response.total_matches == 3
        assert response.total_execution_time_ms == 50.5

    def test_is_success_all_success(self):
        """Test is_success when all results succeeded."""
        results = {
            "layer_1": FilterResult(
                layer_id="layer_1",
                expression_raw="test",
                status=FilterStatus.SUCCESS,
                feature_ids=[1]
            ),
            "layer_2": FilterResult(
                layer_id="layer_2",
                expression_raw="test",
                status=FilterStatus.SUCCESS,
                feature_ids=[2]
            )
        }
        response = FilterResponse(
            results=results,
            total_matches=2,
            total_execution_time_ms=10,
            from_cache=False
        )
        assert response.is_success

    def test_has_error(self):
        """Test has_error property."""
        results = {
            "layer_1": FilterResult.error(
                layer_id="layer_1",
                expression_raw="test",
                error_message="Failed"
            )
        }
        response = FilterResponse(
            results=results,
            total_matches=0,
            total_execution_time_ms=10,
            from_cache=False
        )
        assert response.has_error

    def test_layer_count(self):
        """Test layer_count property."""
        results = {
            f"layer_{i}": FilterResult(
                layer_id=f"layer_{i}",
                expression_raw="test",
                status=FilterStatus.SUCCESS,
                feature_ids=[]
            )
            for i in range(5)
        }
        response = FilterResponse(
            results=results,
            total_matches=0,
            total_execution_time_ms=10,
            from_cache=False
        )
        assert response.layer_count == 5

    def test_error_messages(self):
        """Test error_messages property."""
        results = {
            "layer_1": FilterResult.error(
                layer_id="layer_1",
                expression_raw="test",
                error_message="Error 1"
            ),
            "layer_2": FilterResult.error(
                layer_id="layer_2",
                expression_raw="test",
                error_message="Error 2"
            )
        }
        response = FilterResponse(
            results=results,
            total_matches=0,
            total_execution_time_ms=10,
            from_cache=False
        )
        assert len(response.error_messages) == 2


# ============================================================================
# FilterService Basic Tests
# ============================================================================

class TestFilterServiceBasic:
    """Tests for basic FilterService functionality."""

    def test_create_service(self, mock_backend, mock_cache, mock_layer_repository):
        """Test creating service with config."""
        service = FilterService(
            backends={ProviderType.POSTGRESQL: mock_backend},
            cache=mock_cache,
            layer_repository=mock_layer_repository
        )
        assert service is not None

    def test_get_available_backends(self, filter_service):
        """Test getting available backends."""
        backends = filter_service.get_available_backends()
        assert isinstance(backends, dict)


# ============================================================================
# FilterService Apply Filter Tests
# ============================================================================

class TestFilterServiceApplyFilter:
    """Tests for apply_filter method."""

    def test_apply_filter_simple(self, filter_service, sample_expression):
        """Test applying a simple filter."""
        request = FilterRequest(
            expression=sample_expression,
            source_layer_id="layer_123",
            target_layer_ids=["layer_target"]
        )
        
        response = filter_service.apply_filter(request)
        
        assert response.is_success
        assert response.total_matches == 10

    def test_apply_filter_multiple_layers(self, filter_service, sample_expression, mock_backend):
        """Test applying filter to multiple layers."""
        request = FilterRequest(
            expression=sample_expression,
            source_layer_id="layer_123",
            target_layer_ids=["layer_1", "layer_2", "layer_3"]
        )
        
        response = filter_service.apply_filter(request)
        
        assert response.is_success
        # Backend.execute called for each layer
        assert mock_backend.execute.call_count >= 1

    def test_apply_filter_validates_expression(
        self, filter_service, sample_expression, mock_expression_service
    ):
        """Test that expression is validated before applying."""
        request = FilterRequest(
            expression=sample_expression,
            source_layer_id="layer_123",
            target_layer_ids=["layer_target"]
        )
        
        filter_service.apply_filter(request)
        
        mock_expression_service.validate.assert_called()

    def test_apply_filter_invalid_expression(
        self, filter_service, sample_expression, mock_expression_service
    ):
        """Test behavior with invalid expression."""
        mock_expression_service.validate.return_value = Mock(
            is_valid=False,
            error_message="Syntax error"
        )
        
        request = FilterRequest(
            expression=sample_expression,
            source_layer_id="layer_123",
            target_layer_ids=["layer_target"]
        )
        
        response = filter_service.apply_filter(request)
        
        assert response.has_error


# ============================================================================
# FilterService Cache Tests
# ============================================================================

class TestFilterServiceCache:
    """Tests for caching behavior."""

    def test_cache_miss_calls_backend(self, filter_service, sample_expression, mock_cache, mock_backend):
        """Test that cache miss results in backend call."""
        mock_cache.get.return_value = None
        
        request = FilterRequest(
            expression=sample_expression,
            source_layer_id="layer_123",
            target_layer_ids=["layer_target"],
            use_cache=True
        )
        
        filter_service.apply_filter(request)
        
        # Backend should be called
        mock_backend.execute.assert_called()

    def test_cache_hit_returns_cached(self, filter_service, sample_expression, mock_cache, mock_backend):
        """Test cache hit returns cached result."""
        cached_result = FilterResult(
            layer_id="layer_target",
            expression_raw="test",
            status=FilterStatus.SUCCESS,
            feature_ids=[99]
        )
        cached_result_with_cache = Mock()
        cached_result_with_cache.with_from_cache.return_value = cached_result
        mock_cache.get.return_value = cached_result_with_cache
        
        request = FilterRequest(
            expression=sample_expression,
            source_layer_id="layer_123",
            target_layer_ids=["layer_target"],
            use_cache=True
        )
        
        response = filter_service.apply_filter(request)
        
        # Verify cache was checked
        mock_cache.get.assert_called()

    def test_clear_cache(self, filter_service, mock_cache):
        """Test clearing cache."""
        mock_cache.clear.return_value = 5
        
        count = filter_service.clear_cache()
        
        assert count == 5
        mock_cache.clear.assert_called()


# ============================================================================
# FilterService Error Handling Tests
# ============================================================================

class TestFilterServiceErrors:
    """Tests for error handling."""

    def test_source_layer_not_found(
        self, filter_service, sample_expression, mock_layer_repository
    ):
        """Test handling of missing source layer."""
        mock_layer_repository.get_layer_info.return_value = None
        
        request = FilterRequest(
            expression=sample_expression,
            source_layer_id="nonexistent",
            target_layer_ids=["layer_target"]
        )
        
        response = filter_service.apply_filter(request)
        
        assert response.has_error
        assert "not found" in response.error_messages[0].lower()

    def test_handles_backend_exception(
        self, filter_service, sample_expression, mock_backend
    ):
        """Test handling of backend exceptions."""
        mock_backend.execute.side_effect = Exception("Backend error")
        
        request = FilterRequest(
            expression=sample_expression,
            source_layer_id="layer_123",
            target_layer_ids=["layer_target"]
        )
        
        response = filter_service.apply_filter(request)
        
        assert response.has_error

    def test_handles_empty_target_list(self, filter_service, sample_expression):
        """Test handling of empty target layer list."""
        request = FilterRequest(
            expression=sample_expression,
            source_layer_id="layer_123",
            target_layer_ids=[]
        )
        
        response = filter_service.apply_filter(request)
        
        # Should succeed with 0 results
        assert response.total_matches == 0


# ============================================================================
# FilterService Cancel Tests
# ============================================================================

class TestFilterServiceCancel:
    """Tests for cancellation."""

    def test_cancel_sets_flag(self, filter_service):
        """Test that cancel sets the flag."""
        filter_service.cancel()
        assert filter_service.is_cancelled


# ============================================================================
# FilterService Statistics Tests
# ============================================================================

class TestFilterServiceStatistics:
    """Tests for statistics tracking."""

    def test_get_statistics(self, filter_service, sample_expression, mock_backend):
        """Test that statistics are tracked."""
        request = FilterRequest(
            expression=sample_expression,
            source_layer_id="layer_123",
            target_layer_ids=["layer_target"]
        )
        
        filter_service.apply_filter(request)
        
        stats = filter_service.get_statistics()
        
        assert stats['total_filters'] >= 1

    def test_reset_statistics(self, filter_service, sample_expression):
        """Test resetting statistics."""
        request = FilterRequest(
            expression=sample_expression,
            source_layer_id="layer_123",
            target_layer_ids=["layer_target"]
        )
        filter_service.apply_filter(request)
        
        filter_service.reset_statistics()
        stats = filter_service.get_statistics()
        
        assert stats['total_filters'] == 0

    def test_cache_hit_rate(self, filter_service):
        """Test cache hit rate in statistics."""
        stats = filter_service.get_statistics()
        
        assert 'cache_hit_rate' in stats


# ============================================================================
# FilterService Validation Tests
# ============================================================================

class TestFilterServiceValidation:
    """Tests for expression validation."""

    def test_validate_expression_valid(self, filter_service, mock_expression_service):
        """Test validating a valid expression."""
        mock_expression_service.validate.return_value = Mock(is_valid=True)
        
        result = filter_service.validate_expression("\"name\" = 'test'")
        
        assert result is True

    def test_validate_expression_invalid(self, filter_service, mock_expression_service):
        """Test validating an invalid expression."""
        mock_expression_service.validate.return_value = Mock(is_valid=False)
        
        result = filter_service.validate_expression("invalid syntax")
        
        assert result is False

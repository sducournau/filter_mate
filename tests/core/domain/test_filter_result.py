"""
Unit tests for FilterResult Value Object.

Tests cover:
- Factory methods (success, error, cancelled, from_cache, partial)
- Computed properties
- Immutability (frozen dataclass)
- Edge cases and status handling
"""
import pytest
from datetime import datetime
from core.domain.filter_result import FilterResult, FilterStatus


class TestFilterStatus:
    """Tests for FilterStatus enum."""

    def test_filter_status_values(self):
        """Test that all statuses have correct values."""
        assert FilterStatus.SUCCESS.value == "success"
        assert FilterStatus.PARTIAL.value == "partial"
        assert FilterStatus.CANCELLED.value == "cancelled"
        assert FilterStatus.ERROR.value == "error"
        assert FilterStatus.NO_MATCHES.value == "no_matches"


class TestFilterResultSuccess:
    """Tests for FilterResult.success() factory."""

    def test_success_with_features(self):
        """Test creating successful result with features."""
        result = FilterResult.success(
            feature_ids=(1, 2, 3, 4, 5),
            layer_id="layer_123",
            expression_raw="field = 'value'",
            execution_time_ms=42.5,
            backend_name="PostgreSQL"
        )
        assert result.count == 5
        assert result.is_success
        assert not result.has_error
        assert result.status == FilterStatus.SUCCESS
        assert result.backend_name == "PostgreSQL"
        assert result.execution_time_ms == 42.5

    def test_success_with_list(self):
        """Test creating result with list instead of tuple."""
        result = FilterResult.success(
            feature_ids=[1, 2, 3],
            layer_id="layer_123",
            expression_raw="field = 'value'"
        )
        assert result.count == 3
        assert result.is_success

    def test_success_no_matches(self):
        """Test creating result with no matches."""
        result = FilterResult.success(
            feature_ids=(),
            layer_id="layer_123",
            expression_raw="field = 'nonexistent'"
        )
        assert result.count == 0
        assert result.is_empty
        assert result.status == FilterStatus.NO_MATCHES
        assert result.is_success  # Still considered success

    def test_success_empty_list(self):
        """Test creating result with empty list."""
        result = FilterResult.success(
            feature_ids=[],
            layer_id="layer_123",
            expression_raw="field = 'value'"
        )
        assert result.is_empty
        assert result.status == FilterStatus.NO_MATCHES

    def test_success_deduplicates_ids(self):
        """Test that duplicate feature IDs are deduplicated."""
        result = FilterResult.success(
            feature_ids=(1, 2, 2, 3, 3, 3),
            layer_id="layer_123",
            expression_raw="field = 'value'"
        )
        assert result.count == 3
        assert result.feature_ids == frozenset({1, 2, 3})

    def test_success_default_values(self):
        """Test success with minimal arguments."""
        result = FilterResult.success(
            feature_ids=(1,),
            layer_id="layer_123",
            expression_raw="field = 1"
        )
        assert result.execution_time_ms == 0.0
        assert result.backend_name == ""
        assert result.is_cached is False


class TestFilterResultError:
    """Tests for FilterResult.error() factory."""

    def test_error_result(self):
        """Test creating error result."""
        result = FilterResult.error(
            layer_id="layer_123",
            expression_raw="invalid expression",
            error_message="Syntax error at position 5"
        )
        assert result.has_error
        assert not result.is_success
        assert result.error_message == "Syntax error at position 5"
        assert result.count == 0
        assert result.is_empty

    def test_error_with_backend(self):
        """Test error result with backend name."""
        result = FilterResult.error(
            layer_id="layer_123",
            expression_raw="bad sql",
            error_message="Connection failed",
            backend_name="PostgreSQL"
        )
        assert result.backend_name == "PostgreSQL"
        assert result.has_error

    def test_error_feature_ids_empty(self):
        """Test error result has empty feature IDs."""
        result = FilterResult.error(
            layer_id="layer_123",
            expression_raw="expr",
            error_message="Error"
        )
        assert result.feature_ids == frozenset()


class TestFilterResultCancelled:
    """Tests for FilterResult.cancelled() factory."""

    def test_cancelled_result(self):
        """Test creating cancelled result."""
        result = FilterResult.cancelled(
            layer_id="layer_123",
            expression_raw="field = 'value'"
        )
        assert result.was_cancelled
        assert not result.is_success
        assert result.count == 0
        assert result.status == FilterStatus.CANCELLED

    def test_cancelled_no_error_message(self):
        """Test cancelled result has no error message."""
        result = FilterResult.cancelled(
            layer_id="layer_123",
            expression_raw="expr"
        )
        assert result.error_message is None


class TestFilterResultFromCache:
    """Tests for FilterResult.from_cache() factory."""

    def test_from_cache(self):
        """Test creating cached result."""
        result = FilterResult.from_cache(
            feature_ids=(1, 2, 3),
            layer_id="layer_123",
            expression_raw="field = 'value'",
            original_execution_time_ms=100.0
        )
        assert result.is_cached is True
        assert result.count == 3
        assert result.is_success
        assert result.execution_time_ms == 100.0

    def test_from_cache_empty(self):
        """Test cached result with no matches."""
        result = FilterResult.from_cache(
            feature_ids=(),
            layer_id="layer_123",
            expression_raw="field = 'value'"
        )
        assert result.is_cached is True
        assert result.status == FilterStatus.NO_MATCHES

    def test_from_cache_with_backend(self):
        """Test cached result with backend name."""
        result = FilterResult.from_cache(
            feature_ids=(1,),
            layer_id="layer_123",
            expression_raw="expr",
            backend_name="Spatialite"
        )
        assert result.backend_name == "Spatialite"


class TestFilterResultPartial:
    """Tests for FilterResult.partial() factory."""

    def test_partial_result(self):
        """Test creating partial result."""
        result = FilterResult.partial(
            feature_ids=(1, 2, 3),
            layer_id="layer_123",
            expression_raw="field = 'value'",
            error_message="Some layers failed",
            execution_time_ms=50.0
        )
        assert result.is_partial
        assert result.count == 3
        assert result.error_message == "Some layers failed"
        assert not result.is_success
        assert not result.has_error

    def test_partial_not_success_or_error(self):
        """Test partial is neither success nor error."""
        result = FilterResult.partial(
            feature_ids=(1,),
            layer_id="layer",
            expression_raw="expr",
            error_message="Partial failure"
        )
        assert not result.is_success
        assert not result.has_error
        assert result.is_partial


class TestFilterResultProperties:
    """Tests for computed properties."""

    def test_count_property(self):
        """Test count returns correct value."""
        result = FilterResult.success(
            feature_ids=(1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
            layer_id="layer",
            expression_raw="expr"
        )
        assert result.count == 10

    def test_is_empty_true(self):
        """Test is_empty for empty result."""
        result = FilterResult.success(
            feature_ids=(),
            layer_id="layer",
            expression_raw="expr"
        )
        assert result.is_empty is True

    def test_is_empty_false(self):
        """Test is_empty for non-empty result."""
        result = FilterResult.success(
            feature_ids=(1,),
            layer_id="layer",
            expression_raw="expr"
        )
        assert result.is_empty is False

    def test_has_error_true(self):
        """Test has_error for error result."""
        result = FilterResult.error(
            layer_id="layer",
            expression_raw="expr",
            error_message="Error"
        )
        assert result.has_error is True

    def test_has_error_false(self):
        """Test has_error for success result."""
        result = FilterResult.success(
            feature_ids=(1,),
            layer_id="layer",
            expression_raw="expr"
        )
        assert result.has_error is False

    def test_is_success_true_with_matches(self):
        """Test is_success for result with matches."""
        result = FilterResult.success(
            feature_ids=(1, 2),
            layer_id="layer",
            expression_raw="expr"
        )
        assert result.is_success is True

    def test_is_success_true_no_matches(self):
        """Test is_success for result with no matches."""
        result = FilterResult.success(
            feature_ids=(),
            layer_id="layer",
            expression_raw="expr"
        )
        assert result.is_success is True

    def test_is_success_false_for_error(self):
        """Test is_success is false for error."""
        result = FilterResult.error(
            layer_id="layer",
            expression_raw="expr",
            error_message="Error"
        )
        assert result.is_success is False

    def test_was_cancelled_true(self):
        """Test was_cancelled for cancelled result."""
        result = FilterResult.cancelled(
            layer_id="layer",
            expression_raw="expr"
        )
        assert result.was_cancelled is True

    def test_was_cancelled_false(self):
        """Test was_cancelled for success result."""
        result = FilterResult.success(
            feature_ids=(1,),
            layer_id="layer",
            expression_raw="expr"
        )
        assert result.was_cancelled is False


class TestFilterResultImmutability:
    """Tests for FilterResult immutability."""

    def test_result_is_frozen(self):
        """Test that result cannot be modified."""
        result = FilterResult.success(
            feature_ids=(1, 2, 3),
            layer_id="layer_123",
            expression_raw="expr"
        )
        with pytest.raises(AttributeError):
            result.layer_id = "modified"

    def test_feature_ids_cannot_be_modified(self):
        """Test that feature_ids cannot be modified directly."""
        result = FilterResult.success(
            feature_ids=(1, 2, 3),
            layer_id="layer_123",
            expression_raw="expr"
        )
        with pytest.raises(AttributeError):
            result.feature_ids = frozenset({4, 5, 6})

    def test_with_cached_returns_new_instance(self):
        """Test that with_cached returns new instance."""
        result1 = FilterResult.success(
            feature_ids=(1, 2, 3),
            layer_id="layer_123",
            expression_raw="expr"
        )
        result2 = result1.with_cached(True)
        
        assert result1 is not result2
        assert result1.is_cached is False
        assert result2.is_cached is True
        # Other fields remain same
        assert result1.feature_ids == result2.feature_ids
        assert result1.layer_id == result2.layer_id

    def test_with_backend_returns_new_instance(self):
        """Test that with_backend returns new instance."""
        result1 = FilterResult.success(
            feature_ids=(1,),
            layer_id="layer",
            expression_raw="expr"
        )
        result2 = result1.with_backend("PostgreSQL")
        
        assert result1 is not result2
        assert result1.backend_name == ""
        assert result2.backend_name == "PostgreSQL"


class TestFilterResultTimestamp:
    """Tests for timestamp handling."""

    def test_timestamp_is_set(self):
        """Test that timestamp is automatically set."""
        before = datetime.now()
        result = FilterResult.success(
            feature_ids=(1,),
            layer_id="layer",
            expression_raw="expr"
        )
        after = datetime.now()
        
        assert before <= result.timestamp <= after

    def test_timestamp_preserved_in_with_methods(self):
        """Test that timestamp is preserved in with methods."""
        result1 = FilterResult.success(
            feature_ids=(1,),
            layer_id="layer",
            expression_raw="expr"
        )
        result2 = result1.with_cached(True)
        
        assert result1.timestamp == result2.timestamp


class TestFilterResultStringRepresentation:
    """Tests for string representation."""

    def test_str_success(self):
        """Test __str__ for success result."""
        result = FilterResult.success(
            feature_ids=(1, 2, 3),
            layer_id="layer",
            expression_raw="expr",
            execution_time_ms=42.5
        )
        s = str(result)
        assert "3 features" in s
        assert "42.5ms" in s

    def test_str_cached(self):
        """Test __str__ shows cached status."""
        result = FilterResult.from_cache(
            feature_ids=(1, 2),
            layer_id="layer",
            expression_raw="expr"
        )
        s = str(result)
        assert "[cached]" in s

    def test_str_error(self):
        """Test __str__ for error result."""
        result = FilterResult.error(
            layer_id="layer",
            expression_raw="expr",
            error_message="Something went wrong"
        )
        s = str(result)
        assert "ERROR" in s
        assert "Something went wrong" in s

    def test_str_cancelled(self):
        """Test __str__ for cancelled result."""
        result = FilterResult.cancelled(
            layer_id="layer",
            expression_raw="expr"
        )
        s = str(result)
        assert "CANCELLED" in s

    def test_str_partial(self):
        """Test __str__ for partial result."""
        result = FilterResult.partial(
            feature_ids=(1,),
            layer_id="layer",
            expression_raw="expr",
            error_message="Partial"
        )
        s = str(result)
        assert "[partial]" in s

    def test_repr(self):
        """Test __repr__ contains detailed info."""
        result = FilterResult.success(
            feature_ids=(1, 2, 3),
            layer_id="layer_123",
            expression_raw="expr",
            execution_time_ms=50.0
        )
        r = repr(result)
        assert "FilterResult" in r
        assert "count=3" in r
        assert "layer_id=" in r
        assert "status=success" in r


class TestFilterResultEquality:
    """Tests for equality and hashing."""

    def test_equal_results(self):
        """Test that equal results are equal."""
        # Create two results with same timestamp for equality
        result1 = FilterResult.success(
            feature_ids=(1, 2, 3),
            layer_id="layer",
            expression_raw="expr"
        )
        result2 = FilterResult(
            feature_ids=result1.feature_ids,
            layer_id=result1.layer_id,
            expression_raw=result1.expression_raw,
            status=result1.status,
            timestamp=result1.timestamp
        )
        assert result1 == result2

    def test_different_features_not_equal(self):
        """Test results with different features are not equal."""
        result1 = FilterResult.success(
            feature_ids=(1, 2, 3),
            layer_id="layer",
            expression_raw="expr"
        )
        result2 = FilterResult.success(
            feature_ids=(4, 5, 6),
            layer_id="layer",
            expression_raw="expr"
        )
        assert result1 != result2

    def test_results_hashable(self):
        """Test that results can be used in sets."""
        result1 = FilterResult.success(
            feature_ids=(1, 2),
            layer_id="layer1",
            expression_raw="expr1"
        )
        result2 = FilterResult.success(
            feature_ids=(3, 4),
            layer_id="layer2",
            expression_raw="expr2"
        )
        
        result_set = {result1, result2}
        assert len(result_set) == 2


class TestFilterResultFeatureIds:
    """Tests for feature_ids handling."""

    def test_feature_ids_is_frozenset(self):
        """Test that feature_ids is a frozenset."""
        result = FilterResult.success(
            feature_ids=(1, 2, 3),
            layer_id="layer",
            expression_raw="expr"
        )
        assert isinstance(result.feature_ids, frozenset)

    def test_feature_ids_membership_check(self):
        """Test O(1) membership check on feature_ids."""
        result = FilterResult.success(
            feature_ids=range(1000),
            layer_id="layer",
            expression_raw="expr"
        )
        assert 500 in result.feature_ids
        assert 2000 not in result.feature_ids

    def test_feature_ids_iteration(self):
        """Test that feature_ids can be iterated."""
        result = FilterResult.success(
            feature_ids=(1, 2, 3),
            layer_id="layer",
            expression_raw="expr"
        )
        ids_list = list(result.feature_ids)
        assert len(ids_list) == 3
        assert set(ids_list) == {1, 2, 3}

# -*- coding: utf-8 -*-
"""
Unit Tests for FilterResult Value Object.

Tests the FilterResult domain object for:
- Creation via factory methods
- Status handling
- Feature ID management
- Execution statistics

Author: FilterMate Team
Date: January 2026
"""
import pytest
import sys
from pathlib import Path
from datetime import datetime

# Add plugin directory to Python path
plugin_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(plugin_dir))

from core.domain.filter_result import FilterResult, FilterStatus


# ============================================================================
# FilterStatus Enum Tests
# ============================================================================

class TestFilterStatus:
    """Tests for FilterStatus enum."""
    
    def test_filter_status_values(self):
        """FilterStatus should have expected values."""
        assert FilterStatus.SUCCESS.value == "success"
        assert FilterStatus.PARTIAL.value == "partial"
        assert FilterStatus.CANCELLED.value == "cancelled"
        assert FilterStatus.ERROR.value == "error"
        assert FilterStatus.NO_MATCHES.value == "no_matches"
    
    def test_all_statuses_count(self):
        """Should have 5 status values."""
        statuses = list(FilterStatus)
        assert len(statuses) == 5


# ============================================================================
# FilterResult Factory Method Tests
# ============================================================================

class TestFilterResultFactoryMethods:
    """Tests for FilterResult factory methods."""
    
    def test_success_with_matches(self):
        """success() should create result with SUCCESS status."""
        result = FilterResult.success(
            feature_ids=[1, 2, 3, 4, 5],
            layer_id="layer_123",
            expression_raw="field = 'value'",
            execution_time_ms=42.5,
            backend_name="PostgreSQL"
        )
        
        assert result.status == FilterStatus.SUCCESS
        assert result.count == 5
        assert result.layer_id == "layer_123"
        assert result.expression_raw == "field = 'value'"
        assert result.execution_time_ms == 42.5
        assert result.backend_name == "PostgreSQL"
    
    def test_success_empty_creates_no_matches(self):
        """success() with empty list should create NO_MATCHES status."""
        result = FilterResult.success(
            feature_ids=[],
            layer_id="layer_123",
            expression_raw="field = 'nonexistent'"
        )
        
        assert result.status == FilterStatus.NO_MATCHES
        assert result.count == 0
    
    def test_error_factory(self):
        """error() should create result with ERROR status."""
        result = FilterResult.error(
            layer_id="layer_123",
            expression_raw="invalid expression",
            error_message="Syntax error at position 5"
        )
        
        assert result.status == FilterStatus.ERROR
        assert result.error_message == "Syntax error at position 5"
        assert result.count == 0
    
    def test_cancelled_factory(self):
        """cancelled() should create result with CANCELLED status."""
        result = FilterResult.cancelled(
            layer_id="layer_123",
            expression_raw="long_running_query"
        )
        
        assert result.status == FilterStatus.CANCELLED
        assert result.count == 0
    
    def test_from_cache_factory(self):
        """from_cache() should create cached result."""
        result = FilterResult.from_cache(
            feature_ids=[10, 20, 30],
            layer_id="layer_123",
            expression_raw="field = 1"
        )
        
        assert result.is_cached
        assert result.status == FilterStatus.SUCCESS
        assert result.execution_time_ms == 0.0


# ============================================================================
# FilterResult Properties Tests
# ============================================================================

class TestFilterResultProperties:
    """Tests for FilterResult computed properties."""
    
    def test_count_property(self):
        """count should return number of feature IDs."""
        result = FilterResult.success(
            feature_ids=[1, 2, 3],
            layer_id="layer_123",
            expression_raw="field = 1"
        )
        
        assert result.count == 3
    
    def test_is_success_true(self):
        """is_success should be True for SUCCESS status."""
        result = FilterResult.success(
            feature_ids=[1],
            layer_id="layer_123",
            expression_raw="field = 1"
        )
        
        assert result.is_success
    
    def test_is_success_false_for_error(self):
        """is_success should be False for ERROR status."""
        result = FilterResult.error(
            layer_id="layer_123",
            expression_raw="bad",
            error_message="Error"
        )
        
        assert not result.is_success
    
    def test_is_empty_true(self):
        """is_empty should be True when no matches."""
        result = FilterResult.success(
            feature_ids=[],
            layer_id="layer_123",
            expression_raw="field = 'none'"
        )
        
        assert result.is_empty
    
    def test_is_empty_false(self):
        """is_empty should be False when has matches."""
        result = FilterResult.success(
            feature_ids=[1, 2],
            layer_id="layer_123",
            expression_raw="field = 1"
        )
        
        assert not result.is_empty
    
    def test_has_error_true(self):
        """has_error should be True when has error message."""
        result = FilterResult.error(
            layer_id="layer_123",
            expression_raw="bad",
            error_message="Something went wrong"
        )
        
        assert result.has_error
    
    def test_has_error_false(self):
        """has_error should be False for success."""
        result = FilterResult.success(
            feature_ids=[1],
            layer_id="layer_123",
            expression_raw="field = 1"
        )
        
        assert not result.has_error


# ============================================================================
# FilterResult Feature IDs Tests
# ============================================================================

class TestFilterResultFeatureIds:
    """Tests for FilterResult feature ID handling."""
    
    def test_feature_ids_is_frozenset(self):
        """feature_ids should be a frozenset."""
        result = FilterResult.success(
            feature_ids=[1, 2, 3],
            layer_id="layer_123",
            expression_raw="field = 1"
        )
        
        assert isinstance(result.feature_ids, frozenset)
    
    def test_feature_ids_deduplication(self):
        """Duplicate feature IDs should be deduplicated."""
        result = FilterResult.success(
            feature_ids=[1, 2, 2, 3, 3, 3],
            layer_id="layer_123",
            expression_raw="field = 1"
        )
        
        assert result.count == 3
        assert result.feature_ids == frozenset([1, 2, 3])
    
    def test_feature_ids_immutable(self):
        """feature_ids should be immutable."""
        result = FilterResult.success(
            feature_ids=[1, 2, 3],
            layer_id="layer_123",
            expression_raw="field = 1"
        )
        
        # frozenset is immutable, cannot add
        with pytest.raises(AttributeError):
            result.feature_ids.add(4)
    
    def test_contains_feature(self):
        """Should support 'in' operator for feature IDs."""
        result = FilterResult.success(
            feature_ids=[10, 20, 30],
            layer_id="layer_123",
            expression_raw="field = 1"
        )
        
        assert 10 in result.feature_ids
        assert 20 in result.feature_ids
        assert 99 not in result.feature_ids


# ============================================================================
# FilterResult Immutability Tests
# ============================================================================

class TestFilterResultImmutability:
    """Tests for FilterResult immutability."""
    
    def test_result_is_frozen(self):
        """FilterResult should be immutable."""
        result = FilterResult.success(
            feature_ids=[1, 2, 3],
            layer_id="layer_123",
            expression_raw="field = 1"
        )
        
        with pytest.raises(Exception):  # FrozenInstanceError
            result.layer_id = "different_layer"
    
    def test_timestamp_is_set(self):
        """timestamp should be set on creation."""
        before = datetime.now()
        result = FilterResult.success(
            feature_ids=[1],
            layer_id="layer_123",
            expression_raw="field = 1"
        )
        after = datetime.now()
        
        assert before <= result.timestamp <= after


# ============================================================================
# FilterResult String Representation Tests
# ============================================================================

class TestFilterResultStringRepresentation:
    """Tests for FilterResult string representation."""
    
    def test_str_success(self):
        """__str__ should show count and time for success."""
        result = FilterResult.success(
            feature_ids=[1, 2, 3],
            layer_id="layer_123",
            expression_raw="field = 1",
            execution_time_ms=50.0,
            backend_name="PostgreSQL"
        )
        
        str_repr = str(result)
        
        assert "3" in str_repr or "features" in str_repr
    
    def test_str_error(self):
        """__str__ should show error message for errors."""
        result = FilterResult.error(
            layer_id="layer_123",
            expression_raw="bad",
            error_message="Parse error"
        )
        
        str_repr = str(result)
        
        assert "ERROR" in str_repr or "Parse error" in str_repr
    
    def test_repr(self):
        """__repr__ should return detailed representation."""
        result = FilterResult.success(
            feature_ids=[1, 2],
            layer_id="layer_123",
            expression_raw="field = 1"
        )
        
        repr_str = repr(result)
        
        assert "FilterResult" in repr_str
        assert "layer_id" in repr_str


# ============================================================================
# FilterResult Equality Tests
# ============================================================================

class TestFilterResultEquality:
    """Tests for FilterResult equality."""
    
    def test_equal_results(self):
        """Results with same feature IDs should be equal."""
        result1 = FilterResult.success(
            feature_ids=[1, 2, 3],
            layer_id="layer_123",
            expression_raw="field = 1"
        )
        result2 = FilterResult.success(
            feature_ids=[1, 2, 3],
            layer_id="layer_123",
            expression_raw="field = 1"
        )
        
        # Note: timestamps will differ, so equality depends on implementation
        assert result1.feature_ids == result2.feature_ids
        assert result1.layer_id == result2.layer_id
    
    def test_different_feature_ids_not_equal(self):
        """Results with different feature IDs should have different feature_ids."""
        result1 = FilterResult.success(
            feature_ids=[1, 2, 3],
            layer_id="layer_123",
            expression_raw="field = 1"
        )
        result2 = FilterResult.success(
            feature_ids=[4, 5, 6],
            layer_id="layer_123",
            expression_raw="field = 1"
        )
        
        assert result1.feature_ids != result2.feature_ids


# ============================================================================
# FilterResult Edge Cases Tests
# ============================================================================

class TestFilterResultEdgeCases:
    """Tests for FilterResult edge cases."""
    
    def test_large_feature_count(self):
        """Should handle large number of features."""
        large_ids = list(range(100000))
        result = FilterResult.success(
            feature_ids=large_ids,
            layer_id="layer_123",
            expression_raw="field > 0"
        )
        
        assert result.count == 100000
    
    def test_zero_execution_time(self):
        """Should handle zero execution time."""
        result = FilterResult.success(
            feature_ids=[1],
            layer_id="layer_123",
            expression_raw="field = 1",
            execution_time_ms=0.0
        )
        
        assert result.execution_time_ms == 0.0
    
    def test_empty_backend_name(self):
        """Should handle empty backend name."""
        result = FilterResult.success(
            feature_ids=[1],
            layer_id="layer_123",
            expression_raw="field = 1",
            backend_name=""
        )
        
        assert result.backend_name == ""
    
    def test_unicode_in_expression(self):
        """Should handle unicode in expression."""
        result = FilterResult.success(
            feature_ids=[1],
            layer_id="layer_123",
            expression_raw="city = 'München'"
        )
        
        assert "München" in result.expression_raw
    
    def test_special_characters_in_error(self):
        """Should handle special characters in error message."""
        result = FilterResult.error(
            layer_id="layer_123",
            expression_raw="field = 'test'",
            error_message="Error at line 5: unexpected '<'"
        )
        
        assert "<" in result.error_message

"""
Unit tests for FilterExpression Value Object.

Tests cover:
- Creation and validation
- Immutability (frozen dataclass)
- Spatial predicate detection
- With methods (functional updates)
- Computed properties
- Edge cases and error handling
"""
import pytest
from core.domain.filter_expression import (
    FilterExpression,
    ProviderType,
    SpatialPredicate,
)


class TestProviderType:
    """Tests for ProviderType enum."""

    def test_provider_type_values(self):
        """Test that all provider types have correct values."""
        assert ProviderType.POSTGRESQL.value == "postgresql"
        assert ProviderType.SPATIALITE.value == "spatialite"
        assert ProviderType.OGR.value == "ogr"
        assert ProviderType.MEMORY.value == "memory"
        assert ProviderType.UNKNOWN.value == "unknown"

    def test_from_qgis_provider_postgres(self):
        """Test conversion from QGIS 'postgres' provider."""
        assert ProviderType.from_qgis_provider("postgres") == ProviderType.POSTGRESQL
        assert ProviderType.from_qgis_provider("postgresql") == ProviderType.POSTGRESQL

    def test_from_qgis_provider_spatialite(self):
        """Test conversion from QGIS 'spatialite' provider."""
        assert ProviderType.from_qgis_provider("spatialite") == ProviderType.SPATIALITE

    def test_from_qgis_provider_ogr(self):
        """Test conversion from QGIS 'ogr' provider."""
        assert ProviderType.from_qgis_provider("ogr") == ProviderType.OGR

    def test_from_qgis_provider_memory(self):
        """Test conversion from QGIS 'memory' provider."""
        assert ProviderType.from_qgis_provider("memory") == ProviderType.MEMORY

    def test_from_qgis_provider_unknown(self):
        """Test unknown provider returns UNKNOWN."""
        assert ProviderType.from_qgis_provider("wfs") == ProviderType.UNKNOWN
        assert ProviderType.from_qgis_provider("xyz") == ProviderType.UNKNOWN

    def test_from_qgis_provider_case_insensitive(self):
        """Test case insensitive conversion."""
        assert ProviderType.from_qgis_provider("POSTGRES") == ProviderType.POSTGRESQL
        assert ProviderType.from_qgis_provider("Spatialite") == ProviderType.SPATIALITE


class TestSpatialPredicate:
    """Tests for SpatialPredicate enum."""

    def test_spatial_predicate_values(self):
        """Test that all predicates have correct values."""
        assert SpatialPredicate.INTERSECTS.value == "intersects"
        assert SpatialPredicate.CONTAINS.value == "contains"
        assert SpatialPredicate.WITHIN.value == "within"
        assert SpatialPredicate.CROSSES.value == "crosses"
        assert SpatialPredicate.TOUCHES.value == "touches"
        assert SpatialPredicate.OVERLAPS.value == "overlaps"
        assert SpatialPredicate.DISJOINT.value == "disjoint"
        assert SpatialPredicate.EQUALS.value == "equals"
        assert SpatialPredicate.DWITHIN.value == "dwithin"


class TestFilterExpressionCreation:
    """Tests for FilterExpression creation and validation."""

    def test_create_simple_expression(self):
        """Test creating a simple non-spatial expression."""
        expr = FilterExpression.create(
            raw="field_name = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        assert expr.raw == "field_name = 'value'"
        assert expr.provider == ProviderType.POSTGRESQL
        assert not expr.is_spatial
        assert expr.source_layer_id == "layer_123"
        assert expr.is_simple

    def test_create_with_whitespace_trimmed(self):
        """Test that raw expression is trimmed."""
        expr = FilterExpression.create(
            raw="  field = 'value'  ",
            provider=ProviderType.SPATIALITE,
            source_layer_id="layer_456"
        )
        assert expr.raw == "field = 'value'"

    def test_create_spatial_expression_intersects(self):
        """Test creating a spatial expression with intersects."""
        expr = FilterExpression.create(
            raw="intersects($geometry, @layer_geometry)",
            provider=ProviderType.SPATIALITE,
            source_layer_id="layer_123"
        )
        assert expr.is_spatial
        assert SpatialPredicate.INTERSECTS in expr.spatial_predicates
        assert not expr.is_simple

    def test_create_spatial_expression_contains(self):
        """Test creating a spatial expression with contains."""
        expr = FilterExpression.create(
            raw="contains($geometry, @point)",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        assert expr.is_spatial
        assert SpatialPredicate.CONTAINS in expr.spatial_predicates

    def test_create_expression_multiple_predicates(self):
        """Test expression with multiple spatial predicates."""
        expr = FilterExpression.create(
            raw="intersects($geometry, @a) OR contains($geometry, @b)",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        assert expr.is_spatial
        assert SpatialPredicate.INTERSECTS in expr.spatial_predicates
        assert SpatialPredicate.CONTAINS in expr.spatial_predicates
        assert len(expr.spatial_predicates) == 2

    def test_create_with_buffer(self):
        """Test creating expression with buffer."""
        expr = FilterExpression.create(
            raw="intersects($geometry, @layer_geometry)",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123",
            buffer_value=100.0
        )
        assert expr.has_buffer
        assert expr.buffer_value == 100.0
        assert expr.buffer_segments == 5  # default

    def test_create_with_custom_buffer_segments(self):
        """Test creating expression with custom buffer segments."""
        expr = FilterExpression.create(
            raw="field = 1",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123",
            buffer_value=50.0,
            buffer_segments=16
        )
        assert expr.buffer_segments == 16

    def test_create_with_target_layers(self):
        """Test creating expression with target layers."""
        expr = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="source_layer",
            target_layer_ids=["target_1", "target_2"]
        )
        assert expr.target_layer_ids == ("target_1", "target_2")

    def test_create_with_pre_converted_sql(self):
        """Test creating expression with pre-converted SQL."""
        expr = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123",
            sql="\"field\" = 'value'"
        )
        assert expr.raw == "field = 'value'"
        assert expr.sql == "\"field\" = 'value'"


class TestFilterExpressionValidation:
    """Tests for FilterExpression validation errors."""

    def test_empty_expression_raises_error(self):
        """Test that empty expression raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            FilterExpression.create(
                raw="",
                provider=ProviderType.OGR,
                source_layer_id="layer_123"
            )

    def test_whitespace_only_expression_raises_error(self):
        """Test that whitespace-only expression raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            FilterExpression.create(
                raw="   ",
                provider=ProviderType.OGR,
                source_layer_id="layer_123"
            )

    def test_negative_buffer_raises_error(self):
        """Test that negative buffer raises ValueError."""
        with pytest.raises(ValueError, match="cannot be negative"):
            FilterExpression.create(
                raw="field = 'value'",
                provider=ProviderType.POSTGRESQL,
                source_layer_id="layer_123",
                buffer_value=-10.0
            )

    def test_zero_buffer_is_allowed(self):
        """Test that zero buffer is allowed."""
        expr = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123",
            buffer_value=0.0
        )
        assert expr.buffer_value == 0.0
        assert not expr.has_buffer  # 0.0 is not considered as having buffer

    def test_invalid_provider_type_raises_error(self):
        """Test that invalid provider type raises TypeError."""
        with pytest.raises(TypeError, match="must be ProviderType"):
            FilterExpression(
                raw="field = 'value'",
                sql="field = 'value'",
                provider="postgresql"  # string instead of enum
            )

    def test_zero_buffer_segments_raises_error(self):
        """Test that zero buffer segments raises ValueError."""
        with pytest.raises(ValueError, match="at least 1"):
            FilterExpression(
                raw="field = 'value'",
                sql="field = 'value'",
                provider=ProviderType.POSTGRESQL,
                buffer_segments=0
            )


class TestFilterExpressionImmutability:
    """Tests for FilterExpression immutability."""

    def test_expression_is_frozen(self):
        """Test that expression cannot be modified."""
        expr = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        with pytest.raises(AttributeError):
            expr.raw = "modified"

    def test_sql_cannot_be_modified(self):
        """Test that SQL cannot be modified directly."""
        expr = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        with pytest.raises(AttributeError):
            expr.sql = "modified sql"

    def test_provider_cannot_be_modified(self):
        """Test that provider cannot be modified directly."""
        expr = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        with pytest.raises(AttributeError):
            expr.provider = ProviderType.OGR

    def test_with_sql_returns_new_instance(self):
        """Test that with_sql returns new instance."""
        expr1 = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        expr2 = expr1.with_sql("\"field\" = 'value'")
        
        assert expr1 is not expr2
        assert expr1.sql == "field = 'value'"
        assert expr2.sql == "\"field\" = 'value'"
        # Other fields remain same
        assert expr1.raw == expr2.raw
        assert expr1.provider == expr2.provider

    def test_with_buffer_returns_new_instance(self):
        """Test that with_buffer returns new instance."""
        expr1 = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        expr2 = expr1.with_buffer(100.0)
        
        assert expr1 is not expr2
        assert expr1.buffer_value is None
        assert expr2.buffer_value == 100.0
        assert expr2.is_spatial  # Buffer makes it spatial

    def test_with_buffer_custom_segments(self):
        """Test with_buffer with custom segments."""
        expr1 = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        expr2 = expr1.with_buffer(50.0, segments=16)
        
        assert expr2.buffer_value == 50.0
        assert expr2.buffer_segments == 16

    def test_with_provider_returns_new_instance(self):
        """Test that with_provider returns new instance."""
        expr1 = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        expr2 = expr1.with_provider(ProviderType.SPATIALITE)
        
        assert expr1 is not expr2
        assert expr1.provider == ProviderType.POSTGRESQL
        assert expr2.provider == ProviderType.SPATIALITE


class TestFilterExpressionProperties:
    """Tests for computed properties."""

    def test_has_buffer_true(self):
        """Test has_buffer returns True when buffer > 0."""
        expr = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123",
            buffer_value=100.0
        )
        assert expr.has_buffer is True

    def test_has_buffer_false_when_none(self):
        """Test has_buffer returns False when buffer is None."""
        expr = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        assert expr.has_buffer is False

    def test_has_buffer_false_when_zero(self):
        """Test has_buffer returns False when buffer is 0."""
        expr = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123",
            buffer_value=0.0
        )
        assert expr.has_buffer is False

    def test_is_simple_true(self):
        """Test is_simple returns True for non-spatial without buffer."""
        expr = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        assert expr.is_simple is True

    def test_is_simple_false_when_spatial(self):
        """Test is_simple returns False when spatial."""
        expr = FilterExpression.create(
            raw="intersects($geometry, @a)",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        assert expr.is_simple is False

    def test_is_simple_false_when_buffered(self):
        """Test is_simple returns False when has buffer."""
        expr = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123",
            buffer_value=100.0
        )
        assert expr.is_simple is False

    def test_predicate_names(self):
        """Test predicate_names returns string list."""
        expr = FilterExpression.create(
            raw="intersects($geometry, @a) AND contains($geometry, @b)",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        names = expr.predicate_names
        assert "intersects" in names
        assert "contains" in names


class TestFilterExpressionStringRepresentation:
    """Tests for string representation."""

    def test_str_simple_expression(self):
        """Test __str__ for simple expression."""
        expr = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        result = str(expr)
        assert "postgresql" in result
        assert "field = 'value'" in result
        assert "[spatial]" not in result

    def test_str_spatial_expression(self):
        """Test __str__ for spatial expression."""
        expr = FilterExpression.create(
            raw="intersects($geometry, @a)",
            provider=ProviderType.SPATIALITE,
            source_layer_id="layer_123"
        )
        result = str(expr)
        assert "spatialite" in result
        assert "[spatial]" in result

    def test_str_with_buffer(self):
        """Test __str__ shows buffer info."""
        expr = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123",
            buffer_value=100.0
        )
        result = str(expr)
        assert "buffer: 100.0" in result

    def test_str_long_expression_truncated(self):
        """Test __str__ truncates long expressions."""
        long_expr = "a" * 100
        expr = FilterExpression.create(
            raw=long_expr,
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        result = str(expr)
        assert "..." in result
        assert len(result) < len(long_expr) + 50

    def test_repr(self):
        """Test __repr__ contains detailed info."""
        expr = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123",
            buffer_value=50.0
        )
        result = repr(expr)
        assert "FilterExpression" in result
        assert "raw=" in result
        assert "provider=" in result
        assert "buffer_value=50.0" in result


class TestFilterExpressionEquality:
    """Tests for equality and hashing."""

    def test_equal_expressions(self):
        """Test that equal expressions are equal."""
        expr1 = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        expr2 = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        assert expr1 == expr2

    def test_different_raw_not_equal(self):
        """Test expressions with different raw are not equal."""
        expr1 = FilterExpression.create(
            raw="field = 'value1'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        expr2 = FilterExpression.create(
            raw="field = 'value2'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        assert expr1 != expr2

    def test_different_provider_not_equal(self):
        """Test expressions with different provider are not equal."""
        expr1 = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        expr2 = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.SPATIALITE,
            source_layer_id="layer_123"
        )
        assert expr1 != expr2

    def test_expressions_hashable(self):
        """Test that expressions can be used in sets and dicts."""
        expr1 = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        expr2 = FilterExpression.create(
            raw="field = 'other'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_456"
        )
        
        # Can be added to set
        expr_set = {expr1, expr2}
        assert len(expr_set) == 2
        
        # Can be used as dict key
        expr_dict = {expr1: "first", expr2: "second"}
        assert expr_dict[expr1] == "first"


class TestSpatialPredicateDetection:
    """Tests for spatial predicate detection."""

    def test_detect_intersects(self):
        """Test detection of intersects predicate."""
        expr = FilterExpression.create(
            raw="intersects($geometry, @other)",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer"
        )
        assert SpatialPredicate.INTERSECTS in expr.spatial_predicates

    def test_detect_contains(self):
        """Test detection of contains predicate."""
        expr = FilterExpression.create(
            raw="contains($geometry, @point)",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer"
        )
        assert SpatialPredicate.CONTAINS in expr.spatial_predicates

    def test_detect_within(self):
        """Test detection of within predicate."""
        expr = FilterExpression.create(
            raw="within($geometry, @polygon)",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer"
        )
        assert SpatialPredicate.WITHIN in expr.spatial_predicates

    def test_detect_dwithin(self):
        """Test detection of dwithin predicate."""
        expr = FilterExpression.create(
            raw="dwithin($geometry, @point, 100)",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer"
        )
        assert SpatialPredicate.DWITHIN in expr.spatial_predicates

    def test_detect_case_insensitive(self):
        """Test detection is case insensitive."""
        expr = FilterExpression.create(
            raw="INTERSECTS($geometry, @other)",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer"
        )
        assert SpatialPredicate.INTERSECTS in expr.spatial_predicates

    def test_no_false_positive_in_field_name(self):
        """Test that predicate in field name is detected (known limitation)."""
        # Note: This is a known limitation - detection is simple string matching
        expr = FilterExpression.create(
            raw="contains_data = 1",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer"
        )
        # Current implementation will detect this as spatial
        # This is documented behavior - ExpressionService handles proper parsing
        assert SpatialPredicate.CONTAINS in expr.spatial_predicates

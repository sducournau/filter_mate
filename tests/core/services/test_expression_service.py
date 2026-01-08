"""
Tests for ExpressionService.

Part of Phase 3 Core Domain Layer implementation.
"""
import pytest
from core.services.expression_service import (
    ExpressionService, ValidationResult, ParsedExpression
)
from core.domain.filter_expression import ProviderType, SpatialPredicate


class TestExpressionValidation:
    """Tests for expression validation."""

    @pytest.fixture
    def service(self):
        return ExpressionService()

    def test_valid_simple_expression(self, service):
        """Test validation of simple expression."""
        result = service.validate("\"field\" = 'value'")
        assert result.is_valid
        assert not result.warnings

    def test_valid_complex_expression(self, service):
        """Test validation of complex expression."""
        result = service.validate(
            "\"name\" = 'test' AND \"count\" > 5 OR \"status\" IN ('A', 'B')"
        )
        assert result.is_valid

    def test_empty_expression_invalid(self, service):
        """Test empty expression is invalid."""
        result = service.validate("")
        assert not result.is_valid
        assert "empty" in result.error_message.lower()

    def test_whitespace_only_expression_invalid(self, service):
        """Test whitespace-only expression is invalid."""
        result = service.validate("   ")
        assert not result.is_valid

    def test_unbalanced_parentheses_open(self, service):
        """Test unbalanced parentheses (missing close)."""
        result = service.validate("((field = 'value')")
        assert not result.is_valid
        assert "parentheses" in result.error_message.lower()

    def test_unbalanced_parentheses_close(self, service):
        """Test unbalanced parentheses (extra close)."""
        result = service.validate("(field = 'value'))")
        assert not result.is_valid
        assert "parentheses" in result.error_message.lower()

    def test_unbalanced_double_quotes(self, service):
        """Test unbalanced double quotes."""
        result = service.validate("\"field = 'value'")
        assert not result.is_valid
        assert "quotes" in result.error_message.lower()

    def test_unbalanced_single_quotes(self, service):
        """Test unbalanced single quotes."""
        result = service.validate("\"field\" = 'value")
        assert not result.is_valid
        assert "quotes" in result.error_message.lower()

    def test_escaped_quotes_valid(self, service):
        """Test that escaped quotes are handled."""
        result = service.validate("\"field\" = 'it''s valid'")
        assert result.is_valid

    def test_warning_for_double_equals(self, service):
        """Test warning for using == instead of =."""
        result = service.validate("\"field\" == 'value'")
        assert result.is_valid  # Still valid, just a warning
        assert any("==" in w for w in result.warnings)

    def test_warning_for_not_equals(self, service):
        """Test warning for using != instead of <>."""
        result = service.validate("\"field\" != 'value'")
        assert result.is_valid
        assert any("!=" in w for w in result.warnings)

    def test_validation_result_bool_conversion(self, service):
        """Test ValidationResult works in boolean context."""
        valid = service.validate("\"field\" = 1")
        invalid = service.validate("")
        
        assert bool(valid)
        assert not bool(invalid)


class TestExpressionParsing:
    """Tests for expression parsing."""

    @pytest.fixture
    def service(self):
        return ExpressionService()

    def test_extract_single_field(self, service):
        """Test extracting single field."""
        parsed = service.parse("\"name\" = 'test'")
        assert "name" in parsed.fields
        assert len(parsed.fields) == 1

    def test_extract_multiple_fields(self, service):
        """Test extracting multiple fields."""
        parsed = service.parse("\"name\" = 'test' AND \"count\" > 5")
        assert "name" in parsed.fields
        assert "count" in parsed.fields
        assert len(parsed.fields) == 2

    def test_detect_spatial_predicate_intersects(self, service):
        """Test detecting intersects predicate."""
        parsed = service.parse("intersects($geometry, @layer_geom)")
        assert parsed.is_spatial
        assert SpatialPredicate.INTERSECTS in parsed.spatial_predicates

    def test_detect_spatial_predicate_contains(self, service):
        """Test detecting contains predicate."""
        parsed = service.parse("contains($geometry, @other)")
        assert SpatialPredicate.CONTAINS in parsed.spatial_predicates

    def test_detect_multiple_spatial_predicates(self, service):
        """Test detecting multiple predicates."""
        parsed = service.parse(
            "intersects($geometry, @g1) OR contains($geometry, @g2)"
        )
        assert len(parsed.spatial_predicates) == 2
        assert SpatialPredicate.INTERSECTS in parsed.spatial_predicates
        assert SpatialPredicate.CONTAINS in parsed.spatial_predicates

    def test_detect_geometry_reference(self, service):
        """Test detecting $geometry reference."""
        parsed = service.parse("$geometry")
        assert parsed.has_geometry_reference

    def test_detect_layer_reference(self, service):
        """Test detecting layer reference."""
        parsed = service.parse("@layer_property('layer', 'name')")
        assert parsed.has_layer_reference

    def test_extract_operators(self, service):
        """Test extracting operators."""
        parsed = service.parse("\"a\" = 1 AND \"b\" = 2 OR \"c\" = 3")
        assert "AND" in parsed.operators
        assert "OR" in parsed.operators

    def test_complexity_simple(self, service):
        """Test complexity for simple expression."""
        simple = service.parse("\"field\" = 'value'")
        assert simple.estimated_complexity <= 2
        assert simple.is_simple

    def test_complexity_complex(self, service):
        """Test complexity for complex expression."""
        complex_expr = service.parse(
            "intersects($geometry, @g) AND contains($geometry, @h) "
            "OR within($geometry, @i) AND \"field\" = 1"
        )
        assert complex_expr.estimated_complexity >= 5
        assert complex_expr.is_complex

    def test_is_spatial_with_predicate(self, service):
        """Test is_spatial for expression with predicate."""
        parsed = service.parse("intersects($geometry, @g)")
        assert parsed.is_spatial

    def test_is_spatial_with_geometry_only(self, service):
        """Test is_spatial for expression with geometry ref only."""
        parsed = service.parse("$geometry IS NOT NULL")
        assert parsed.is_spatial

    def test_not_spatial_for_attribute_only(self, service):
        """Test is_spatial false for attribute-only expression."""
        parsed = service.parse("\"name\" = 'test'")
        assert not parsed.is_spatial


class TestExpressionConversion:
    """Tests for SQL conversion."""

    @pytest.fixture
    def service(self):
        return ExpressionService()

    def test_postgis_function_conversion(self, service):
        """Test conversion of spatial functions to PostGIS."""
        sql = service.to_sql(
            "intersects($geometry, @layer)",
            ProviderType.POSTGRESQL
        )
        assert "ST_Intersects" in sql
        assert "intersects" not in sql.lower() or "ST_Intersects" in sql

    def test_postgis_geometry_replacement(self, service):
        """Test $geometry replacement in PostGIS."""
        sql = service.to_sql(
            "$geometry IS NOT NULL",
            ProviderType.POSTGRESQL,
            geometry_column="geom"
        )
        assert '"geom"' in sql
        assert "$geometry" not in sql

    def test_spatialite_function_conversion(self, service):
        """Test conversion to Spatialite."""
        sql = service.to_sql(
            "intersects($geometry, @layer)",
            ProviderType.SPATIALITE
        )
        assert "Intersects" in sql
        assert "ST_" not in sql

    def test_spatialite_length_function(self, service):
        """Test Spatialite uses GLength instead of Length."""
        sql = service.to_sql(
            "length($geometry)",
            ProviderType.SPATIALITE
        )
        assert "GLength" in sql

    def test_ogr_passthrough(self, service):
        """Test OGR expressions pass through unchanged."""
        original = "\"field\" = 'value'"
        sql = service.to_sql(original, ProviderType.OGR)
        assert sql == original

    def test_memory_passthrough(self, service):
        """Test memory expressions pass through unchanged."""
        original = "\"field\" = 'value'"
        sql = service.to_sql(original, ProviderType.MEMORY)
        assert sql == original

    def test_postgis_boolean_handling(self, service):
        """Test PostGIS keeps TRUE/FALSE."""
        sql = service.to_sql("\"active\" = TRUE", ProviderType.POSTGRESQL)
        assert "TRUE" in sql

    def test_spatialite_boolean_handling(self, service):
        """Test Spatialite converts TRUE/FALSE to 1/0."""
        sql = service.to_sql("\"active\" = TRUE", ProviderType.SPATIALITE)
        assert "1" in sql


class TestExpressionUtilities:
    """Tests for expression utility methods."""

    @pytest.fixture
    def service(self):
        return ExpressionService()

    def test_extract_fields(self, service):
        """Test standalone field extraction."""
        fields = service.extract_fields("\"a\" = 1 AND \"b\" = 2")
        assert fields == {"a", "b"}

    def test_is_spatial_true(self, service):
        """Test is_spatial detection."""
        assert service.is_spatial("intersects($geometry, @g)")
        assert service.is_spatial("$geometry IS NOT NULL")

    def test_is_spatial_false(self, service):
        """Test is_spatial for non-spatial."""
        assert not service.is_spatial("\"name\" = 'test'")

    def test_get_spatial_predicates(self, service):
        """Test getting spatial predicates."""
        predicates = service.get_spatial_predicates(
            "intersects($g, @a) AND contains($g, @b)"
        )
        assert SpatialPredicate.INTERSECTS in predicates
        assert SpatialPredicate.CONTAINS in predicates

    def test_add_buffer_postgis(self, service):
        """Test adding buffer for PostGIS."""
        result = service.add_buffer(
            "intersects($geometry, @g)",
            buffer_value=100.0,
            provider=ProviderType.POSTGRESQL
        )
        assert "ST_Buffer" in result
        assert "100.0" in result

    def test_add_buffer_spatialite(self, service):
        """Test adding buffer for Spatialite."""
        result = service.add_buffer(
            "intersects($geometry, @g)",
            buffer_value=50.0,
            provider=ProviderType.SPATIALITE
        )
        assert "Buffer" in result
        assert "50.0" in result

    def test_normalize_whitespace(self, service):
        """Test expression normalization."""
        result = service.normalize("  field   =   1  ")
        assert result == "field = 1"

    def test_normalize_operators(self, service):
        """Test operator case normalization."""
        result = service.normalize("field = 1 and other = 2")
        assert "AND" in result

    def test_combine_expressions_single(self, service):
        """Test combining single expression."""
        result = service.combine_expressions(["field = 1"])
        assert result == "field = 1"

    def test_combine_expressions_multiple(self, service):
        """Test combining multiple expressions."""
        result = service.combine_expressions(
            ["field1 = 1", "field2 = 2"],
            operator="AND"
        )
        assert "(field1 = 1)" in result
        assert "(field2 = 2)" in result
        assert "AND" in result

    def test_combine_expressions_or(self, service):
        """Test combining with OR operator."""
        result = service.combine_expressions(
            ["a = 1", "b = 2"],
            operator="OR"
        )
        assert "OR" in result

    def test_combine_expressions_empty(self, service):
        """Test combining empty list."""
        result = service.combine_expressions([])
        assert result == ""

    def test_negate_expression(self, service):
        """Test negating expression."""
        result = service.negate("field = 1")
        assert result == "NOT (field = 1)"

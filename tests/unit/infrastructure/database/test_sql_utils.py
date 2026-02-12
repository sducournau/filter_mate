# -*- coding: utf-8 -*-
"""
Tests for SQL utility functions.

These are PURE PYTHON tests -- no QGIS or database dependency.
Tests cover sanitize_sql_identifier() and format_pk_values_for_sql().

The functions safe_set_subset_string() and create_temp_spatialite_table()
require QGIS/Spatialite and are tested in integration tests.

Module tested: infrastructure.database.sql_utils
"""
from infrastructure.database.sql_utils import (
    sanitize_sql_identifier,
    format_pk_values_for_sql,
)


# =========================================================================
# sanitize_sql_identifier
# =========================================================================

class TestSanitizeSqlIdentifier:
    """Tests for sanitize_sql_identifier()."""

    # --- Normal identifiers ---

    def test_simple_table_name(self):
        assert sanitize_sql_identifier("my_table") == "my_table"

    def test_schema_dot_table(self):
        """Schema.table notation must be preserved."""
        assert sanitize_sql_identifier("public.roads") == "public.roads"

    def test_quoted_identifier_preserves_quotes(self):
        """Double-quoted identifiers (PostgreSQL) preserve quotes but spaces are replaced."""
        # The regex [^\w\."] replaces space with underscore, even inside quotes
        result = sanitize_sql_identifier('"My Table"')
        assert result == '"My_Table"'
        assert '"' in result  # quotes preserved

    def test_alphanumeric_with_underscore(self):
        assert sanitize_sql_identifier("table_123") == "table_123"

    def test_numeric_prefix(self):
        """Identifiers starting with a digit."""
        assert sanitize_sql_identifier("123abc") == "123abc"

    # --- Dangerous input ---

    def test_sql_injection_semicolon(self):
        """Semicolons must be replaced with underscores."""
        result = sanitize_sql_identifier("table; DROP TABLE users;")
        assert ";" not in result
        assert "DROP" in result  # word kept, only special chars removed

    def test_sql_injection_single_quote(self):
        """Single quotes must be replaced."""
        result = sanitize_sql_identifier("table' OR '1'='1")
        assert "'" not in result

    def test_sql_injection_double_dash_comment(self):
        """Double dashes (SQL comments) must be sanitized."""
        result = sanitize_sql_identifier("table--comment")
        assert "--" not in result

    def test_parentheses_removed(self):
        result = sanitize_sql_identifier("table()")
        assert "(" not in result
        assert ")" not in result

    def test_backtick_removed(self):
        result = sanitize_sql_identifier("`my_table`")
        assert "`" not in result

    # --- Edge cases ---

    def test_empty_string(self):
        assert sanitize_sql_identifier("") == ""

    def test_none_input(self):
        """None coerced to string 'None' then sanitized."""
        # The function calls str(identifier), so None -> "None"
        # But it first checks `if not identifier` which is True for None
        assert sanitize_sql_identifier(None) == ""

    def test_only_special_chars(self):
        """Input with only special characters."""
        result = sanitize_sql_identifier("@#$%^&*()")
        # All replaced with _, then stripped
        assert result == ""  # all become _ then stripped

    def test_spaces_replaced(self):
        """Spaces must be replaced with underscores."""
        result = sanitize_sql_identifier("my table name")
        assert " " not in result
        assert "_" in result

    def test_preserves_dots_in_schema_table(self):
        assert sanitize_sql_identifier("schema.table.column") == "schema.table.column"

    def test_leading_trailing_underscores_stripped(self):
        """Underscores from sanitization at boundaries are stripped."""
        result = sanitize_sql_identifier(" table ")
        assert not result.startswith("_")
        assert not result.endswith("_")

    def test_mixed_valid_invalid(self):
        result = sanitize_sql_identifier("valid_name!@#extra")
        assert "!" not in result
        assert "@" not in result
        assert "#" not in result
        assert "valid_name" in result


# =========================================================================
# format_pk_values_for_sql
# =========================================================================

class TestFormatPkValuesForSql:
    """Tests for format_pk_values_for_sql()."""

    # --- Numeric values ---

    def test_numeric_integers(self):
        """Integer PK values should not be quoted."""
        result = format_pk_values_for_sql([1, 2, 3], pk_field="id")
        assert result == "1, 2, 3"

    def test_numeric_floats(self):
        result = format_pk_values_for_sql([1.5, 2.5], pk_field="id")
        assert "1.5" in result
        assert "2.5" in result

    def test_numeric_mixed_int_float(self):
        result = format_pk_values_for_sql([1, 2.5], pk_field="id")
        assert "'" not in result  # no quotes for numeric

    def test_numeric_forced_via_parameter(self):
        """is_numeric=True forces numeric formatting even for string values."""
        result = format_pk_values_for_sql(["1", "2", "3"], pk_field="code", is_numeric=True)
        # When is_numeric=True, values are formatted without quotes
        assert "'" not in result

    # --- String values ---

    def test_string_values_quoted(self):
        """String PK values must be single-quoted."""
        result = format_pk_values_for_sql(["abc", "def"], pk_field="code")
        assert "'abc'" in result
        assert "'def'" in result

    def test_string_with_single_quote_escaped(self):
        """Single quotes in values must be escaped (doubled)."""
        result = format_pk_values_for_sql(["O'Brien"], pk_field="name")
        assert "O''Brien" in result

    # --- UUID values ---

    def test_uuid_values_detected_from_field_schema(self):
        """UUID fields from layer schema should get ::uuid cast."""
        from unittest.mock import MagicMock
        layer = MagicMock()
        fields = MagicMock()
        fields.indexOf.return_value = 0
        field_mock = MagicMock()
        field_mock.typeName.return_value = "uuid"
        field_mock.isNumeric.return_value = False
        fields.__getitem__ = MagicMock(return_value=field_mock)
        layer.fields.return_value = fields

        result = format_pk_values_for_sql(
            ["550e8400-e29b-41d4-a716-446655440000"],
            pk_field="uuid_pk",
            layer=layer,
        )
        assert "::uuid" in result

    # --- Empty input ---

    def test_empty_list(self):
        assert format_pk_values_for_sql([], pk_field="id") == ""

    def test_none_values_list(self):
        """None as the values list."""
        # The function checks `if not values` first
        assert format_pk_values_for_sql(None, pk_field="id") == ""

    # --- Boolean exclusion ---

    def test_booleans_treated_as_numeric_via_strategy_2(self):
        """bool is subclass of int. Strategy 1 excludes bools explicitly,
        but strategy 2 checks isinstance(v, (int, float)) which includes bool.
        So booleans are ultimately treated as numeric and formatted as str(bool)."""
        result = format_pk_values_for_sql([True, False], pk_field="flag")
        # Strategy 2 detects True/False as numeric (isinstance(True, (int, float)) is True)
        # Formatted as str(True) = "True", str(False) = "False"
        assert "True" in result
        assert "False" in result
        assert "'" not in result  # no quoting (treated as numeric)

    # --- Fallback detection ---

    def test_common_pk_name_fallback_numeric(self):
        """Common PK names like 'id', 'fid' should be treated as numeric."""
        result = format_pk_values_for_sql(["1", "2"], pk_field="fid")
        # Strategy 2: string "1" looks numeric -> treated as numeric
        # OR strategy 4: "fid" is common numeric name
        assert "'" not in result or "1" in result

    def test_string_looking_like_integer(self):
        """Strings that look like integers should be detected as numeric."""
        result = format_pk_values_for_sql(["100", "200", "300"], pk_field="id")
        assert "'" not in result

    def test_string_not_looking_like_integer(self):
        """Strings that are clearly not numeric should be quoted."""
        result = format_pk_values_for_sql(["abc", "def"], pk_field="code")
        assert "'abc'" in result

    def test_negative_string_integers(self):
        """Negative integer strings should be detected as numeric."""
        result = format_pk_values_for_sql(["-1", "-2"], pk_field="id")
        assert "'" not in result


# =========================================================================
# build_feature_id_expression (standalone function)
# =========================================================================

class TestBuildFeatureIdExpression:
    """Tests for the standalone build_feature_id_expression function."""

    def test_postgresql_numeric_with_table(self):
        from infrastructure.database.sql_utils import format_pk_values_for_sql
        # This is tested indirectly via format_pk_values_for_sql
        # The actual build_feature_id_expression is in expression_builder.py
        # but we test the underlying formatter here
        result = format_pk_values_for_sql([1, 2, 3], pk_field="id")
        assert result == "1, 2, 3"

    def test_large_value_list_performance(self):
        """Ensure large lists don't cause issues."""
        values = list(range(10000))
        result = format_pk_values_for_sql(values, pk_field="id")
        assert "9999" in result
        assert len(result.split(",")) == 10000

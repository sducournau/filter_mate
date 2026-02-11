# -*- coding: utf-8 -*-
"""
Tests for expression builder functions.

Tests cover the standalone functions in core/filter/expression_builder.py:
    - build_feature_id_expression()
    - build_combined_filter_expression()

The ExpressionBuilder class methods that require QgsVectorLayer and backend
objects are tested in integration tests.

Module tested: core.filter.expression_builder
"""
import pytest

from core.filter.expression_builder import (
    build_feature_id_expression,
    build_combined_filter_expression,
)


# =========================================================================
# build_feature_id_expression
# =========================================================================

class TestBuildFeatureIdExpression:
    """Tests for build_feature_id_expression()."""

    # --- PostgreSQL provider ---

    def test_postgresql_numeric_with_table(self):
        result = build_feature_id_expression(
            features_ids=["1", "2", "3"],
            primary_key_name="id",
            table_name="roads",
            provider_type="postgresql",
            is_numeric=True,
        )
        assert result == '"roads"."id" IN (1, 2, 3)'

    def test_postgresql_numeric_without_table(self):
        result = build_feature_id_expression(
            features_ids=["10", "20"],
            primary_key_name="gid",
            table_name=None,
            provider_type="postgresql",
            is_numeric=True,
        )
        assert result == '"gid" IN (10, 20)'

    def test_postgresql_text_with_table(self):
        result = build_feature_id_expression(
            features_ids=["abc", "def"],
            primary_key_name="code",
            table_name="regions",
            provider_type="postgresql",
            is_numeric=False,
        )
        assert '"regions"."code" IN' in result
        assert "'abc'" in result
        assert "'def'" in result

    def test_postgresql_text_without_table(self):
        result = build_feature_id_expression(
            features_ids=["x", "y"],
            primary_key_name="code",
            table_name=None,
            provider_type="postgresql",
            is_numeric=False,
        )
        assert '"code" IN' in result

    # --- OGR provider ---

    def test_ogr_numeric_with_fid(self):
        """OGR provider with 'fid' should use unquoted fid."""
        result = build_feature_id_expression(
            features_ids=["1", "2"],
            primary_key_name="fid",
            table_name=None,
            provider_type="ogr",
            is_numeric=True,
        )
        assert result == "fid IN (1, 2)"
        assert '"fid"' not in result  # unquoted for OGR

    def test_ogr_numeric_with_custom_pk(self):
        """OGR with non-fid PK should be quoted."""
        result = build_feature_id_expression(
            features_ids=["1", "2"],
            primary_key_name="objectid",
            table_name=None,
            provider_type="ogr",
            is_numeric=True,
        )
        assert '"objectid" IN (1, 2)' == result

    def test_ogr_text_values(self):
        result = build_feature_id_expression(
            features_ids=["abc", "def"],
            primary_key_name="code",
            table_name=None,
            provider_type="ogr",
            is_numeric=False,
        )
        assert "'abc'" in result
        assert "'def'" in result

    # --- SpatiaLite provider ---

    def test_spatialite_numeric_with_fid(self):
        result = build_feature_id_expression(
            features_ids=["5", "10"],
            primary_key_name="fid",
            table_name=None,
            provider_type="spatialite",
            is_numeric=True,
        )
        assert result == "fid IN (5, 10)"
        assert '"fid"' not in result  # unquoted for spatialite

    def test_spatialite_with_quoted_pk(self):
        result = build_feature_id_expression(
            features_ids=["1"],
            primary_key_name="pk_col",
            table_name=None,
            provider_type="spatialite",
            is_numeric=True,
        )
        assert '"pk_col" IN (1)' == result

    # --- Empty input ---

    def test_empty_feature_ids(self):
        result = build_feature_id_expression(
            features_ids=[],
            primary_key_name="id",
            table_name="t",
            provider_type="postgresql",
        )
        assert result == ""

    # --- Single value ---

    def test_single_value(self):
        result = build_feature_id_expression(
            features_ids=["42"],
            primary_key_name="id",
            table_name="t",
            provider_type="postgresql",
            is_numeric=True,
        )
        assert result == '"t"."id" IN (42)'


# =========================================================================
# build_combined_filter_expression
# =========================================================================

class TestBuildCombinedFilterExpression:
    """Tests for build_combined_filter_expression()."""

    # --- No old subset ---

    def test_no_old_subset_returns_new(self):
        result = build_combined_filter_expression(
            new_expression="population > 10000",
            old_subset=None,
            combine_operator="AND",
        )
        assert result == "population > 10000"

    def test_empty_old_subset_returns_new(self):
        result = build_combined_filter_expression(
            new_expression="population > 10000",
            old_subset="",
            combine_operator="AND",
        )
        assert result == "population > 10000"

    # --- No combine operator ---

    def test_no_combine_operator_returns_new(self):
        result = build_combined_filter_expression(
            new_expression="population > 10000",
            old_subset="type = 'city'",
            combine_operator=None,
        )
        assert result == "population > 10000"

    # --- AND combination ---

    def test_and_combination_simple(self):
        result = build_combined_filter_expression(
            new_expression="population > 10000",
            old_subset="type = 'city'",
            combine_operator="AND",
        )
        assert "AND" in result
        assert "population > 10000" in result
        assert "type = 'city'" in result

    # --- OR combination ---

    def test_or_combination_simple(self):
        result = build_combined_filter_expression(
            new_expression="population > 10000",
            old_subset="type = 'city'",
            combine_operator="OR",
        )
        assert "OR" in result
        assert "population > 10000" in result
        assert "type = 'city'" in result

    # --- WHERE clause handling ---

    def test_old_subset_with_where_clause(self):
        """Old subset containing WHERE should be handled properly."""
        result = build_combined_filter_expression(
            new_expression="population > 5000",
            old_subset='SELECT * FROM table WHERE type = \'city\'',
            combine_operator="AND",
        )
        assert "AND" in result
        assert "population > 5000" in result

    def test_new_expression_with_where_prefix_stripped(self):
        """If new_expression starts with 'WHERE', it should be stripped."""
        result = build_combined_filter_expression(
            new_expression="WHERE population > 5000",
            old_subset="SELECT * FROM t WHERE type = 'city'",
            combine_operator="AND",
        )
        # Should not have "WHERE WHERE"
        assert "WHERE WHERE" not in result.upper()

    # --- Sanitize callback ---

    def test_sanitize_fn_applied(self):
        """Sanitize function should be called on old_subset."""
        def my_sanitize(subset):
            return subset.replace("display_only", "").strip()

        result = build_combined_filter_expression(
            new_expression="pop > 100",
            old_subset="display_only type = 'A'",
            combine_operator="AND",
            sanitize_fn=my_sanitize,
        )
        assert "display_only" not in result
        assert "type = 'A'" in result

    def test_sanitize_fn_returns_empty_falls_back(self):
        """If sanitize_fn returns empty, return new expression only."""
        def my_sanitize(subset):
            return ""

        result = build_combined_filter_expression(
            new_expression="pop > 100",
            old_subset="invalid stuff",
            combine_operator="AND",
            sanitize_fn=my_sanitize,
        )
        assert result == "pop > 100"

    # --- Parenthesization ---

    def test_simple_combination_wrapped_in_parens(self):
        """Simple subsets (no WHERE) should be wrapped in parentheses."""
        result = build_combined_filter_expression(
            new_expression="a = 1",
            old_subset="b = 2",
            combine_operator="OR",
        )
        assert "( b = 2 )" in result
        assert "( a = 1 )" in result

    # --- Edge cases ---

    def test_both_none(self):
        result = build_combined_filter_expression(
            new_expression="a = 1",
            old_subset=None,
            combine_operator=None,
        )
        assert result == "a = 1"

    def test_complex_old_subset_with_closing_parens(self):
        """Old subset ending with )) should have one paren stripped."""
        result = build_combined_filter_expression(
            new_expression="new_filter = 1",
            old_subset="SELECT * FROM t WHERE (type = 'city'))",
            combine_operator="AND",
        )
        assert "AND" in result

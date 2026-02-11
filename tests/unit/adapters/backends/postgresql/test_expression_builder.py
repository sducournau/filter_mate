# -*- coding: utf-8 -*-
"""
Unit tests for PostgreSQL Expression Builder.

Tests the PostgreSQLExpressionBuilder class for:
- Predicate sorting and mapping
- Simple WKT expression generation
- EXISTS subquery generation
- Source table reference parsing
- ST_Buffer with endcap styles
- Geographic CRS handling
- Column case normalization
- Numeric type casting
- Geometric filter detection
- Complex query detection
- Supports_layer check

All QGIS dependencies are mocked via the root conftest.py.
"""
import sys
import types
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Module-level mock setup -- must run before importing the builder
# ---------------------------------------------------------------------------

def _ensure_module_mocks():
    """Install mock modules required by PostgreSQLExpressionBuilder imports."""
    ROOT = "filter_mate"

    if ROOT not in sys.modules:
        fm = types.ModuleType(ROOT)
        fm.__path__ = []
        fm.__package__ = ROOT
        sys.modules[ROOT] = fm

    mocks_needed = {
        f"{ROOT}.core": MagicMock(),
        f"{ROOT}.core.ports": MagicMock(),
        f"{ROOT}.core.ports.geometric_filter_port": MagicMock(),
        f"{ROOT}.core.filter": MagicMock(),
        f"{ROOT}.core.filter.expression_combiner": MagicMock(),
        f"{ROOT}.infrastructure": MagicMock(),
        f"{ROOT}.infrastructure.database": MagicMock(),
        f"{ROOT}.infrastructure.database.sql_utils": MagicMock(),
        f"{ROOT}.infrastructure.utils": MagicMock(),
        f"{ROOT}.infrastructure.constants": MagicMock(),
        f"{ROOT}.adapters": MagicMock(),
        f"{ROOT}.adapters.backends": MagicMock(),
        f"{ROOT}.adapters.backends.postgresql": MagicMock(),
        f"{ROOT}.adapters.backends.postgresql.filter_chain_optimizer": MagicMock(),
        f"{ROOT}.adapters.backends.postgresql.filter_executor": MagicMock(),
    }

    for mod_name, mock_obj in mocks_needed.items():
        if mod_name not in sys.modules:
            sys.modules[mod_name] = mock_obj

    # Provide a real ABC base for GeometricFilterPort so the builder can subclass
    from abc import ABC, abstractmethod

    class _FakeGeometricFilterPort(ABC):
        def __init__(self, task_params):
            self.task_params = task_params
            self._warnings = []

        def log_debug(self, msg): pass
        def log_info(self, msg): pass
        def log_warning(self, msg): self._warnings.append(msg)
        def log_error(self, msg): pass

        def _get_buffer_endcap_style(self):
            return self.task_params.get("buffer_endcap_style", "round")

        def _apply_centroid_transform(self, geom_expr, layer_props):
            return f"ST_PointOnSurface({geom_expr})"

    sys.modules[f"{ROOT}.core.ports.geometric_filter_port"].GeometricFilterPort = _FakeGeometricFilterPort
    # Also ensure safe_set_subset_string is a callable
    sys.modules[f"{ROOT}.infrastructure.database.sql_utils"].safe_set_subset_string = MagicMock(return_value=True)
    sys.modules[f"{ROOT}.infrastructure.database.sql_utils"].sanitize_sql_identifier = lambda x: x

    # Mark chain optimizer as unavailable so import doesn't fail
    chain_mod = sys.modules[f"{ROOT}.adapters.backends.postgresql.filter_chain_optimizer"]
    chain_mod.FilterChainOptimizer = MagicMock
    chain_mod.FilterChainContext = MagicMock
    chain_mod.OptimizationStrategy = MagicMock


_ensure_module_mocks()


# Now import the class under test
import importlib.util
import os

_builder_path = os.path.normpath(os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..", "..", "..",
    "adapters", "backends", "postgresql", "expression_builder.py"
))

_spec = importlib.util.spec_from_file_location(
    "filter_mate.adapters.backends.postgresql.expression_builder",
    _builder_path,
)
_mod = importlib.util.module_from_spec(_spec)
_mod.__package__ = "filter_mate.adapters.backends.postgresql"
sys.modules[_mod.__name__] = _mod
_spec.loader.exec_module(_mod)

PostgreSQLExpressionBuilder = _mod.PostgreSQLExpressionBuilder


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def builder():
    """Create a default PostgreSQLExpressionBuilder with minimal task_params."""
    return PostgreSQLExpressionBuilder(task_params={
        "buffer_endcap_style": "round",
        "buffer_segments": 5,
    })


@pytest.fixture
def mock_pg_layer():
    """Create a mock PostgreSQL layer."""
    layer = MagicMock()
    layer.providerType.return_value = "postgres"
    layer.name.return_value = "test_buildings"
    layer.source.return_value = "dbname='mydb' host=localhost port=5432 sslmode=disable"

    # Fields
    field1 = MagicMock()
    field1.name.return_value = "id"
    field1.typeName.return_value = "integer"
    field2 = MagicMock()
    field2.name.return_value = "Name"
    field2.typeName.return_value = "varchar"
    layer.fields.return_value = [field1, field2]

    return layer


# ===========================================================================
# Tests -- supports_layer
# ===========================================================================

class TestSupportsLayer:
    def test_supports_postgres_layer(self, builder, mock_pg_layer):
        assert builder.supports_layer(mock_pg_layer) is True

    def test_rejects_ogr_layer(self, builder):
        layer = MagicMock()
        layer.providerType.return_value = "ogr"
        assert builder.supports_layer(layer) is False

    def test_rejects_none(self, builder):
        assert builder.supports_layer(None) is False


# ===========================================================================
# Tests -- get_backend_name
# ===========================================================================

class TestGetBackendName:
    def test_returns_postgresql(self, builder):
        assert builder.get_backend_name() == "PostgreSQL"


# ===========================================================================
# Tests -- _sort_predicates
# ===========================================================================

class TestSortPredicates:
    def test_sorts_by_selectivity(self, builder):
        predicates = {
            "intersects": "ST_Intersects",
            "within": "ST_Within",
            "contains": "ST_Contains",
        }
        sorted_result = builder._sort_predicates(predicates)
        names = [item[0] for item in sorted_result]
        # within is most selective (order 1), then contains (2), then intersects (8)
        assert names == ["within", "contains", "intersects"]

    def test_single_predicate(self, builder):
        predicates = {"intersects": "ST_Intersects"}
        sorted_result = builder._sort_predicates(predicates)
        assert len(sorted_result) == 1
        assert sorted_result[0][1] == "ST_Intersects"

    def test_empty_predicates(self, builder):
        assert builder._sort_predicates({}) == []


# ===========================================================================
# Tests -- _parse_source_table_reference
# ===========================================================================

class TestParseSourceTableReference:
    def test_parses_three_part_reference(self, builder):
        ref = '"public"."buildings"."geom"'
        result = builder._parse_source_table_reference(ref)
        assert result == {"schema": "public", "table": "buildings", "geom_field": "geom"}

    def test_parses_two_part_reference(self, builder):
        ref = '"roads"."geometry"'
        result = builder._parse_source_table_reference(ref)
        assert result == {"schema": "public", "table": "roads", "geom_field": "geometry"}

    def test_parses_reference_inside_function(self, builder):
        ref = 'ST_Buffer("ref"."demand_points"."geom", 100)'
        result = builder._parse_source_table_reference(ref)
        assert result["schema"] == "ref"
        assert result["table"] == "demand_points"
        assert result["geom_field"] == "geom"

    def test_returns_none_for_unparseable(self, builder):
        result = builder._parse_source_table_reference("some_random_text")
        assert result is None


# ===========================================================================
# Tests -- _build_simple_wkt_expression
# ===========================================================================

class TestBuildSimpleWktExpression:
    def test_basic_intersects(self, builder):
        expr = builder._build_simple_wkt_expression(
            geom_expr='"buildings"."geom"',
            predicate_func="ST_Intersects",
            source_wkt="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            source_srid=2154,
            buffer_value=None,
        )
        assert "ST_Intersects" in expr
        assert "ST_GeomFromText" in expr
        assert "ST_MakeValid" in expr
        assert "2154" in expr

    def test_with_buffer(self, builder):
        expr = builder._build_simple_wkt_expression(
            geom_expr='"t"."geom"',
            predicate_func="ST_Within",
            source_wkt="POINT(0 0)",
            source_srid=2154,
            buffer_value=100,
        )
        assert "ST_Buffer" in expr
        assert "100" in expr

    def test_geographic_crs_buffer(self, builder):
        expr = builder._build_simple_wkt_expression(
            geom_expr='"t"."geom"',
            predicate_func="ST_Intersects",
            source_wkt="POINT(2.3 48.8)",
            source_srid=4326,
            buffer_value=500,
        )
        # Should use ST_Transform to 3857 for metric buffer
        assert "ST_Transform" in expr
        assert "3857" in expr
        assert "500" in expr

    def test_zero_buffer_ignored(self, builder):
        expr = builder._build_simple_wkt_expression(
            geom_expr='"t"."geom"',
            predicate_func="ST_Intersects",
            source_wkt="POINT(0 0)",
            source_srid=2154,
            buffer_value=0,
        )
        assert "ST_Buffer" not in expr


# ===========================================================================
# Tests -- _build_st_buffer_with_style
# ===========================================================================

class TestBuildStBufferWithStyle:
    def test_positive_buffer_round_endcap(self, builder):
        result = builder._build_st_buffer_with_style('"t"."geom"', 100.0)
        assert "ST_Buffer" in result
        assert "100.0" in result
        assert "quad_segs=5" in result
        # No CASE WHEN for positive buffer
        assert "CASE WHEN" not in result

    def test_negative_buffer_wrapped_in_makevalid(self, builder):
        result = builder._build_st_buffer_with_style('"t"."geom"', -50.0)
        assert "ST_MakeValid" in result
        assert "ST_IsEmpty" in result
        assert "CASE WHEN" in result
        assert "-50.0" in result

    def test_flat_endcap_style(self):
        b = PostgreSQLExpressionBuilder(task_params={
            "buffer_endcap_style": "flat",
            "buffer_segments": 8,
        })
        result = b._build_st_buffer_with_style('"t"."geom"', 25.0)
        assert "endcap=flat" in result
        assert "quad_segs=8" in result


# ===========================================================================
# Tests -- _normalize_column_case
# ===========================================================================

class TestNormalizeColumnCase:
    def test_normalizes_case_mismatch(self, builder, mock_pg_layer):
        expr = '"name" = \'foo\''
        result = builder._normalize_column_case(expr, mock_pg_layer)
        # "name" should become "Name" (matching the field)
        assert '"Name"' in result

    def test_preserves_correct_case(self, builder, mock_pg_layer):
        expr = '"Name" = \'foo\''
        result = builder._normalize_column_case(expr, mock_pg_layer)
        assert '"Name"' in result

    def test_returns_empty_for_empty_expr(self, builder, mock_pg_layer):
        assert builder._normalize_column_case("", mock_pg_layer) == ""
        assert builder._normalize_column_case(None, mock_pg_layer) is None

    def test_returns_expr_for_none_layer(self, builder):
        expr = '"field" = 1'
        assert builder._normalize_column_case(expr, None) == expr


# ===========================================================================
# Tests -- _apply_numeric_type_casting
# ===========================================================================

class TestApplyNumericTypeCasting:
    def test_casts_varchar_comparison(self, builder, mock_pg_layer):
        expr = '"Name" > 100'
        result = builder._apply_numeric_type_casting(expr, mock_pg_layer)
        assert "::numeric" in result

    def test_no_cast_for_integer_field(self, builder, mock_pg_layer):
        expr = '"id" > 100'
        result = builder._apply_numeric_type_casting(expr, mock_pg_layer)
        # "id" is integer, so no ::numeric needed
        assert "::numeric" not in result

    def test_no_double_cast(self, builder, mock_pg_layer):
        expr = '"Name"::numeric > 100'
        result = builder._apply_numeric_type_casting(expr, mock_pg_layer)
        # Should not add a second ::numeric
        assert result.count("::numeric") == 1

    def test_empty_expression(self, builder, mock_pg_layer):
        assert builder._apply_numeric_type_casting("", mock_pg_layer) == ""
        assert builder._apply_numeric_type_casting(None, mock_pg_layer) is None


# ===========================================================================
# Tests -- _is_geometric_filter
# ===========================================================================

class TestIsGeometricFilter:
    def test_detects_exists(self, builder):
        assert builder._is_geometric_filter("EXISTS (SELECT 1 FROM ...)") is True

    def test_detects_st_intersects(self, builder):
        assert builder._is_geometric_filter('ST_INTERSECTS("t"."geom", ...)') is True

    def test_detects_source_alias(self, builder):
        assert builder._is_geometric_filter("__source.geom") is True

    def test_non_geometric_filter(self, builder):
        assert builder._is_geometric_filter('"id" IN (1, 2, 3)') is False

    def test_detects_st_buffer(self, builder):
        assert builder._is_geometric_filter("ST_Buffer(geom, 100)") is True


# ===========================================================================
# Tests -- _detect_and_warn_complex_query
# ===========================================================================

class TestDetectComplexQuery:
    def test_detects_buffer_plus_chaining(self, builder):
        builder._detect_and_warn_complex_query(
            buffer_expression="if(homecount > 100, 50, 1)",
            source_filter="EXISTS (SELECT 1 FROM zone_pop ...)",
            layer_name="test"
        )
        assert builder._is_complex_query is True

    def test_no_complex_when_no_buffer(self, builder):
        builder._detect_and_warn_complex_query(
            buffer_expression=None,
            source_filter="EXISTS (SELECT 1 FROM zone_pop ...)",
            layer_name="test"
        )
        assert builder._is_complex_query is False

    def test_no_complex_when_no_exists(self, builder):
        builder._detect_and_warn_complex_query(
            buffer_expression="100",
            source_filter='"id" IN (1, 2, 3)',
            layer_name="test"
        )
        assert builder._is_complex_query is False


# ===========================================================================
# Tests -- PREDICATE_FUNCTIONS mapping
# ===========================================================================

class TestPredicateFunctions:
    def test_all_standard_predicates_mapped(self, builder):
        expected = [
            "intersects", "contains", "within", "touches",
            "overlaps", "crosses", "disjoint", "equals",
            "covers", "coveredby",
        ]
        for pred in expected:
            assert pred in builder.PREDICATE_FUNCTIONS, f"Missing predicate: {pred}"
            assert builder.PREDICATE_FUNCTIONS[pred].startswith("ST_")

    def test_intersects_maps_correctly(self, builder):
        assert builder.PREDICATE_FUNCTIONS["intersects"] == "ST_Intersects"


# ===========================================================================
# Tests -- build_expression (integration-style with mocks)
# ===========================================================================

class TestBuildExpression:
    def test_no_predicates_returns_no_results(self, builder):
        result = builder.build_expression(
            layer_props={"layer_name": "test", "layer_schema": "public"},
            predicates={},
            source_wkt="POINT(0 0)",
            source_srid=2154,
            source_feature_count=10,
        )
        assert result == "1 = 0"

    def test_simple_wkt_mode_small_dataset(self, builder):
        result = builder.build_expression(
            layer_props={"layer_name": "test", "layer_table_name": "test"},
            predicates={"intersects": "ST_Intersects"},
            source_wkt="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            source_srid=2154,
            source_feature_count=10,
        )
        assert "ST_Intersects" in result
        assert "ST_GeomFromText" in result

    def test_exists_mode_large_dataset(self, builder):
        result = builder.build_expression(
            layer_props={"layer_name": "test", "layer_table_name": "test"},
            predicates={"intersects": "ST_Intersects"},
            source_geom='"public"."source"."geom"',
            source_wkt="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            source_srid=2154,
            source_feature_count=500,
        )
        assert "EXISTS" in result
        assert "__source" in result

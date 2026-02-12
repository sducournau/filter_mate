# -*- coding: utf-8 -*-
"""
Unit tests for OGR Filter Executor.

Tests the pure functions in ogr/filter_executor.py:
- format_ogr_pk_values(): PK value formatting for SQL
- normalize_column_names_for_ogr(): Case normalization
- build_ogr_simple_filter(): IN clause construction
- combine_ogr_filters(): Filter combination with AND/OR/NOT
- register_temp_layer() / cleanup_ogr_temp_layers(): Registry
- build_ogr_filter_from_selection(): Selection-based filter
- apply_ogr_subset(): Thread-safe subset application
- execute_reset_action_ogr(): Reset to no filter
- execute_unfilter_action_ogr(): Restore previous filter

All QGIS dependencies are mocked.
"""
import sys
import types
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Mock setup
# ---------------------------------------------------------------------------

def _ensure_ogr_mocks():
    ROOT = "filter_mate"
    if ROOT not in sys.modules:
        fm = types.ModuleType(ROOT)
        fm.__path__ = []
        fm.__package__ = ROOT
        sys.modules[ROOT] = fm

    mocks = {
        f"{ROOT}.core": MagicMock(),
        f"{ROOT}.core.geometry": MagicMock(),
        f"{ROOT}.core.geometry.geometry_safety": MagicMock(),
        f"{ROOT}.infrastructure": MagicMock(),
        f"{ROOT}.infrastructure.database": MagicMock(),
        f"{ROOT}.infrastructure.database.sql_utils": MagicMock(),
        f"{ROOT}.adapters": MagicMock(),
        f"{ROOT}.adapters.backends": MagicMock(),
        f"{ROOT}.adapters.backends.ogr": MagicMock(),
    }
    mocks[f"{ROOT}.infrastructure.database.sql_utils"].safe_set_subset_string = MagicMock(return_value=True)

    for name, mock_obj in mocks.items():
        if name not in sys.modules:
            sys.modules[name] = mock_obj


_ensure_ogr_mocks()

import importlib.util
import os

_executor_path = os.path.normpath(os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..", "..", "..",
    "adapters", "backends", "ogr", "filter_executor.py"
))

_spec = importlib.util.spec_from_file_location(
    "filter_mate.adapters.backends.ogr.filter_executor",
    _executor_path,
)
_mod = importlib.util.module_from_spec(_spec)
_mod.__package__ = "filter_mate.adapters.backends.ogr"
sys.modules[_mod.__name__] = _mod
_spec.loader.exec_module(_mod)

format_ogr_pk_values = _mod.format_ogr_pk_values
normalize_column_names_for_ogr = _mod.normalize_column_names_for_ogr
build_ogr_simple_filter = _mod.build_ogr_simple_filter
combine_ogr_filters = _mod.combine_ogr_filters
register_temp_layer = _mod.register_temp_layer
apply_ogr_subset = _mod.apply_ogr_subset
execute_reset_action_ogr = _mod.execute_reset_action_ogr
execute_unfilter_action_ogr = _mod.execute_unfilter_action_ogr
OGRSourceContext = _mod.OGRSourceContext
validate_task_features = _mod.validate_task_features
determine_source_mode = _mod.determine_source_mode

# Reset the temp layer registry between test runs
_temp_registry = _mod._temp_layer_registry


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture(autouse=True)
def clear_temp_registry():
    """Clear the temp layer registry before each test."""
    _mod._temp_layer_registry.clear()
    yield
    _mod._temp_layer_registry.clear()


# ===========================================================================
# Tests -- format_ogr_pk_values
# ===========================================================================

class TestFormatOgrPkValues:
    def test_numeric_values(self):
        result = format_ogr_pk_values([1, 2, 3], is_numeric=True)
        assert result == "1, 2, 3"

    def test_string_values(self):
        result = format_ogr_pk_values(["a", "b", "c"], is_numeric=False)
        assert result == "'a', 'b', 'c'"

    def test_string_values_with_quotes(self):
        result = format_ogr_pk_values(["it's", "John's"], is_numeric=False)
        assert "'it''s'" in result
        assert "'John''s'" in result

    def test_empty_values(self):
        assert format_ogr_pk_values([], is_numeric=True) == ""
        assert format_ogr_pk_values([], is_numeric=False) == ""

    def test_single_value(self):
        assert format_ogr_pk_values([42], is_numeric=True) == "42"
        assert format_ogr_pk_values(["x"], is_numeric=False) == "'x'"


# ===========================================================================
# Tests -- normalize_column_names_for_ogr
# ===========================================================================

class TestNormalizeColumnNames:
    def test_fixes_case_mismatch(self):
        expr = '"NAME" = \'foo\''
        result = normalize_column_names_for_ogr(expr, ["name", "id"])
        assert '"name"' in result

    def test_preserves_correct_case(self):
        expr = '"name" = \'foo\''
        result = normalize_column_names_for_ogr(expr, ["name", "id"])
        assert '"name"' in result

    def test_no_change_for_unknown_column(self):
        expr = '"unknown_col" = 1'
        result = normalize_column_names_for_ogr(expr, ["name", "id"])
        assert '"unknown_col"' in result

    def test_empty_expression(self):
        assert normalize_column_names_for_ogr("", ["name"]) == ""

    def test_empty_field_names(self):
        expr = '"name" = 1'
        assert normalize_column_names_for_ogr(expr, []) == expr

    def test_multiple_columns_fixed(self):
        expr = '"NAME" = \'foo\' AND "ID" > 10'
        result = normalize_column_names_for_ogr(expr, ["name", "id"])
        assert '"name"' in result
        assert '"id"' in result


# ===========================================================================
# Tests -- build_ogr_simple_filter
# ===========================================================================

class TestBuildOgrSimpleFilter:
    def test_numeric_filter(self):
        result = build_ogr_simple_filter("id", [1, 2, 3], is_numeric=True)
        assert result == '"id" IN (1, 2, 3)'

    def test_string_filter(self):
        result = build_ogr_simple_filter("code", ["A", "B"], is_numeric=False)
        assert result == '"code" IN (\'A\', \'B\')'

    def test_empty_ids(self):
        assert build_ogr_simple_filter("id", [], is_numeric=True) == ""

    def test_single_id(self):
        result = build_ogr_simple_filter("fid", [42], is_numeric=True)
        assert result == '"fid" IN (42)'


# ===========================================================================
# Tests -- combine_ogr_filters
# ===========================================================================

class TestCombineOgrFilters:
    def test_and_combination(self):
        result = combine_ogr_filters('"a" = 1', '"b" = 2', "AND")
        assert result == '("a" = 1) AND ("b" = 2)'

    def test_or_combination(self):
        result = combine_ogr_filters('"a" = 1', '"b" = 2', "OR")
        assert result == '("a" = 1) OR ("b" = 2)'

    def test_not_combination(self):
        result = combine_ogr_filters('"a" = 1', '"b" = 2', "NOT")
        assert result == '("a" = 1) AND NOT ("b" = 2)'

    def test_empty_existing_filter(self):
        result = combine_ogr_filters("", '"b" = 2', "AND")
        assert result == '"b" = 2'

    def test_empty_new_filter(self):
        result = combine_ogr_filters('"a" = 1', "", "AND")
        assert result == '"a" = 1'

    def test_case_insensitive_operator(self):
        result = combine_ogr_filters('"a" = 1', '"b" = 2', "and")
        assert "AND" in result


# ===========================================================================
# Tests -- register_temp_layer
# ===========================================================================

class TestRegisterTempLayer:
    def test_registers_layer_id(self):
        register_temp_layer("layer_123")
        assert "layer_123" in _mod._temp_layer_registry

    def test_no_duplicate_registration(self):
        register_temp_layer("layer_123")
        register_temp_layer("layer_123")
        assert _mod._temp_layer_registry.count("layer_123") == 1

    def test_multiple_layers(self):
        register_temp_layer("layer_1")
        register_temp_layer("layer_2")
        assert len(_mod._temp_layer_registry) == 2


# ===========================================================================
# Tests -- apply_ogr_subset
# ===========================================================================

class TestApplyOgrSubset:
    def test_direct_application(self):
        layer = MagicMock()
        layer.setSubsetString.return_value = True
        result = apply_ogr_subset(layer, '"id" > 10')
        assert result is True
        layer.setSubsetString.assert_called_once_with('"id" > 10')

    def test_queued_application(self):
        layer = MagicMock()
        queue_func = MagicMock()
        result = apply_ogr_subset(layer, '"id" > 10', queue_subset_func=queue_func)
        assert result is True
        queue_func.assert_called_once_with(layer, '"id" > 10')

    def test_direct_application_error(self):
        layer = MagicMock()
        layer.setSubsetString.side_effect = Exception("OGR error")
        result = apply_ogr_subset(layer, '"id" > 10')
        assert result is False


# ===========================================================================
# Tests -- execute_reset_action_ogr
# ===========================================================================

class TestExecuteResetActionOgr:
    def test_resets_direct(self):
        layer = MagicMock()
        layer.name.return_value = "test"
        result = execute_reset_action_ogr(layer, cleanup_temp_layers=False)
        assert result is True
        layer.setSubsetString.assert_called_once_with("")

    def test_resets_queued(self):
        layer = MagicMock()
        layer.name.return_value = "test"
        queue_func = MagicMock()
        result = execute_reset_action_ogr(layer, queue_subset_func=queue_func, cleanup_temp_layers=False)
        assert result is True
        queue_func.assert_called_once_with(layer, "")

    def test_returns_false_on_error(self):
        layer = MagicMock()
        layer.name.side_effect = Exception("error")
        layer.setSubsetString.side_effect = Exception("error")
        result = execute_reset_action_ogr(layer, cleanup_temp_layers=False)
        assert result is False


# ===========================================================================
# Tests -- execute_unfilter_action_ogr
# ===========================================================================

class TestExecuteUnfilterActionOgr:
    def test_restores_previous_subset(self):
        layer = MagicMock()
        layer.name.return_value = "test"
        result = execute_unfilter_action_ogr(layer, previous_subset='"id" > 5')
        assert result is True
        layer.setSubsetString.assert_called_once_with('"id" > 5')

    def test_clears_when_no_previous(self):
        layer = MagicMock()
        layer.name.return_value = "test"
        result = execute_unfilter_action_ogr(layer, previous_subset=None)
        assert result is True
        layer.setSubsetString.assert_called_once_with("")

    def test_queued_mode(self):
        layer = MagicMock()
        layer.name.return_value = "test"
        queue_func = MagicMock()
        result = execute_unfilter_action_ogr(
            layer, previous_subset='"x" = 1', queue_subset_func=queue_func
        )
        assert result is True
        queue_func.assert_called_once_with(layer, '"x" = 1')


# ===========================================================================
# Tests -- OGRSourceContext
# ===========================================================================

class TestOGRSourceContext:
    def test_default_values(self):
        ctx = OGRSourceContext()
        assert ctx.source_layer is None
        assert ctx.has_to_reproject_source_layer is False
        assert ctx.param_use_centroids_source_layer is False
        assert ctx.task_parameters == {}

    def test_custom_values(self):
        layer = MagicMock()
        ctx = OGRSourceContext(
            source_layer=layer,
            has_to_reproject_source_layer=True,
            param_use_centroids_source_layer=True,
        )
        assert ctx.source_layer is layer
        assert ctx.has_to_reproject_source_layer is True


# ===========================================================================
# Tests -- validate_task_features
# ===========================================================================

class TestValidateTaskFeatures:
    def test_filters_none_and_empty(self):
        features = [None, "", MagicMock(hasGeometry=MagicMock(return_value=False))]
        valid, invalid, recovered = validate_task_features(features)
        assert len(valid) == 0
        assert invalid >= 1

    def test_valid_features_pass(self):
        feat = MagicMock()
        feat.hasGeometry.return_value = True
        geom = MagicMock()
        geom.isEmpty.return_value = False
        feat.geometry.return_value = geom
        valid, invalid, _ = validate_task_features([feat])
        assert len(valid) == 1
        assert invalid == 0

    def test_cancel_check(self):
        """Test that cancellation stops processing.

        The implementation checks at i > 0 and i % 100 == 0, so with 300
        features: first check at i=100 (returns False), second at i=200
        (returns True -> break).  We expect ~200 valid features, well
        below 300.
        """
        features = [MagicMock() for _ in range(300)]
        for f in features:
            f.hasGeometry.return_value = True
            g = MagicMock()
            g.isEmpty.return_value = False
            f.geometry.return_value = g

        cancel_called = [0]

        def cancel_check():
            cancel_called[0] += 1
            return cancel_called[0] > 1  # Cancel after second check (i=200)

        valid, _, _ = validate_task_features(features, cancel_check=cancel_check)
        # Should have stopped at i=200, well before processing all 300
        assert len(valid) < 300


# ===========================================================================
# Tests -- determine_source_mode
# ===========================================================================

class TestDetermineSourceMode:
    def test_invalid_when_no_layer(self):
        ctx = OGRSourceContext(source_layer=None)
        mode, data = determine_source_mode(ctx)
        assert mode == "INVALID"

    def test_direct_mode_default(self):
        layer = MagicMock()
        layer.subsetString.return_value = ""
        layer.selectedFeatureCount.return_value = 0
        ctx = OGRSourceContext(
            source_layer=layer,
            task_parameters={},
        )
        mode, data = determine_source_mode(ctx)
        assert mode == "DIRECT"

    def test_selection_mode(self):
        layer = MagicMock()
        layer.subsetString.return_value = ""
        layer.selectedFeatureCount.return_value = 5
        ctx = OGRSourceContext(
            source_layer=layer,
            task_parameters={},
        )
        mode, data = determine_source_mode(ctx)
        assert mode == "SELECTION"

    def test_subset_mode(self):
        layer = MagicMock()
        layer.subsetString.return_value = '"id" > 10'
        layer.selectedFeatureCount.return_value = 0
        ctx = OGRSourceContext(
            source_layer=layer,
            task_parameters={},
        )
        mode, data = determine_source_mode(ctx)
        assert mode == "SUBSET"

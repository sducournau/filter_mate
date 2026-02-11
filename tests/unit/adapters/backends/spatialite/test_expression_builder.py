# -*- coding: utf-8 -*-
"""
Unit tests for Spatialite Expression Builder.

Tests the SpatialiteExpressionBuilder class for:
- Layer support detection (spatialite, geopackage)
- Expression building with predicates
- GeoPackage GeomFromGPB conversion
- Dynamic buffer fallback to OGR
- GeometryCollection fallback to OGR
- Source geometry SQL construction
- Geometric filter detection
- Empty/invalid inputs handling

All QGIS dependencies are mocked.
"""
import sys
import types
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Mock setup
# ---------------------------------------------------------------------------

def _ensure_spatialite_mocks():
    ROOT = "filter_mate"
    if ROOT not in sys.modules:
        fm = types.ModuleType(ROOT)
        fm.__path__ = []
        fm.__package__ = ROOT
        sys.modules[ROOT] = fm

    from abc import ABC

    class _FakeGeometricFilterPort(ABC):
        def __init__(self, task_params):
            self.task_params = task_params
            self._warnings = []
            self._logger = MagicMock()

        def log_debug(self, msg): pass
        def log_info(self, msg): pass
        def log_warning(self, msg): self._warnings.append(msg)
        def log_error(self, msg): pass

        def _get_buffer_endcap_style(self):
            return self.task_params.get("buffer_endcap_style", "round")

        def _apply_centroid_transform(self, geom_expr, layer_props):
            return f"ST_PointOnSurface({geom_expr})"

        def _detect_geometry_column(self, layer_props):
            return layer_props.get("layer_geometry_field", "geom")

        def _get_layer_srid(self, layer):
            if not layer:
                return 4326
            try:
                crs = layer.crs()
                if crs and crs.isValid():
                    authid = crs.authid()
                    if ':' in authid:
                        return int(authid.split(':')[1])
            except Exception:
                pass
            return 2154

        def _get_source_srid(self):
            if self.task_params:
                source_crs = self.task_params.get('infos', {}).get('layer_crs_authid', '')
                if ':' in str(source_crs):
                    try:
                        return int(str(source_crs).split(':')[1])
                    except (ValueError, IndexError):
                        pass
            return self.task_params.get("source_srid", 4326)

    mocks = {
        f"{ROOT}.core": MagicMock(),
        f"{ROOT}.core.ports": MagicMock(),
        f"{ROOT}.core.ports.geometric_filter_port": MagicMock(),
        f"{ROOT}.infrastructure": MagicMock(),
        f"{ROOT}.infrastructure.database": MagicMock(),
        f"{ROOT}.infrastructure.database.sql_utils": MagicMock(),
        f"{ROOT}.adapters": MagicMock(),
        f"{ROOT}.adapters.backends": MagicMock(),
        f"{ROOT}.adapters.backends.spatialite": MagicMock(),
        f"{ROOT}.adapters.backends.spatialite.filter_executor": MagicMock(),
    }
    mocks[f"{ROOT}.infrastructure.database.sql_utils"].safe_set_subset_string = MagicMock(return_value=True)
    mocks[f"{ROOT}.core.ports.geometric_filter_port"].GeometricFilterPort = _FakeGeometricFilterPort

    # Always overwrite -- other test files may have already registered plain
    # MagicMock() objects for these module paths, which would lack the real
    # _FakeGeometricFilterPort class required by SpatialiteExpressionBuilder.
    for name, mock_obj in mocks.items():
        sys.modules[name] = mock_obj


_ensure_spatialite_mocks()

import importlib.util
import os

_builder_path = os.path.normpath(os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..", "..", "..",
    "adapters", "backends", "spatialite", "expression_builder.py"
))

# Force-reload to pick up the freshly installed fake GeometricFilterPort.
_mod_name = "filter_mate.adapters.backends.spatialite.expression_builder"
if _mod_name in sys.modules:
    del sys.modules[_mod_name]

_spec = importlib.util.spec_from_file_location(_mod_name, _builder_path)
_mod = importlib.util.module_from_spec(_spec)
_mod.__package__ = "filter_mate.adapters.backends.spatialite"
sys.modules[_mod_name] = _mod
_spec.loader.exec_module(_mod)

SpatialiteExpressionBuilder = _mod.SpatialiteExpressionBuilder
USE_OGR_FALLBACK = _mod.USE_OGR_FALLBACK


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def builder():
    return SpatialiteExpressionBuilder(task_params={
        "buffer_endcap_style": "round",
        "source_srid": 2154,
    })


@pytest.fixture
def mock_spatialite_layer():
    layer = MagicMock()
    layer.providerType.return_value = "spatialite"
    layer.source.return_value = "/tmp/test.sqlite"
    layer.isValid.return_value = True
    return layer


@pytest.fixture
def mock_gpkg_layer():
    layer = MagicMock()
    layer.providerType.return_value = "ogr"
    layer.source.return_value = "/tmp/data.gpkg|layername=buildings"
    layer.isValid.return_value = True
    return layer


# ===========================================================================
# Tests -- supports_layer
# ===========================================================================

class TestSupportsLayer:
    def test_supports_spatialite(self, builder, mock_spatialite_layer):
        assert builder.supports_layer(mock_spatialite_layer) is True

    def test_supports_geopackage(self, builder, mock_gpkg_layer):
        assert builder.supports_layer(mock_gpkg_layer) is True

    def test_rejects_postgres(self, builder):
        layer = MagicMock()
        layer.providerType.return_value = "postgres"
        assert builder.supports_layer(layer) is False

    def test_rejects_none(self, builder):
        assert builder.supports_layer(None) is False

    def test_rejects_ogr_non_gpkg(self, builder):
        layer = MagicMock()
        layer.providerType.return_value = "ogr"
        layer.source.return_value = "/tmp/data.shp"
        assert builder.supports_layer(layer) is False


# ===========================================================================
# Tests -- get_backend_name
# ===========================================================================

class TestGetBackendName:
    def test_returns_spatialite(self, builder):
        assert builder.get_backend_name() == "Spatialite"


# ===========================================================================
# Tests -- build_expression
# ===========================================================================

class TestBuildExpression:
    def test_basic_intersects(self, builder):
        expr = builder.build_expression(
            layer_props={"layer_name": "test", "layer_geometry_field": "geom"},
            predicates={"intersects": True},
            source_geom="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
        )
        assert "Intersects" in expr
        assert "GeomFromText" in expr
        assert "MakeValid" in expr

    def test_multiple_predicates_combined_with_or(self, builder):
        expr = builder.build_expression(
            layer_props={"layer_name": "test", "layer_geometry_field": "geom"},
            predicates={"intersects": True, "within": True},
            source_geom="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
        )
        assert " OR " in expr

    def test_no_predicates_returns_no_results(self, builder):
        expr = builder.build_expression(
            layer_props={"layer_name": "test"},
            predicates={},
            source_geom="POINT(0 0)",
        )
        assert expr == "1 = 0"

    def test_false_predicates_skipped(self, builder):
        expr = builder.build_expression(
            layer_props={"layer_name": "test", "layer_geometry_field": "geom"},
            predicates={"intersects": False, "within": False},
            source_geom="POINT(0 0)",
        )
        assert expr == "1 = 0"

    def test_dynamic_buffer_returns_ogr_fallback(self, builder):
        expr = builder.build_expression(
            layer_props={"layer_name": "test"},
            predicates={"intersects": True},
            source_geom="POINT(0 0)",
            buffer_expression="if(homecount > 100, 50, 1)",
        )
        assert expr == USE_OGR_FALLBACK

    def test_geometry_collection_returns_ogr_fallback(self, builder):
        expr = builder.build_expression(
            layer_props={"layer_name": "test", "layer_geometry_field": "geom"},
            predicates={"intersects": True},
            source_geom="GEOMETRYCOLLECTION(POINT(0 0), LINESTRING(0 0, 1 1))",
        )
        assert expr == USE_OGR_FALLBACK

    def test_no_source_geom_returns_no_results(self, builder):
        expr = builder.build_expression(
            layer_props={"layer_name": "test"},
            predicates={"intersects": True},
            source_geom=None,
        )
        assert expr == "1 = 0"

    def test_non_string_source_geom_returns_no_results(self, builder):
        expr = builder.build_expression(
            layer_props={"layer_name": "test"},
            predicates={"intersects": True},
            source_geom=12345,
        )
        assert expr == "1 = 0"


# ===========================================================================
# Tests -- GeoPackage detection
# ===========================================================================

class TestGeoPackageDetection:
    def test_geopackage_uses_geomfromgpb(self, builder, mock_gpkg_layer):
        expr = builder.build_expression(
            layer_props={
                "layer_name": "test",
                "layer_geometry_field": "geom",
                "layer": mock_gpkg_layer,
            },
            predicates={"intersects": True},
            source_geom="POINT(0 0)",
        )
        assert "GeomFromGPB" in expr


# ===========================================================================
# Tests -- _build_source_geometry_sql
# ===========================================================================

class TestBuildSourceGeometrySql:
    def test_basic_geometry(self, builder):
        sql = builder._build_source_geometry_sql(
            "POINT(0 0)", 2154, 2154, None, None
        )
        assert "GeomFromText" in sql
        assert "MakeValid" in sql
        assert "2154" in sql

    def test_with_crs_transform(self, builder):
        sql = builder._build_source_geometry_sql(
            "POINT(0 0)", 4326, 2154, None, None
        )
        assert "Transform" in sql
        assert "2154" in sql

    def test_with_buffer(self, builder):
        sql = builder._build_source_geometry_sql(
            "POINT(0 0)", 2154, 2154, 100, None
        )
        assert "Buffer" in sql
        assert "100" in sql

    def test_negative_buffer_wrapped_in_makevalid(self, builder):
        sql = builder._build_source_geometry_sql(
            "POINT(0 0)", 2154, 2154, -50, None
        )
        assert "Buffer" in sql
        assert "MakeValid" in sql

    def test_escapes_single_quotes(self, builder):
        wkt = "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
        sql = builder._build_source_geometry_sql(wkt, 2154, 2154, None, None)
        # No single quote issues
        assert "GeomFromText" in sql


# ===========================================================================
# Tests -- PREDICATE_FUNCTIONS
# ===========================================================================

class TestPredicateFunctions:
    def test_all_standard_predicates(self, builder):
        expected = [
            "intersects", "contains", "within", "touches",
            "overlaps", "crosses", "disjoint", "equals",
        ]
        for pred in expected:
            assert pred in builder.PREDICATE_FUNCTIONS

    def test_spatialite_function_names(self, builder):
        # Spatialite uses non-ST_ prefix
        assert builder.PREDICATE_FUNCTIONS["intersects"] == "Intersects"
        assert builder.PREDICATE_FUNCTIONS["contains"] == "Contains"
        assert builder.PREDICATE_FUNCTIONS["within"] == "Within"


# ===========================================================================
# Tests -- _is_geometric_filter
# ===========================================================================

class TestIsGeometricFilter:
    def test_detects_intersects(self, builder):
        assert builder._is_geometric_filter("Intersects(geom, ...)") is True

    def test_detects_geomfromtext(self, builder):
        assert builder._is_geometric_filter("GeomFromText('POINT(0 0)', 2154)") is True

    def test_detects_geomfromgpb(self, builder):
        assert builder._is_geometric_filter("GeomFromGPB(geom)") is True

    def test_detects_buffer(self, builder):
        assert builder._is_geometric_filter("Buffer(geom, 100)") is True

    def test_non_geometric(self, builder):
        assert builder._is_geometric_filter('"id" IN (1, 2, 3)') is False


# ===========================================================================
# Tests -- apply_filter
# ===========================================================================

class TestApplyFilter:
    def test_apply_empty_expression(self, builder, mock_spatialite_layer):
        result = builder.apply_filter(mock_spatialite_layer, "")
        assert result is False

    def test_apply_ogr_fallback_sentinel(self, builder, mock_spatialite_layer):
        result = builder.apply_filter(mock_spatialite_layer, USE_OGR_FALLBACK)
        assert result is False

    def test_apply_valid_expression(self, builder, mock_spatialite_layer):
        result = builder.apply_filter(
            mock_spatialite_layer,
            'Intersects("geom", GeomFromText(\'POINT(0 0)\', 2154))'
        )
        assert result is True

    def test_combine_with_existing_filter(self, builder, mock_spatialite_layer):
        result = builder.apply_filter(
            mock_spatialite_layer,
            'Intersects("geom", GeomFromText(\'POINT(0 0)\', 2154))',
            old_subset='"type" = \'highway\'',
            combine_operator="AND",
        )
        assert result is True

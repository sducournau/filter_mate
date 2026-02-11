# -*- coding: utf-8 -*-
"""
Tests for FilterMate domain models.

These are PURE PYTHON tests -- no QGIS dependency.
Tests cover all dataclasses, enums, value objects, and entities
defined in core/domain/.

Modules tested:
    - core.domain.filter_expression (FilterExpression, ProviderType, SpatialPredicate)
    - core.domain.filter_result (FilterResult, FilterStatus)
    - core.domain.layer_info (LayerInfo, GeometryType)
    - core.domain.optimization_config (OptimizationConfig)
    - core.domain.raster_filter_criteria (RasterSamplingCriteria, ComparisonOperator, etc.)
"""
import pytest

from core.domain.filter_expression import (
    FilterExpression,
    ProviderType,
    SpatialPredicate,
)
from core.domain.filter_result import FilterResult, FilterStatus
from core.domain.layer_info import LayerInfo, GeometryType
from core.domain.optimization_config import OptimizationConfig
from core.domain.raster_filter_criteria import (
    ComparisonOperator,
    RasterSamplingCriteria,
    RasterSamplingResult,
    SamplingMethod,
    SamplingStats,
)


# =========================================================================
# ProviderType enum
# =========================================================================

class TestProviderType:
    """Tests for ProviderType enum and its factory method."""

    def test_enum_values(self):
        assert ProviderType.POSTGRESQL.value == "postgresql"
        assert ProviderType.SPATIALITE.value == "spatialite"
        assert ProviderType.OGR.value == "ogr"
        assert ProviderType.MEMORY.value == "memory"
        assert ProviderType.UNKNOWN.value == "unknown"

    def test_from_qgis_provider_postgres(self):
        assert ProviderType.from_qgis_provider("postgres") == ProviderType.POSTGRESQL

    def test_from_qgis_provider_postgresql(self):
        assert ProviderType.from_qgis_provider("postgresql") == ProviderType.POSTGRESQL

    def test_from_qgis_provider_spatialite(self):
        assert ProviderType.from_qgis_provider("spatialite") == ProviderType.SPATIALITE

    def test_from_qgis_provider_ogr(self):
        assert ProviderType.from_qgis_provider("ogr") == ProviderType.OGR

    def test_from_qgis_provider_memory(self):
        assert ProviderType.from_qgis_provider("memory") == ProviderType.MEMORY

    def test_from_qgis_provider_unknown(self):
        assert ProviderType.from_qgis_provider("wfs") == ProviderType.UNKNOWN

    def test_from_qgis_provider_case_insensitive(self):
        assert ProviderType.from_qgis_provider("POSTGRES") == ProviderType.POSTGRESQL
        assert ProviderType.from_qgis_provider("OGR") == ProviderType.OGR


# =========================================================================
# SpatialPredicate enum
# =========================================================================

class TestSpatialPredicate:
    """Tests for SpatialPredicate enum values."""

    def test_all_predicates_exist(self):
        expected = [
            "intersects", "contains", "within", "crosses",
            "touches", "overlaps", "disjoint", "equals", "dwithin",
        ]
        for pred_value in expected:
            assert SpatialPredicate(pred_value).value == pred_value


# =========================================================================
# FilterExpression value object
# =========================================================================

class TestFilterExpression:
    """Tests for the FilterExpression frozen dataclass."""

    def test_create_simple_expression(self):
        expr = FilterExpression.create(
            raw="name = 'Paris'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_1",
        )
        assert expr.raw == "name = 'Paris'"
        assert expr.provider == ProviderType.POSTGRESQL
        assert expr.source_layer_id == "layer_1"
        assert expr.is_simple is True
        assert expr.is_spatial is False

    def test_create_spatial_expression_detected(self):
        expr = FilterExpression.create(
            raw="intersects(geom, buffer(point, 100))",
            provider=ProviderType.OGR,
            source_layer_id="layer_2",
        )
        assert expr.is_spatial is True
        assert SpatialPredicate.INTERSECTS in expr.spatial_predicates

    def test_create_with_buffer(self):
        expr = FilterExpression.create(
            raw="field = 1",
            provider=ProviderType.OGR,
            source_layer_id="layer_3",
            buffer_value=10.0,
        )
        assert expr.buffer_value == 10.0
        assert expr.has_buffer is True

    def test_empty_expression_raises(self):
        with pytest.raises(ValueError, match="empty"):
            FilterExpression.create(
                raw="",
                provider=ProviderType.OGR,
                source_layer_id="layer_x",
            )

    def test_whitespace_expression_raises(self):
        with pytest.raises(ValueError, match="empty"):
            FilterExpression.create(
                raw="   ",
                provider=ProviderType.OGR,
                source_layer_id="layer_x",
            )

    def test_negative_buffer_raises(self):
        with pytest.raises(ValueError, match="negative"):
            FilterExpression(
                raw="field = 1",
                sql="field = 1",
                provider=ProviderType.OGR,
                buffer_value=-5.0,
            )

    def test_invalid_provider_type_raises(self):
        with pytest.raises(TypeError):
            FilterExpression(
                raw="field = 1",
                sql="field = 1",
                provider="not_a_provider",
            )

    def test_zero_buffer_segments_raises(self):
        with pytest.raises(ValueError, match="segments"):
            FilterExpression(
                raw="field = 1",
                sql="field = 1",
                provider=ProviderType.OGR,
                buffer_segments=0,
            )

    def test_frozen_immutability(self):
        expr = FilterExpression.create(
            raw="field = 1",
            provider=ProviderType.OGR,
            source_layer_id="layer_5",
        )
        with pytest.raises(AttributeError):
            expr.raw = "field = 2"

    def test_with_sql(self):
        expr = FilterExpression.create(
            raw="field = 1",
            provider=ProviderType.OGR,
            source_layer_id="layer_6",
        )
        new_expr = expr.with_sql("SELECT * WHERE field = 1")
        assert new_expr.sql == "SELECT * WHERE field = 1"
        assert new_expr.raw == "field = 1"  # raw unchanged
        assert expr.sql != new_expr.sql  # original unchanged

    def test_with_buffer(self):
        expr = FilterExpression.create(
            raw="field = 1",
            provider=ProviderType.OGR,
            source_layer_id="layer_7",
        )
        buffered = expr.with_buffer(25.0, segments=8)
        assert buffered.buffer_value == 25.0
        assert buffered.buffer_segments == 8
        assert buffered.is_spatial is True

    def test_with_provider(self):
        expr = FilterExpression.create(
            raw="field = 1",
            provider=ProviderType.OGR,
            source_layer_id="layer_8",
        )
        pg_expr = expr.with_provider(ProviderType.POSTGRESQL)
        assert pg_expr.provider == ProviderType.POSTGRESQL
        assert expr.provider == ProviderType.OGR

    def test_create_spatial_from_predicates(self):
        expr = FilterExpression.create_spatial(
            predicates=[SpatialPredicate.INTERSECTS, SpatialPredicate.CONTAINS],
            buffer_value=5.0,
            provider=ProviderType.POSTGRESQL,
            source_layer_id="src",
        )
        assert expr.is_spatial is True
        assert len(expr.spatial_predicates) == 2
        assert expr.buffer_value == 5.0

    def test_predicate_names(self):
        expr = FilterExpression.create_spatial(
            predicates=[SpatialPredicate.WITHIN, SpatialPredicate.TOUCHES],
            provider=ProviderType.OGR,
        )
        assert expr.predicate_names == ["within", "touches"]

    def test_str_truncates_long_expression(self):
        long_raw = "x" * 100
        expr = FilterExpression.create(
            raw=long_raw,
            provider=ProviderType.OGR,
            source_layer_id="l",
        )
        result = str(expr)
        assert "..." in result

    def test_detect_multiple_spatial_predicates(self):
        expr = FilterExpression.create(
            raw="intersects AND within AND disjoint query",
            provider=ProviderType.OGR,
            source_layer_id="l",
        )
        assert SpatialPredicate.INTERSECTS in expr.spatial_predicates
        assert SpatialPredicate.WITHIN in expr.spatial_predicates
        assert SpatialPredicate.DISJOINT in expr.spatial_predicates


# =========================================================================
# FilterStatus enum
# =========================================================================

class TestFilterStatus:
    """Tests for FilterStatus enum values."""

    def test_all_statuses(self):
        assert FilterStatus.SUCCESS.value == "success"
        assert FilterStatus.PARTIAL.value == "partial"
        assert FilterStatus.CANCELLED.value == "cancelled"
        assert FilterStatus.ERROR.value == "error"
        assert FilterStatus.NO_MATCHES.value == "no_matches"


# =========================================================================
# FilterResult value object
# =========================================================================

class TestFilterResult:
    """Tests for the FilterResult frozen dataclass and factory methods."""

    def test_success_with_features(self):
        result = FilterResult.success(
            feature_ids=[1, 2, 3],
            layer_id="layer_1",
            expression_raw="field > 0",
            execution_time_ms=42.5,
        )
        assert result.status == FilterStatus.SUCCESS
        assert result.count == 3
        assert result.is_success is True
        assert result.has_error is False
        assert result.is_empty is False
        assert result.execution_time_ms == 42.5

    def test_success_empty_gives_no_matches(self):
        result = FilterResult.success(
            feature_ids=[],
            layer_id="layer_2",
            expression_raw="field > 9999",
        )
        assert result.status == FilterStatus.NO_MATCHES
        assert result.is_success is True  # NO_MATCHES is still success
        assert result.is_empty is True
        assert result.count == 0

    def test_error_result(self):
        result = FilterResult.error(
            layer_id="layer_3",
            expression_raw="bad SQL",
            error_message="Syntax error at position 5",
        )
        assert result.status == FilterStatus.ERROR
        assert result.has_error is True
        assert result.is_success is False
        assert result.error_message == "Syntax error at position 5"
        assert result.count == 0

    def test_cancelled_result(self):
        result = FilterResult.cancelled(
            layer_id="layer_4",
            expression_raw="long running query",
        )
        assert result.status == FilterStatus.CANCELLED
        assert result.was_cancelled is True
        assert result.is_success is False

    def test_from_cache(self):
        result = FilterResult.from_cache(
            feature_ids=[10, 20],
            layer_id="layer_5",
            expression_raw="cached expr",
            original_execution_time_ms=100.0,
        )
        assert result.is_cached is True
        assert result.count == 2

    def test_partial_result(self):
        result = FilterResult.partial(
            feature_ids=[1],
            layer_id="layer_6",
            expression_raw="partial query",
            error_message="1/3 layers failed",
            execution_time_ms=55.0,
        )
        assert result.status == FilterStatus.PARTIAL
        assert result.is_partial is True
        assert result.error_message == "1/3 layers failed"

    def test_with_cached(self):
        original = FilterResult.success(
            feature_ids=[1, 2],
            layer_id="layer_7",
            expression_raw="expr",
        )
        cached = original.with_cached(True)
        assert cached.is_cached is True
        assert original.is_cached is False  # original unchanged

    def test_with_backend(self):
        original = FilterResult.success(
            feature_ids=[1],
            layer_id="layer_8",
            expression_raw="expr",
        )
        updated = original.with_backend("PostgreSQL")
        assert updated.backend_name == "PostgreSQL"
        assert original.backend_name == ""  # original unchanged

    def test_frozen_immutability(self):
        result = FilterResult.success(
            feature_ids=[1],
            layer_id="layer_9",
            expression_raw="expr",
        )
        with pytest.raises(AttributeError):
            result.layer_id = "changed"

    def test_feature_ids_are_frozenset(self):
        result = FilterResult.success(
            feature_ids=[3, 1, 2, 1],  # duplicates
            layer_id="layer_10",
            expression_raw="expr",
        )
        assert isinstance(result.feature_ids, frozenset)
        assert result.count == 3  # duplicates removed

    def test_str_success(self):
        result = FilterResult.success(
            feature_ids=[1, 2],
            layer_id="l",
            expression_raw="e",
            execution_time_ms=10.5,
        )
        s = str(result)
        assert "2 features" in s
        assert "10.5ms" in s

    def test_str_error(self):
        result = FilterResult.error(
            layer_id="l",
            expression_raw="e",
            error_message="boom",
        )
        assert "ERROR" in str(result)
        assert "boom" in str(result)

    def test_str_cancelled(self):
        result = FilterResult.cancelled(layer_id="l", expression_raw="e")
        assert "CANCELLED" in str(result)


# =========================================================================
# GeometryType enum
# =========================================================================

class TestGeometryType:
    """Tests for GeometryType enum and WKB conversion."""

    def test_from_qgis_wkb_type_point(self):
        assert GeometryType.from_qgis_wkb_type(1) == GeometryType.POINT

    def test_from_qgis_wkb_type_polygon(self):
        assert GeometryType.from_qgis_wkb_type(3) == GeometryType.POLYGON

    def test_from_qgis_wkb_type_multipolygon(self):
        assert GeometryType.from_qgis_wkb_type(6) == GeometryType.MULTIPOLYGON

    def test_from_qgis_wkb_type_no_geometry(self):
        assert GeometryType.from_qgis_wkb_type(100) == GeometryType.NO_GEOMETRY

    def test_from_qgis_wkb_type_unknown(self):
        assert GeometryType.from_qgis_wkb_type(999) == GeometryType.UNKNOWN

    def test_from_qgis_wkb_type_zero(self):
        assert GeometryType.from_qgis_wkb_type(0) == GeometryType.UNKNOWN


# =========================================================================
# LayerInfo entity
# =========================================================================

class TestLayerInfo:
    """Tests for LayerInfo entity (identity-based equality)."""

    def test_create_basic(self):
        info = LayerInfo.create(
            layer_id="abc123",
            name="Roads",
            provider_type=ProviderType.POSTGRESQL,
        )
        assert info.layer_id == "abc123"
        assert info.name == "Roads"
        assert info.is_postgresql is True

    def test_empty_layer_id_raises(self):
        with pytest.raises(ValueError, match="layer_id"):
            LayerInfo(
                layer_id="",
                name="Roads",
                provider_type=ProviderType.OGR,
            )

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="name"):
            LayerInfo(
                layer_id="abc",
                name="",
                provider_type=ProviderType.OGR,
            )

    def test_invalid_provider_type_raises(self):
        with pytest.raises(TypeError):
            LayerInfo(
                layer_id="abc",
                name="test",
                provider_type="not_valid",
            )

    def test_equality_by_layer_id(self):
        a = LayerInfo.create(layer_id="x", name="A", provider_type=ProviderType.OGR)
        b = LayerInfo.create(layer_id="x", name="B", provider_type=ProviderType.POSTGRESQL)
        assert a == b  # same layer_id -> equal

    def test_inequality_different_layer_id(self):
        a = LayerInfo.create(layer_id="x", name="A", provider_type=ProviderType.OGR)
        b = LayerInfo.create(layer_id="y", name="A", provider_type=ProviderType.OGR)
        assert a != b

    def test_hash_by_layer_id(self):
        a = LayerInfo.create(layer_id="x", name="A", provider_type=ProviderType.OGR)
        b = LayerInfo.create(layer_id="x", name="B", provider_type=ProviderType.POSTGRESQL)
        assert hash(a) == hash(b)
        assert len({a, b}) == 1  # same in a set

    def test_provider_checks(self):
        pg = LayerInfo.create(layer_id="1", name="t", provider_type=ProviderType.POSTGRESQL)
        sl = LayerInfo.create(layer_id="2", name="t", provider_type=ProviderType.SPATIALITE)
        ogr = LayerInfo.create(layer_id="3", name="t", provider_type=ProviderType.OGR)
        mem = LayerInfo.create(layer_id="4", name="t", provider_type=ProviderType.MEMORY)

        assert pg.is_postgresql and not pg.is_spatialite
        assert sl.is_spatialite and not sl.is_ogr
        assert ogr.is_ogr and not ogr.is_memory
        assert mem.is_memory and not mem.is_postgresql

    def test_geometry_checks(self):
        poly = LayerInfo.create(
            layer_id="1", name="t", provider_type=ProviderType.OGR,
            geometry_type=GeometryType.POLYGON,
        )
        line = LayerInfo.create(
            layer_id="2", name="t", provider_type=ProviderType.OGR,
            geometry_type=GeometryType.MULTILINE,
        )
        point = LayerInfo.create(
            layer_id="3", name="t", provider_type=ProviderType.OGR,
            geometry_type=GeometryType.POINT,
        )
        no_geom = LayerInfo.create(
            layer_id="4", name="t", provider_type=ProviderType.OGR,
            geometry_type=GeometryType.NO_GEOMETRY,
        )

        assert poly.is_polygon and poly.has_geometry
        assert line.is_line and line.is_multipart
        assert point.is_point and not point.is_multipart
        assert not no_geom.has_geometry

    def test_size_checks(self):
        small = LayerInfo.create(
            layer_id="1", name="t", provider_type=ProviderType.OGR,
            feature_count=500,
        )
        large = LayerInfo.create(
            layer_id="2", name="t", provider_type=ProviderType.OGR,
            feature_count=50000,
        )
        very_large = LayerInfo.create(
            layer_id="3", name="t", provider_type=ProviderType.OGR,
            feature_count=200000,
        )

        assert not small.is_large and not small.is_very_large
        assert large.is_large and not large.is_very_large
        assert very_large.is_large and very_large.is_very_large

    def test_qualified_table_name(self):
        with_schema = LayerInfo.create(
            layer_id="1", name="t", provider_type=ProviderType.POSTGRESQL,
            schema_name="public", table_name="roads",
        )
        without_schema = LayerInfo.create(
            layer_id="2", name="t", provider_type=ProviderType.OGR,
            table_name="roads",
        )
        no_table = LayerInfo.create(
            layer_id="3", name="my_layer", provider_type=ProviderType.OGR,
        )

        assert with_schema.qualified_table_name == "public.roads"
        assert without_schema.qualified_table_name == "roads"
        assert no_table.qualified_table_name == "my_layer"

    def test_with_feature_count(self):
        original = LayerInfo.create(
            layer_id="1", name="t", provider_type=ProviderType.OGR,
            feature_count=100,
        )
        updated = original.with_feature_count(500)
        assert updated.feature_count == 500
        assert original.feature_count == 100  # original unchanged

    def test_with_spatial_index(self):
        original = LayerInfo.create(
            layer_id="1", name="t", provider_type=ProviderType.OGR,
            has_spatial_index=False,
        )
        updated = original.with_spatial_index(True)
        assert updated.has_spatial_index is True
        assert original.has_spatial_index is False

    def test_equality_not_implemented_for_other_types(self):
        info = LayerInfo.create(layer_id="1", name="t", provider_type=ProviderType.OGR)
        assert info.__eq__("not_a_layer_info") == NotImplemented


# =========================================================================
# OptimizationConfig value object
# =========================================================================

class TestOptimizationConfig:
    """Tests for OptimizationConfig frozen dataclass."""

    def test_default_config(self):
        config = OptimizationConfig.default()
        assert config.use_materialized_views is True
        assert config.use_cache is True
        assert config.batch_size == 5000

    def test_performance_config(self):
        config = OptimizationConfig.performance()
        assert config.parallel_execution is True
        assert config.mv_feature_threshold == 5000
        assert config.cache_max_entries == 200

    def test_memory_efficient_config(self):
        config = OptimizationConfig.memory_efficient()
        assert config.use_materialized_views is False
        assert config.parallel_execution is False
        assert config.cache_max_entries == 20

    def test_disabled_config(self):
        config = OptimizationConfig.disabled()
        assert config.use_materialized_views is False
        assert config.use_cache is False
        assert config.use_spatial_index is False
        assert config.parallel_execution is False

    def test_for_layer_count_large(self):
        config = OptimizationConfig.for_layer_count(200000)
        assert config.parallel_execution is True  # performance preset

    def test_for_layer_count_medium(self):
        config = OptimizationConfig.for_layer_count(50000)
        assert config.use_materialized_views is True  # default preset

    def test_for_layer_count_small(self):
        config = OptimizationConfig.for_layer_count(500)
        assert config.use_materialized_views is False  # memory_efficient

    def test_should_use_mv(self):
        config = OptimizationConfig.default()
        assert config.should_use_mv(50000) is True
        assert config.should_use_mv(100) is False

    def test_should_use_mv_disabled(self):
        config = OptimizationConfig.disabled()
        assert config.should_use_mv(50000) is False

    def test_should_use_mv_complexity(self):
        config = OptimizationConfig.default()
        # Even with low feature count, high complexity triggers MV
        assert config.should_use_mv(100, expression_complexity=5) is True

    def test_should_use_spatial_index(self):
        config = OptimizationConfig.default()
        assert config.should_use_spatial_index(5000) is True
        assert config.should_use_spatial_index(100) is False

    def test_should_use_streaming(self):
        config = OptimizationConfig.default()
        assert config.should_use_streaming(100000) is True
        assert config.should_use_streaming(1000) is False

    def test_should_use_parallel(self):
        config = OptimizationConfig.performance()
        assert config.should_use_parallel(50000) is True
        assert config.should_use_parallel(100) is False

    def test_get_batch_count(self):
        config = OptimizationConfig(batch_size=1000)
        assert config.get_batch_count(3500) == 4
        assert config.get_batch_count(1000) == 1
        assert config.get_batch_count(0) == 0

    def test_with_cache_ttl(self):
        config = OptimizationConfig.default()
        updated = config.with_cache_ttl(60.0)
        assert updated.cache_ttl_seconds == 60.0
        assert config.cache_ttl_seconds == 300.0

    def test_with_batch_size(self):
        config = OptimizationConfig.default()
        updated = config.with_batch_size(2000)
        assert updated.batch_size == 2000

    def test_with_parallel(self):
        config = OptimizationConfig.default()
        updated = config.with_parallel(True, max_workers=8)
        assert updated.parallel_execution is True
        assert updated.max_workers == 8

    def test_with_caching(self):
        config = OptimizationConfig.default()
        updated = config.with_caching(False)
        assert updated.use_cache is False

    def test_validation_negative_threshold(self):
        with pytest.raises(ValueError, match="mv_feature_threshold"):
            OptimizationConfig(mv_feature_threshold=-1)

    def test_validation_negative_cache_ttl(self):
        with pytest.raises(ValueError, match="cache_ttl_seconds"):
            OptimizationConfig(cache_ttl_seconds=-1)

    def test_validation_zero_batch_size(self):
        with pytest.raises(ValueError, match="batch_size"):
            OptimizationConfig(batch_size=0)

    def test_validation_zero_max_workers(self):
        with pytest.raises(ValueError, match="max_workers"):
            OptimizationConfig(max_workers=0)

    def test_frozen_immutability(self):
        config = OptimizationConfig.default()
        with pytest.raises(AttributeError):
            config.batch_size = 999

    def test_str_representation(self):
        config = OptimizationConfig.default()
        s = str(config)
        assert "MV" in s
        assert "Cache" in s
        assert "SpatialIdx" in s


# =========================================================================
# ComparisonOperator enum
# =========================================================================

class TestComparisonOperator:
    """Tests for ComparisonOperator enum and evaluate()."""

    def test_symbol_property(self):
        assert ComparisonOperator.EQUAL.symbol == "="
        assert ComparisonOperator.GREATER_THAN.symbol == ">"
        assert ComparisonOperator.BETWEEN.symbol == "BETWEEN"

    def test_evaluate_equal(self):
        assert ComparisonOperator.EQUAL.evaluate(5.0, 5.0) is True
        assert ComparisonOperator.EQUAL.evaluate(5.0, 6.0) is False

    def test_evaluate_not_equal(self):
        assert ComparisonOperator.NOT_EQUAL.evaluate(5.0, 6.0) is True
        assert ComparisonOperator.NOT_EQUAL.evaluate(5.0, 5.0) is False

    def test_evaluate_greater_than(self):
        assert ComparisonOperator.GREATER_THAN.evaluate(10.0, 5.0) is True
        assert ComparisonOperator.GREATER_THAN.evaluate(5.0, 5.0) is False

    def test_evaluate_greater_equal(self):
        assert ComparisonOperator.GREATER_EQUAL.evaluate(5.0, 5.0) is True
        assert ComparisonOperator.GREATER_EQUAL.evaluate(4.0, 5.0) is False

    def test_evaluate_less_than(self):
        assert ComparisonOperator.LESS_THAN.evaluate(3.0, 5.0) is True
        assert ComparisonOperator.LESS_THAN.evaluate(5.0, 5.0) is False

    def test_evaluate_less_equal(self):
        assert ComparisonOperator.LESS_EQUAL.evaluate(5.0, 5.0) is True
        assert ComparisonOperator.LESS_EQUAL.evaluate(6.0, 5.0) is False

    def test_evaluate_between(self):
        assert ComparisonOperator.BETWEEN.evaluate(5.0, 1.0, 10.0) is True
        assert ComparisonOperator.BETWEEN.evaluate(1.0, 1.0, 10.0) is True  # inclusive
        assert ComparisonOperator.BETWEEN.evaluate(10.0, 1.0, 10.0) is True  # inclusive
        assert ComparisonOperator.BETWEEN.evaluate(0.5, 1.0, 10.0) is False

    def test_evaluate_between_without_max_raises(self):
        with pytest.raises(ValueError, match="threshold_max"):
            ComparisonOperator.BETWEEN.evaluate(5.0, 1.0)


# =========================================================================
# SamplingMethod enum
# =========================================================================

class TestSamplingMethod:
    """Tests for SamplingMethod enum values."""

    def test_all_methods(self):
        assert SamplingMethod.CENTROID.value == "centroid"
        assert SamplingMethod.POINT_ON_SURFACE.value == "point_on_surface"
        assert SamplingMethod.MEAN_UNDER_POLYGON.value == "mean_under_polygon"


# =========================================================================
# RasterSamplingCriteria value object
# =========================================================================

class TestRasterSamplingCriteria:
    """Tests for RasterSamplingCriteria frozen dataclass."""

    def test_create_basic(self):
        criteria = RasterSamplingCriteria(
            raster_uri="/tmp/dem.tif",
            vector_uri="/tmp/parcels.gpkg",
            band=1,
            threshold=100.0,
        )
        assert criteria.raster_uri == "/tmp/dem.tif"
        assert criteria.band == 1
        assert criteria.method == SamplingMethod.POINT_ON_SURFACE  # default
        assert criteria.operator == ComparisonOperator.GREATER_EQUAL  # default

    def test_band_zero_raises(self):
        with pytest.raises(ValueError, match="Band number"):
            RasterSamplingCriteria(
                raster_uri="/tmp/r.tif",
                vector_uri="/tmp/v.gpkg",
                band=0,
            )

    def test_negative_band_raises(self):
        with pytest.raises(ValueError, match="Band number"):
            RasterSamplingCriteria(
                raster_uri="/tmp/r.tif",
                vector_uri="/tmp/v.gpkg",
                band=-1,
            )

    def test_between_without_max_raises(self):
        with pytest.raises(ValueError, match="threshold_max"):
            RasterSamplingCriteria(
                raster_uri="/tmp/r.tif",
                vector_uri="/tmp/v.gpkg",
                operator=ComparisonOperator.BETWEEN,
                threshold=1.0,
                threshold_max=None,
            )

    def test_between_max_less_than_min_raises(self):
        with pytest.raises(ValueError, match="threshold_max"):
            RasterSamplingCriteria(
                raster_uri="/tmp/r.tif",
                vector_uri="/tmp/v.gpkg",
                operator=ComparisonOperator.BETWEEN,
                threshold=10.0,
                threshold_max=5.0,
            )

    def test_between_valid(self):
        criteria = RasterSamplingCriteria(
            raster_uri="/tmp/r.tif",
            vector_uri="/tmp/v.gpkg",
            operator=ComparisonOperator.BETWEEN,
            threshold=1.0,
            threshold_max=10.0,
        )
        assert criteria.threshold_max == 10.0

    def test_frozen_immutability(self):
        criteria = RasterSamplingCriteria(
            raster_uri="/tmp/r.tif",
            vector_uri="/tmp/v.gpkg",
        )
        with pytest.raises(AttributeError):
            criteria.band = 2


# =========================================================================
# RasterSamplingResult
# =========================================================================

class TestRasterSamplingResult:
    """Tests for RasterSamplingResult dataclass."""

    def test_empty_result(self):
        result = RasterSamplingResult()
        assert result.matching_count == 0
        assert result.is_success is True
        assert result.total_features == 0

    def test_result_with_matches(self):
        result = RasterSamplingResult(
            feature_values={1: 10.0, 2: 20.0, 3: None},
            matching_ids=[1, 2],
            total_features=3,
            sampled_count=2,
            nodata_count=1,
        )
        assert result.matching_count == 2
        assert result.is_success is True
        assert "2/3" in result.summary()

    def test_result_with_error(self):
        result = RasterSamplingResult(error_message="Raster not found")
        assert result.is_success is False
        assert "Error" in result.summary()

    def test_summary_format(self):
        result = RasterSamplingResult(
            matching_ids=[1],
            total_features=10,
            sampled_count=8,
            nodata_count=2,
        )
        summary = result.summary()
        assert "1/10" in summary
        assert "8 sampled" in summary
        assert "2 NoData" in summary


# =========================================================================
# SamplingStats value object
# =========================================================================

class TestSamplingStats:
    """Tests for SamplingStats frozen dataclass and from_values()."""

    def test_from_values_basic(self):
        stats = SamplingStats.from_values([1.0, 2.0, 3.0, 4.0, 5.0])
        assert stats is not None
        assert stats.min_value == 1.0
        assert stats.max_value == 5.0
        assert stats.mean_value == 3.0
        assert stats.median_value == 3.0

    def test_from_values_single(self):
        stats = SamplingStats.from_values([42.0])
        assert stats.min_value == 42.0
        assert stats.max_value == 42.0
        assert stats.mean_value == 42.0
        assert stats.std_value == 0.0
        assert stats.median_value == 42.0

    def test_from_values_empty_returns_none(self):
        assert SamplingStats.from_values([]) is None

    def test_from_values_even_count_median(self):
        stats = SamplingStats.from_values([1.0, 2.0, 3.0, 4.0])
        assert stats.median_value == 2.5  # average of 2.0 and 3.0

    def test_from_values_std_deviation(self):
        stats = SamplingStats.from_values([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        # Population std dev of [2,4,4,4,5,5,7,9] = 2.0
        assert abs(stats.std_value - 2.0) < 0.01

    def test_frozen_immutability(self):
        stats = SamplingStats(min_value=0, max_value=10, mean_value=5)
        with pytest.raises(AttributeError):
            stats.min_value = -1

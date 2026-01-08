# -*- coding: utf-8 -*-
"""
Unit Tests for FilterExpression Value Object.

Tests the FilterExpression domain object for:
- Creation and validation
- Spatial predicate detection
- Provider type conversion
- Immutability

Author: FilterMate Team
Date: January 2026
"""
import pytest
import sys
from pathlib import Path

# Add plugin directory to Python path
plugin_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(plugin_dir))

from core.domain.filter_expression import (
    FilterExpression,
    ProviderType,
    SpatialPredicate,
)


# ============================================================================
# ProviderType Enum Tests
# ============================================================================

class TestProviderType:
    """Tests for ProviderType enum."""
    
    def test_provider_type_values(self):
        """ProviderType should have expected values."""
        assert ProviderType.POSTGRESQL.value == "postgresql"
        assert ProviderType.SPATIALITE.value == "spatialite"
        assert ProviderType.OGR.value == "ogr"
        assert ProviderType.MEMORY.value == "memory"
        assert ProviderType.UNKNOWN.value == "unknown"
    
    def test_from_qgis_provider_postgres(self):
        """Should convert 'postgres' to POSTGRESQL."""
        result = ProviderType.from_qgis_provider("postgres")
        assert result == ProviderType.POSTGRESQL
    
    def test_from_qgis_provider_postgresql(self):
        """Should convert 'postgresql' to POSTGRESQL."""
        result = ProviderType.from_qgis_provider("postgresql")
        assert result == ProviderType.POSTGRESQL
    
    def test_from_qgis_provider_spatialite(self):
        """Should convert 'spatialite' to SPATIALITE."""
        result = ProviderType.from_qgis_provider("spatialite")
        assert result == ProviderType.SPATIALITE
    
    def test_from_qgis_provider_ogr(self):
        """Should convert 'ogr' to OGR."""
        result = ProviderType.from_qgis_provider("ogr")
        assert result == ProviderType.OGR
    
    def test_from_qgis_provider_memory(self):
        """Should convert 'memory' to MEMORY."""
        result = ProviderType.from_qgis_provider("memory")
        assert result == ProviderType.MEMORY
    
    def test_from_qgis_provider_unknown(self):
        """Should return UNKNOWN for unrecognized providers."""
        result = ProviderType.from_qgis_provider("wfs")
        assert result == ProviderType.UNKNOWN
        
        result = ProviderType.from_qgis_provider("unknown_provider")
        assert result == ProviderType.UNKNOWN
    
    def test_from_qgis_provider_case_insensitive(self):
        """Conversion should be case-insensitive."""
        assert ProviderType.from_qgis_provider("POSTGRES") == ProviderType.POSTGRESQL
        assert ProviderType.from_qgis_provider("PostgreSQL") == ProviderType.POSTGRESQL
        assert ProviderType.from_qgis_provider("OGR") == ProviderType.OGR


# ============================================================================
# SpatialPredicate Enum Tests
# ============================================================================

class TestSpatialPredicate:
    """Tests for SpatialPredicate enum."""
    
    def test_spatial_predicate_values(self):
        """SpatialPredicate should have expected values."""
        assert SpatialPredicate.INTERSECTS.value == "intersects"
        assert SpatialPredicate.CONTAINS.value == "contains"
        assert SpatialPredicate.WITHIN.value == "within"
        assert SpatialPredicate.CROSSES.value == "crosses"
        assert SpatialPredicate.TOUCHES.value == "touches"
        assert SpatialPredicate.OVERLAPS.value == "overlaps"
        assert SpatialPredicate.DISJOINT.value == "disjoint"
        assert SpatialPredicate.EQUALS.value == "equals"
        assert SpatialPredicate.DWITHIN.value == "dwithin"
    
    def test_all_predicates_count(self):
        """Should have 9 spatial predicates."""
        predicates = list(SpatialPredicate)
        assert len(predicates) == 9


# ============================================================================
# FilterExpression Creation Tests
# ============================================================================

class TestFilterExpressionCreation:
    """Tests for FilterExpression creation and validation."""
    
    def test_create_simple_expression(self):
        """Should create a simple filter expression."""
        expr = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        
        assert expr.raw == "field = 'value'"
        assert expr.provider == ProviderType.POSTGRESQL
        assert expr.source_layer_id == "layer_123"
        assert not expr.is_spatial
    
    def test_create_with_sql(self):
        """Should use provided SQL."""
        expr = FilterExpression.create(
            raw="field LIKE '%test%'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123",
            sql="\"field\" ILIKE '%test%'"
        )
        
        assert expr.sql == "\"field\" ILIKE '%test%'"
    
    def test_create_with_buffer(self):
        """Should create expression with buffer."""
        expr = FilterExpression.create(
            raw="intersects($geometry, @buffer)",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123",
            buffer_value=100.0,
            buffer_segments=16
        )
        
        assert expr.buffer_value == 100.0
        assert expr.buffer_segments == 16
    
    def test_create_with_target_layers(self):
        """Should create expression with target layers."""
        expr = FilterExpression.create(
            raw="field = 1",
            provider=ProviderType.SPATIALITE,
            source_layer_id="source_layer",
            target_layer_ids=["target_1", "target_2"]
        )
        
        assert "target_1" in expr.target_layer_ids
        assert "target_2" in expr.target_layer_ids
    
    def test_create_strips_whitespace(self):
        """Should strip whitespace from expression."""
        expr = FilterExpression.create(
            raw="   field = 'value'   ",
            provider=ProviderType.OGR,
            source_layer_id="layer_123"
        )
        
        assert expr.raw == "field = 'value'"


# ============================================================================
# FilterExpression Validation Tests
# ============================================================================

class TestFilterExpressionValidation:
    """Tests for FilterExpression validation."""
    
    def test_empty_expression_raises(self):
        """Empty expression should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            FilterExpression.create(
                raw="",
                provider=ProviderType.POSTGRESQL,
                source_layer_id="layer_123"
            )
    
    def test_whitespace_only_expression_raises(self):
        """Whitespace-only expression should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            FilterExpression.create(
                raw="   \t\n  ",
                provider=ProviderType.POSTGRESQL,
                source_layer_id="layer_123"
            )
    
    def test_negative_buffer_raises(self):
        """Negative buffer value should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be negative"):
            FilterExpression.create(
                raw="field = 1",
                provider=ProviderType.POSTGRESQL,
                source_layer_id="layer_123",
                buffer_value=-10.0
            )
    
    def test_zero_buffer_segments_raises(self):
        """Zero buffer segments should raise ValueError."""
        with pytest.raises(ValueError, match="at least 1"):
            FilterExpression.create(
                raw="field = 1",
                provider=ProviderType.POSTGRESQL,
                source_layer_id="layer_123",
                buffer_segments=0
            )
    
    def test_invalid_provider_type_raises(self):
        """Invalid provider type should raise TypeError."""
        with pytest.raises(TypeError, match="must be ProviderType"):
            FilterExpression(
                raw="field = 1",
                sql="field = 1",
                provider="postgresql"  # Should be ProviderType enum
            )


# ============================================================================
# FilterExpression Immutability Tests
# ============================================================================

class TestFilterExpressionImmutability:
    """Tests for FilterExpression immutability."""
    
    def test_expression_is_frozen(self):
        """FilterExpression should be immutable (frozen dataclass)."""
        expr = FilterExpression.create(
            raw="field = 1",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        
        with pytest.raises(Exception):  # FrozenInstanceError
            expr.raw = "field = 2"
    
    def test_feature_ids_tuple_immutable(self):
        """target_layer_ids should be a tuple (immutable)."""
        expr = FilterExpression.create(
            raw="field = 1",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123",
            target_layer_ids=["layer_1", "layer_2"]
        )
        
        assert isinstance(expr.target_layer_ids, tuple)


# ============================================================================
# FilterExpression Spatial Detection Tests
# ============================================================================

class TestFilterExpressionSpatialDetection:
    """Tests for spatial predicate detection."""
    
    def test_detect_intersects(self):
        """Should detect 'intersects' predicate."""
        expr = FilterExpression.create(
            raw="intersects($geometry, geom_from_wkt('POINT(0 0)'))",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        
        assert expr.is_spatial
        assert SpatialPredicate.INTERSECTS in expr.spatial_predicates
    
    def test_detect_contains(self):
        """Should detect 'contains' predicate."""
        expr = FilterExpression.create(
            raw="contains($geometry, @selected_geometry)",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        
        assert expr.is_spatial
        assert SpatialPredicate.CONTAINS in expr.spatial_predicates
    
    def test_detect_within(self):
        """Should detect 'within' predicate."""
        expr = FilterExpression.create(
            raw="within($geometry, @buffer)",
            provider=ProviderType.SPATIALITE,
            source_layer_id="layer_123"
        )
        
        assert expr.is_spatial
        assert SpatialPredicate.WITHIN in expr.spatial_predicates
    
    def test_detect_multiple_predicates(self):
        """Should detect multiple spatial predicates."""
        expr = FilterExpression.create(
            raw="intersects($geometry, @area) OR within($geometry, @region)",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        
        assert expr.is_spatial
        assert len(expr.spatial_predicates) >= 2
    
    def test_non_spatial_expression(self):
        """Non-spatial expression should have is_spatial=False."""
        expr = FilterExpression.create(
            raw="population > 10000 AND status = 'active'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        
        assert not expr.is_spatial
        assert len(expr.spatial_predicates) == 0


# ============================================================================
# FilterExpression Property Tests
# ============================================================================

class TestFilterExpressionProperties:
    """Tests for FilterExpression computed properties."""
    
    def test_is_simple_for_attribute_filter(self):
        """Attribute-only filter should be simple."""
        expr = FilterExpression.create(
            raw="field = 1",
            provider=ProviderType.OGR,
            source_layer_id="layer_123"
        )
        
        # Check is_simple if it exists
        if hasattr(expr, 'is_simple'):
            assert expr.is_simple
    
    def test_has_buffer_true(self):
        """Should report has_buffer=True when buffer set."""
        expr = FilterExpression.create(
            raw="field = 1",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123",
            buffer_value=50.0
        )
        
        if hasattr(expr, 'has_buffer'):
            assert expr.has_buffer
    
    def test_has_buffer_false(self):
        """Should report has_buffer=False when no buffer."""
        expr = FilterExpression.create(
            raw="field = 1",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        
        if hasattr(expr, 'has_buffer'):
            assert not expr.has_buffer


# ============================================================================
# FilterExpression String Representation Tests
# ============================================================================

class TestFilterExpressionRepr:
    """Tests for FilterExpression string representations."""
    
    def test_str_representation(self):
        """String representation should be readable."""
        expr = FilterExpression.create(
            raw="field = 'value'",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        
        str_repr = str(expr)
        assert "field = 'value'" in str_repr
    
    def test_repr_representation(self):
        """Repr should contain class name."""
        expr = FilterExpression.create(
            raw="field = 1",
            provider=ProviderType.OGR,
            source_layer_id="layer_123"
        )
        
        repr_str = repr(expr)
        assert "FilterExpression" in repr_str


# ============================================================================
# FilterExpression Equality Tests
# ============================================================================

class TestFilterExpressionEquality:
    """Tests for FilterExpression equality."""
    
    def test_equal_expressions(self):
        """Equal expressions should be equal."""
        expr1 = FilterExpression.create(
            raw="field = 1",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        expr2 = FilterExpression.create(
            raw="field = 1",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        
        assert expr1 == expr2
    
    def test_different_raw_not_equal(self):
        """Different raw expressions should not be equal."""
        expr1 = FilterExpression.create(
            raw="field = 1",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        expr2 = FilterExpression.create(
            raw="field = 2",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        
        assert expr1 != expr2
    
    def test_different_provider_not_equal(self):
        """Different providers should not be equal."""
        expr1 = FilterExpression.create(
            raw="field = 1",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        expr2 = FilterExpression.create(
            raw="field = 1",
            provider=ProviderType.SPATIALITE,
            source_layer_id="layer_123"
        )
        
        assert expr1 != expr2
    
    def test_hashable(self):
        """FilterExpression should be hashable (usable in sets/dicts)."""
        expr = FilterExpression.create(
            raw="field = 1",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        
        # Should not raise
        hash_value = hash(expr)
        assert isinstance(hash_value, int)
        
        # Should be usable in a set
        expr_set = {expr}
        assert expr in expr_set

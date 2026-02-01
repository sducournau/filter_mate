# -*- coding: utf-8 -*-
"""
Tests for Filter Criteria Value Objects.

Unit tests for VectorFilterCriteria and RasterFilterCriteria.
Part of the Unified Filter System (EPIC-UNIFIED-FILTER).

Author: FilterMate Team (BMAD - Amelia)
Date: February 2026
"""

import pytest
import sys
import os
from dataclasses import FrozenInstanceError

# Add the plugin root to path for direct module import (avoid QGIS dependencies)
plugin_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
if plugin_root not in sys.path:
    sys.path.insert(0, plugin_root)

# Direct import of the pure Python module (no QGIS dependencies)
from core.domain.filter_criteria import (
    LayerType,
    VectorFilterCriteria,
    RasterFilterCriteria,
    RasterPredicate,
    UnifiedFilterCriteria,
    validate_criteria,
    criteria_from_dict
)


class TestLayerType:
    """Tests for LayerType enum."""
    
    def test_vector_value(self):
        assert LayerType.VECTOR.value == "vector"
    
    def test_raster_value(self):
        assert LayerType.RASTER.value == "raster"
    
    def test_from_string_vector(self):
        assert LayerType.from_string("vector") == LayerType.VECTOR
        assert LayerType.from_string("VECTOR") == LayerType.VECTOR
        assert LayerType.from_string("Vector") == LayerType.VECTOR
    
    def test_from_string_raster(self):
        assert LayerType.from_string("raster") == LayerType.RASTER
    
    def test_from_string_invalid(self):
        with pytest.raises(ValueError) as excinfo:
            LayerType.from_string("unknown")
        assert "Unknown layer type" in str(excinfo.value)


class TestVectorFilterCriteria:
    """Tests for VectorFilterCriteria."""
    
    def test_create_with_expression(self):
        """Test creating criteria with filter expression."""
        criteria = VectorFilterCriteria(
            layer_id="layer_123",
            expression="population > 10000"
        )
        
        assert criteria.layer_id == "layer_123"
        assert criteria.expression == "population > 10000"
        assert criteria.layer_type == LayerType.VECTOR
        assert criteria.is_valid is True
    
    def test_create_with_spatial_predicate(self):
        """Test creating criteria with spatial filter."""
        criteria = VectorFilterCriteria(
            layer_id="layer_123",
            source_layer_id="source_456",
            spatial_predicate="intersects",
            buffer_value=100.0
        )
        
        assert criteria.is_valid is True
        assert criteria.is_spatial is True
        assert criteria.has_buffer is True
    
    def test_invalid_missing_layer_id(self):
        """Test that missing layer_id makes criteria invalid."""
        criteria = VectorFilterCriteria(
            layer_id="",
            expression="population > 10000"
        )
        
        assert criteria.is_valid is False
    
    def test_invalid_missing_expression_and_spatial(self):
        """Test that missing both expression and spatial makes criteria invalid."""
        criteria = VectorFilterCriteria(
            layer_id="layer_123"
        )
        
        assert criteria.is_valid is False
    
    def test_to_display_string_expression_only(self):
        """Test display string with expression only."""
        criteria = VectorFilterCriteria(
            layer_id="layer_123",
            expression="population > 10000"
        )
        
        assert criteria.to_display_string() == "population > 10000"
    
    def test_to_display_string_full(self):
        """Test display string with all parameters."""
        criteria = VectorFilterCriteria(
            layer_id="layer_123",
            expression="type = 'residential'",
            spatial_predicate="intersects",
            buffer_value=50.0,
            use_selection=True
        )
        
        display = criteria.to_display_string()
        assert "type = 'residential'" in display
        assert "[intersects]" in display
        assert "(buffer: 50.0)" in display
        assert "(selection only)" in display
    
    def test_to_display_string_empty(self):
        """Test display string with no parameters."""
        criteria = VectorFilterCriteria(layer_id="layer_123")
        assert criteria.to_display_string() == "(no filter)"
    
    def test_immutability(self):
        """Test that criteria are immutable (frozen dataclass)."""
        criteria = VectorFilterCriteria(
            layer_id="layer_123",
            expression="test"
        )
        
        with pytest.raises(FrozenInstanceError):
            criteria.expression = "new expression"
    
    def test_with_expression(self):
        """Test creating new instance with updated expression."""
        original = VectorFilterCriteria(
            layer_id="layer_123",
            expression="old"
        )
        
        new = original.with_expression("new expression")
        
        assert original.expression == "old"  # Original unchanged
        assert new.expression == "new expression"
        assert new.layer_id == original.layer_id
    
    def test_with_spatial(self):
        """Test creating new instance with spatial filter."""
        original = VectorFilterCriteria(
            layer_id="layer_123",
            expression="test"
        )
        
        new = original.with_spatial("source_456", "within", 100.0)
        
        assert new.source_layer_id == "source_456"
        assert new.spatial_predicate == "within"
        assert new.buffer_value == 100.0
        assert new.expression == "test"  # Preserved


class TestRasterFilterCriteria:
    """Tests for RasterFilterCriteria."""
    
    def test_create_with_value_range(self):
        """Test creating criteria with value range."""
        criteria = RasterFilterCriteria(
            layer_id="raster_123",
            band_index=1,
            min_value=0.0,
            max_value=100.0
        )
        
        assert criteria.layer_id == "raster_123"
        assert criteria.band_index == 1
        assert criteria.min_value == 0.0
        assert criteria.max_value == 100.0
        assert criteria.layer_type == LayerType.RASTER
        assert criteria.is_valid is True
    
    def test_create_with_mask(self):
        """Test creating criteria with vector mask."""
        criteria = RasterFilterCriteria(
            layer_id="raster_123",
            mask_layer_id="vector_456"
        )
        
        assert criteria.is_valid is True
        assert criteria.has_mask is True
    
    def test_create_with_nodata_predicate(self):
        """Test creating criteria with nodata predicate."""
        criteria = RasterFilterCriteria(
            layer_id="raster_123",
            predicate=RasterPredicate.IS_NOT_NODATA
        )
        
        assert criteria.is_valid is True
    
    def test_invalid_missing_layer_id(self):
        """Test that missing layer_id makes criteria invalid."""
        criteria = RasterFilterCriteria(
            layer_id="",
            min_value=0.0,
            max_value=100.0
        )
        
        assert criteria.is_valid is False
    
    def test_invalid_band_index_zero(self):
        """Test that band_index < 1 makes criteria invalid."""
        criteria = RasterFilterCriteria(
            layer_id="raster_123",
            band_index=0,
            min_value=0.0,
            max_value=100.0
        )
        
        assert criteria.is_valid is False
    
    def test_invalid_inverted_range(self):
        """Test that min > max makes criteria invalid."""
        criteria = RasterFilterCriteria(
            layer_id="raster_123",
            min_value=100.0,
            max_value=0.0
        )
        
        assert criteria.is_valid is False
    
    def test_invalid_no_filter_condition(self):
        """Test that no filter condition makes criteria invalid."""
        criteria = RasterFilterCriteria(
            layer_id="raster_123",
            band_index=1
            # No min_value, max_value, mask, or nodata predicate
        )
        
        assert criteria.is_valid is False
    
    def test_to_display_string_range(self):
        """Test display string with value range."""
        criteria = RasterFilterCriteria(
            layer_id="raster_123",
            band_index=2,
            min_value=500.0,
            max_value=1500.0
        )
        
        display = criteria.to_display_string()
        assert "Band 2" in display
        assert "[500.0 - 1500.0]" in display
    
    def test_to_display_string_min_only(self):
        """Test display string with min value only."""
        criteria = RasterFilterCriteria(
            layer_id="raster_123",
            min_value=100.0
        )
        
        assert "> 100.0" in criteria.to_display_string()
    
    def test_to_display_string_max_only(self):
        """Test display string with max value only."""
        criteria = RasterFilterCriteria(
            layer_id="raster_123",
            max_value=500.0
        )
        
        assert "< 500.0" in criteria.to_display_string()
    
    def test_to_display_string_nodata(self):
        """Test display string with nodata predicate."""
        criteria = RasterFilterCriteria(
            layer_id="raster_123",
            predicate=RasterPredicate.IS_NODATA
        )
        
        assert "[NoData only]" in criteria.to_display_string()
    
    def test_to_display_string_masked(self):
        """Test display string with mask."""
        criteria = RasterFilterCriteria(
            layer_id="raster_123",
            min_value=0.0,
            max_value=100.0,
            mask_layer_id="vector_456"
        )
        
        assert "(masked)" in criteria.to_display_string()
    
    def test_immutability(self):
        """Test that criteria are immutable."""
        criteria = RasterFilterCriteria(
            layer_id="raster_123",
            min_value=0.0,
            max_value=100.0
        )
        
        with pytest.raises(FrozenInstanceError):
            criteria.min_value = 50.0
    
    def test_with_range(self):
        """Test creating new instance with updated range."""
        original = RasterFilterCriteria(
            layer_id="raster_123",
            min_value=0.0,
            max_value=100.0
        )
        
        new = original.with_range(200.0, 400.0)
        
        assert original.min_value == 0.0  # Original unchanged
        assert new.min_value == 200.0
        assert new.max_value == 400.0
    
    def test_with_mask(self):
        """Test creating new instance with mask."""
        original = RasterFilterCriteria(
            layer_id="raster_123",
            min_value=0.0,
            max_value=100.0
        )
        
        new = original.with_mask("vector_456", [1, 2, 3])
        
        assert new.mask_layer_id == "vector_456"
        assert new.mask_feature_ids == (1, 2, 3)
        assert new.min_value == original.min_value  # Preserved
    
    def test_with_band(self):
        """Test creating new instance with different band."""
        original = RasterFilterCriteria(
            layer_id="raster_123",
            band_index=1,
            min_value=0.0,
            max_value=100.0
        )
        
        new = original.with_band(3)
        
        assert original.band_index == 1  # Original unchanged
        assert new.band_index == 3
        assert new.min_value == original.min_value


class TestValidateCriteria:
    """Tests for validate_criteria function."""
    
    def test_valid_vector_criteria(self):
        """Test validation of valid vector criteria."""
        criteria = VectorFilterCriteria(
            layer_id="layer_123",
            expression="test"
        )
        
        is_valid, error = validate_criteria(criteria)
        
        assert is_valid is True
        assert error == ""
    
    def test_invalid_vector_missing_layer_id(self):
        """Test validation fails for missing layer_id."""
        criteria = VectorFilterCriteria(
            layer_id="",
            expression="test"
        )
        
        is_valid, error = validate_criteria(criteria)
        
        assert is_valid is False
        assert "Layer ID is required" in error
    
    def test_invalid_vector_missing_expression(self):
        """Test validation fails for missing expression."""
        criteria = VectorFilterCriteria(
            layer_id="layer_123"
        )
        
        is_valid, error = validate_criteria(criteria)
        
        assert is_valid is False
        assert "expression or spatial predicate" in error
    
    def test_invalid_vector_spatial_without_source(self):
        """Test validation fails for spatial without source."""
        criteria = VectorFilterCriteria(
            layer_id="layer_123",
            spatial_predicate="intersects"
            # missing source_layer_id
        )
        
        is_valid, error = validate_criteria(criteria)
        
        assert is_valid is False
        assert "Source layer is required" in error
    
    def test_valid_raster_criteria(self):
        """Test validation of valid raster criteria."""
        criteria = RasterFilterCriteria(
            layer_id="raster_123",
            min_value=0.0,
            max_value=100.0
        )
        
        is_valid, error = validate_criteria(criteria)
        
        assert is_valid is True
        assert error == ""
    
    def test_invalid_raster_band_index(self):
        """Test validation fails for invalid band index."""
        criteria = RasterFilterCriteria(
            layer_id="raster_123",
            band_index=0,
            min_value=0.0,
            max_value=100.0
        )
        
        is_valid, error = validate_criteria(criteria)
        
        assert is_valid is False
        assert "Band index must be >= 1" in error
    
    def test_invalid_raster_inverted_range(self):
        """Test validation fails for inverted range."""
        criteria = RasterFilterCriteria(
            layer_id="raster_123",
            min_value=100.0,
            max_value=0.0
        )
        
        is_valid, error = validate_criteria(criteria)
        
        assert is_valid is False
        assert "Min value cannot be greater than max value" in error


class TestCriteriaFromDict:
    """Tests for criteria_from_dict function."""
    
    def test_create_vector_from_dict(self):
        """Test creating vector criteria from dict."""
        data = {
            'layer_type': 'vector',
            'layer_id': 'layer_123',
            'expression': 'population > 10000',
            'buffer_value': 50.0
        }
        
        criteria = criteria_from_dict(data)
        
        assert isinstance(criteria, VectorFilterCriteria)
        assert criteria.layer_id == 'layer_123'
        assert criteria.expression == 'population > 10000'
        assert criteria.buffer_value == 50.0
    
    def test_create_raster_from_dict(self):
        """Test creating raster criteria from dict."""
        data = {
            'layer_type': 'raster',
            'layer_id': 'raster_123',
            'band_index': 2,
            'min_value': 100.0,
            'max_value': 500.0,
            'predicate': 'within_range'
        }
        
        criteria = criteria_from_dict(data)
        
        assert isinstance(criteria, RasterFilterCriteria)
        assert criteria.layer_id == 'raster_123'
        assert criteria.band_index == 2
        assert criteria.min_value == 100.0
        assert criteria.max_value == 500.0
        assert criteria.predicate == RasterPredicate.WITHIN_RANGE
    
    def test_missing_layer_type_raises(self):
        """Test that missing layer_type raises ValueError."""
        data = {
            'layer_id': 'layer_123',
            'expression': 'test'
        }
        
        with pytest.raises(ValueError) as excinfo:
            criteria_from_dict(data)
        
        assert "'layer_type' key is required" in str(excinfo.value)
    
    def test_invalid_layer_type_raises(self):
        """Test that invalid layer_type raises ValueError."""
        data = {
            'layer_type': 'unknown_type',
            'layer_id': 'layer_123'
        }
        
        with pytest.raises(ValueError) as excinfo:
            criteria_from_dict(data)
        
        assert "Unknown layer type" in str(excinfo.value)
    
    def test_raster_with_mask_feature_ids(self):
        """Test creating raster criteria with mask feature IDs."""
        data = {
            'layer_type': 'raster',
            'layer_id': 'raster_123',
            'mask_layer_id': 'vector_456',
            'mask_feature_ids': [1, 2, 3]
        }
        
        criteria = criteria_from_dict(data)
        
        assert criteria.mask_feature_ids == (1, 2, 3)  # Converted to tuple


class TestProtocolCompliance:
    """Tests for FilterCriteria protocol compliance."""
    
    def test_vector_criteria_is_filter_criteria(self):
        """Test that VectorFilterCriteria complies with protocol."""
        from core.domain.filter_criteria import FilterCriteria
        
        criteria = VectorFilterCriteria(
            layer_id="layer_123",
            expression="test"
        )
        
        # Check protocol compliance via isinstance with runtime_checkable
        assert isinstance(criteria, FilterCriteria)
    
    def test_raster_criteria_is_filter_criteria(self):
        """Test that RasterFilterCriteria complies with protocol."""
        from core.domain.filter_criteria import FilterCriteria
        
        criteria = RasterFilterCriteria(
            layer_id="raster_123",
            min_value=0.0,
            max_value=100.0
        )
        
        assert isinstance(criteria, FilterCriteria)


class TestUnifiedFilterCriteriaType:
    """Tests for UnifiedFilterCriteria type alias."""
    
    def test_vector_is_unified(self):
        """Test that VectorFilterCriteria is UnifiedFilterCriteria."""
        criteria: UnifiedFilterCriteria = VectorFilterCriteria(
            layer_id="layer_123",
            expression="test"
        )
        
        assert criteria.layer_type == LayerType.VECTOR
    
    def test_raster_is_unified(self):
        """Test that RasterFilterCriteria is UnifiedFilterCriteria."""
        criteria: UnifiedFilterCriteria = RasterFilterCriteria(
            layer_id="raster_123",
            min_value=0.0,
            max_value=100.0
        )
        
        assert criteria.layer_type == LayerType.RASTER

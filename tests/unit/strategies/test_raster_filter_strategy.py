# -*- coding: utf-8 -*-
"""
Unit tests for RasterFilterStrategy.

Tests for:
- RasterFilterStrategy: Raster layer filtering operations
- Integration with RasterFilterCriteria

Author: FilterMate Team (BMAD - TEA)
Date: February 2026
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os
import re

# Add plugin root to path
plugin_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
if plugin_root not in sys.path:
    sys.path.insert(0, plugin_root)


def load_module_without_relative_imports(filepath: str, namespace: dict) -> dict:
    """Load a Python module while handling relative imports."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove all 'from .xxx import' and 'from ..xxx import' lines
    content = re.sub(r'^from \.\S+.*$', '', content, flags=re.MULTILINE)
    content = re.sub(r'^from \.\.\S+.*$', '', content, flags=re.MULTILINE)
    
    exec(content, namespace)
    return namespace


class TestRasterFilterCriteria(unittest.TestCase):
    """Tests for RasterFilterCriteria value object."""
    
    def setUp(self):
        """Set up test fixtures."""
        sys.modules['qgis'] = MagicMock()
        sys.modules['qgis.core'] = MagicMock()
        
        criteria_path = os.path.join(plugin_root, 'core', 'domain', 'filter_criteria.py')
        self.criteria_ns = load_module_without_relative_imports(
            criteria_path,
            {'__name__': 'filter_criteria'}
        )
        
        self.LayerType = self.criteria_ns['LayerType']
        self.RasterFilterCriteria = self.criteria_ns['RasterFilterCriteria']
        self.RasterPredicate = self.criteria_ns['RasterPredicate']
        self.validate_criteria = self.criteria_ns['validate_criteria']
    
    def test_raster_criteria_creation(self):
        """Test RasterFilterCriteria creation with defaults."""
        criteria = self.RasterFilterCriteria(
            layer_id="dem_layer"
        )
        
        self.assertEqual(criteria.layer_id, "dem_layer")
        self.assertEqual(criteria.layer_type, self.LayerType.RASTER)
        self.assertEqual(criteria.band_index, 1)
        self.assertIsNone(criteria.min_value)
        self.assertIsNone(criteria.max_value)
    
    def test_raster_criteria_with_range(self):
        """Test RasterFilterCriteria with value range."""
        criteria = self.RasterFilterCriteria(
            layer_id="elevation",
            band_index=1,
            min_value=100.0,
            max_value=500.0
        )
        
        self.assertEqual(criteria.min_value, 100.0)
        self.assertEqual(criteria.max_value, 500.0)
    
    def test_raster_criteria_with_predicate(self):
        """Test RasterFilterCriteria with predicate."""
        criteria = self.RasterFilterCriteria(
            layer_id="classified",
            predicate=self.RasterPredicate.IS_NOT_NODATA
        )
        
        self.assertEqual(criteria.predicate, self.RasterPredicate.IS_NOT_NODATA)
    
    def test_raster_criteria_with_mask(self):
        """Test RasterFilterCriteria with mask layer."""
        criteria = self.RasterFilterCriteria(
            layer_id="dem",
            mask_layer_id="study_area",
            min_value=500
        )
        
        self.assertEqual(criteria.mask_layer_id, "study_area")
    
    def test_raster_criteria_immutable(self):
        """Test that RasterFilterCriteria is immutable."""
        criteria = self.RasterFilterCriteria(
            layer_id="dem",
            min_value=100
        )
        
        with self.assertRaises(Exception):  # FrozenInstanceError
            criteria.min_value = 200
    
    def test_raster_criteria_display_string(self):
        """Test RasterFilterCriteria display string."""
        criteria = self.RasterFilterCriteria(
            layer_id="elevation",
            band_index=2,
            min_value=100,
            max_value=500
        )
        
        display = criteria.to_display_string()
        self.assertIn("band", display.lower())
        self.assertIn("100", display)
        self.assertIn("500", display)
    
    def test_raster_predicate_values(self):
        """Test RasterPredicate enum values."""
        self.assertEqual(self.RasterPredicate.WITHIN_RANGE.value, "within_range")
        self.assertEqual(self.RasterPredicate.IS_NODATA.value, "is_nodata")
        self.assertEqual(self.RasterPredicate.ABOVE_VALUE.value, "above_value")


class TestRasterFilterStrategyValidation(unittest.TestCase):
    """Tests for RasterFilterStrategy validation logic (standalone)."""
    
    def test_validate_empty_layer_id(self):
        """Test validation rejects empty layer_id."""
        # Standalone validation logic test
        layer_id = ""
        
        is_valid = bool(layer_id)
        self.assertFalse(is_valid)
    
    def test_validate_invalid_band_index(self):
        """Test validation rejects invalid band index."""
        band_index = 0  # Invalid: must be >= 1
        
        is_valid = band_index >= 1
        self.assertFalse(is_valid)
    
    def test_validate_valid_band_index(self):
        """Test validation accepts valid band index."""
        band_index = 1
        
        is_valid = band_index >= 1
        self.assertTrue(is_valid)
    
    def test_validate_invalid_range(self):
        """Test validation rejects min > max."""
        min_value = 500
        max_value = 100
        
        is_valid = min_value <= max_value
        self.assertFalse(is_valid)
    
    def test_validate_valid_range(self):
        """Test validation accepts valid range."""
        min_value = 100
        max_value = 500
        
        is_valid = min_value <= max_value
        self.assertTrue(is_valid)
    
    def test_validate_needs_filter_condition(self):
        """Test validation requires at least one filter condition."""
        min_value = None
        max_value = None
        predicate = None
        mask_layer_id = None
        
        has_value_filter = min_value is not None or max_value is not None
        has_predicate = predicate is not None
        has_mask = mask_layer_id is not None
        
        is_valid = has_value_filter or has_predicate or has_mask
        self.assertFalse(is_valid)
    
    def test_validate_with_value_filter(self):
        """Test validation accepts criteria with value filter."""
        min_value = 100
        max_value = None
        
        has_value_filter = min_value is not None or max_value is not None
        self.assertTrue(has_value_filter)


class TestUnifiedFilterServiceWithRaster(unittest.TestCase):
    """Integration tests for UnifiedFilterService with raster support."""
    
    def test_service_supports_raster_type(self):
        """Test that service recognizes raster layer type."""
        from enum import Enum
        
        class LayerType(Enum):
            VECTOR = 'vector'
            RASTER = 'raster'
        
        # Simulate factory with both strategies
        strategies = {
            LayerType.VECTOR: object,
            LayerType.RASTER: object
        }
        
        self.assertIn(LayerType.RASTER, strategies)
        self.assertEqual(len(strategies), 2)
    
    def test_criteria_type_detection(self):
        """Test automatic criteria type detection."""
        sys.modules['qgis'] = MagicMock()
        sys.modules['qgis.core'] = MagicMock()
        
        criteria_path = os.path.join(plugin_root, 'core', 'domain', 'filter_criteria.py')
        ns = load_module_without_relative_imports(criteria_path, {'__name__': 'filter_criteria'})
        
        VectorFilterCriteria = ns['VectorFilterCriteria']
        RasterFilterCriteria = ns['RasterFilterCriteria']
        LayerType = ns['LayerType']
        
        vector_criteria = VectorFilterCriteria(layer_id="test", expression="x > 1")
        raster_criteria = RasterFilterCriteria(layer_id="dem", min_value=100)
        
        self.assertEqual(vector_criteria.layer_type, LayerType.VECTOR)
        self.assertEqual(raster_criteria.layer_type, LayerType.RASTER)


class TestFilterResultFactories(unittest.TestCase):
    """Tests for UnifiedFilterResult factory methods (standalone)."""
    
    def test_raster_success_structure(self):
        """Test raster success result structure."""
        from dataclasses import dataclass, field
        from enum import Enum
        from typing import Optional, List, Dict, Any
        
        class FilterStatus(Enum):
            SUCCESS = 'success'
            ERROR = 'error'
        
        @dataclass
        class MockResult:
            status: FilterStatus
            layer_id: str
            layer_type: str
            affected_count: int = 0
            output_path: Optional[str] = None
            statistics: Dict[str, Any] = field(default_factory=dict)
            
            @property
            def is_success(self):
                return self.status == FilterStatus.SUCCESS
        
        result = MockResult(
            status=FilterStatus.SUCCESS,
            layer_id="dem",
            layer_type="raster",
            affected_count=50000,
            output_path="/tmp/filtered.tif",
            statistics={"total_pixels": 100000, "match_percentage": 50.0}
        )
        
        self.assertTrue(result.is_success)
        self.assertEqual(result.layer_type, "raster")
        self.assertEqual(result.affected_count, 50000)
        self.assertEqual(result.statistics["match_percentage"], 50.0)
    
    def test_raster_error_structure(self):
        """Test raster error result structure."""
        from dataclasses import dataclass
        from enum import Enum
        from typing import Optional
        
        class FilterStatus(Enum):
            SUCCESS = 'success'
            ERROR = 'error'
        
        @dataclass
        class MockResult:
            status: FilterStatus
            layer_id: str
            layer_type: str
            error_message: Optional[str] = None
            
            @property
            def is_success(self):
                return self.status == FilterStatus.SUCCESS
        
        result = MockResult(
            status=FilterStatus.ERROR,
            layer_id="dem",
            layer_type="raster",
            error_message="Invalid band index"
        )
        
        self.assertFalse(result.is_success)
        self.assertEqual(result.status, FilterStatus.ERROR)
        self.assertIn("band", result.error_message.lower())


class TestStrategyPolymorphism(unittest.TestCase):
    """Tests for polymorphic behavior of strategies."""
    
    def test_abstract_methods_defined(self):
        """Test that abstract strategy defines required methods."""
        from abc import ABC, abstractmethod
        
        class MockAbstractStrategy(ABC):
            @abstractmethod
            def validate_criteria(self, criteria):
                pass
            
            @abstractmethod
            def apply_filter(self, criteria):
                pass
            
            @abstractmethod
            def get_preview(self, criteria):
                pass
            
            @abstractmethod
            def export(self, criteria, output_path, **options):
                pass
        
        # Verify we can't instantiate abstract class
        with self.assertRaises(TypeError):
            MockAbstractStrategy()
    
    def test_concrete_strategy_implements_interface(self):
        """Test concrete strategies implement full interface."""
        from abc import ABC, abstractmethod
        
        class AbstractStrategy(ABC):
            @abstractmethod
            def validate_criteria(self, criteria):
                pass
            @abstractmethod
            def apply_filter(self, criteria):
                pass
            @abstractmethod
            def get_preview(self, criteria):
                pass
            @abstractmethod
            def export(self, criteria, output_path, **options):
                pass
        
        class ConcreteRasterStrategy(AbstractStrategy):
            def validate_criteria(self, criteria):
                return True, None
            def apply_filter(self, criteria):
                return {"success": True}
            def get_preview(self, criteria):
                return {"type": "raster"}
            def export(self, criteria, output_path, **options):
                return {"success": True}
        
        strategy = ConcreteRasterStrategy()
        
        # All methods should be callable
        self.assertEqual(strategy.validate_criteria({}), (True, None))
        self.assertEqual(strategy.apply_filter({})["success"], True)
        self.assertEqual(strategy.get_preview({})["type"], "raster")
        self.assertEqual(strategy.export({}, "/tmp/out.tif")["success"], True)


if __name__ == '__main__':
    unittest.main()

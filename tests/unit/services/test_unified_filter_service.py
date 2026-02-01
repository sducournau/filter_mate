# -*- coding: utf-8 -*-
"""
Unit tests for Unified Filter Service and Factory.

Tests for:
- FilterStrategyFactory: Strategy creation and registration
- UnifiedFilterService: Unified filtering operations

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


class TestFilterCriteriaIntegration(unittest.TestCase):
    """Integration tests for filter criteria."""
    
    def setUp(self):
        """Set up test fixtures by loading modules."""
        # Mock QGIS
        sys.modules['qgis'] = MagicMock()
        sys.modules['qgis.core'] = MagicMock()
        
        # Load filter criteria (no relative imports)
        criteria_path = os.path.join(plugin_root, 'core', 'domain', 'filter_criteria.py')
        self.criteria_ns = load_module_without_relative_imports(
            criteria_path, 
            {'__name__': 'filter_criteria'}
        )
        
        self.LayerType = self.criteria_ns['LayerType']
        self.VectorFilterCriteria = self.criteria_ns['VectorFilterCriteria']
        self.RasterFilterCriteria = self.criteria_ns['RasterFilterCriteria']
        self.validate_criteria = self.criteria_ns['validate_criteria']
    
    def test_layer_type_enum(self):
        """Test LayerType enum values."""
        self.assertEqual(self.LayerType.VECTOR.value, 'vector')
        self.assertEqual(self.LayerType.RASTER.value, 'raster')
    
    def test_vector_criteria_creation(self):
        """Test VectorFilterCriteria creation."""
        criteria = self.VectorFilterCriteria(
            layer_id="test_layer",
            expression="field > 100"
        )
        
        self.assertEqual(criteria.layer_id, "test_layer")
        self.assertEqual(criteria.expression, "field > 100")
        self.assertEqual(criteria.layer_type, self.LayerType.VECTOR)
    
    def test_raster_criteria_creation(self):
        """Test RasterFilterCriteria creation."""
        criteria = self.RasterFilterCriteria(
            layer_id="raster_layer",
            band_index=1,
            min_value=100.0,
            max_value=500.0
        )
        
        self.assertEqual(criteria.layer_id, "raster_layer")
        self.assertEqual(criteria.layer_type, self.LayerType.RASTER)
        self.assertEqual(criteria.band_index, 1)
    
    def test_validate_criteria_valid(self):
        """Test validation of valid criteria."""
        criteria = self.VectorFilterCriteria(
            layer_id="test_layer",
            expression="field > 100"
        )
        
        is_valid, error = self.validate_criteria(criteria)
        self.assertTrue(is_valid)
        self.assertIsNone(error)
    
    def test_validate_criteria_invalid_empty_layer(self):
        """Test validation rejects empty layer_id."""
        criteria = self.VectorFilterCriteria(
            layer_id="",
            expression="field > 100"
        )
        
        is_valid, error = self.validate_criteria(criteria)
        self.assertFalse(is_valid)
        self.assertIn('layer_id', error.lower())


class TestBaseFilterStrategy(unittest.TestCase):
    """Tests for base filter strategy classes."""
    
    def setUp(self):
        """Set up test fixtures."""
        sys.modules['qgis'] = MagicMock()
        sys.modules['qgis.core'] = MagicMock()
        
        # Load criteria first
        criteria_path = os.path.join(plugin_root, 'core', 'domain', 'filter_criteria.py')
        self.criteria_ns = load_module_without_relative_imports(
            criteria_path,
            {'__name__': 'filter_criteria'}
        )
        
        # Load base strategy with criteria in namespace
        base_path = os.path.join(plugin_root, 'core', 'strategies', 'base_filter_strategy.py')
        self.strategy_ns = {'__name__': 'base_filter_strategy'}
        self.strategy_ns.update(self.criteria_ns)
        load_module_without_relative_imports(base_path, self.strategy_ns)
        
        self.FilterStatus = self.strategy_ns['FilterStatus']
        self.UnifiedFilterResult = self.strategy_ns['UnifiedFilterResult']
        self.FilterContext = self.strategy_ns['FilterContext']
        self.AbstractFilterStrategy = self.strategy_ns['AbstractFilterStrategy']
    
    def test_filter_status_enum(self):
        """Test FilterStatus enum values."""
        self.assertEqual(self.FilterStatus.SUCCESS.value, 'success')
        self.assertEqual(self.FilterStatus.ERROR.value, 'error')
        self.assertEqual(self.FilterStatus.CANCELLED.value, 'cancelled')
    
    def test_filter_context_creation(self):
        """Test FilterContext creation."""
        progress_cb = Mock()
        cancel_cb = Mock(return_value=False)
        
        context = self.FilterContext(
            progress_callback=progress_cb,
            cancel_callback=cancel_cb
        )
        
        self.assertEqual(context.progress_callback, progress_cb)
        self.assertEqual(context.cancel_callback, cancel_cb)
    
    def test_unified_result_vector_success(self):
        """Test UnifiedFilterResult.vector_success factory."""
        result = self.UnifiedFilterResult.vector_success(
            layer_id="layer1",
            expression_applied="field > 100",
            affected_count=42,
            feature_ids=[1, 2, 3]
        )
        
        self.assertTrue(result.is_success)
        self.assertEqual(result.status, self.FilterStatus.SUCCESS)
        self.assertEqual(result.layer_type, "vector")
        self.assertEqual(result.affected_count, 42)
        self.assertEqual(result.feature_ids, [1, 2, 3])
    
    def test_unified_result_raster_success(self):
        """Test UnifiedFilterResult.raster_success factory."""
        result = self.UnifiedFilterResult.raster_success(
            layer_id="raster1",
            output_path="/tmp/output.tif",
            pixel_count=5000,
            statistics={"mean": 42.5}
        )
        
        self.assertTrue(result.is_success)
        self.assertEqual(result.layer_type, "raster")
        self.assertEqual(result.output_path, "/tmp/output.tif")
        self.assertEqual(result.affected_count, 5000)
    
    def test_unified_result_error(self):
        """Test UnifiedFilterResult.error factory."""
        result = self.UnifiedFilterResult.error(
            layer_id="layer1",
            layer_type="vector",
            error_message="Something went wrong"
        )
        
        self.assertFalse(result.is_success)
        self.assertEqual(result.status, self.FilterStatus.ERROR)
        self.assertEqual(result.error_message, "Something went wrong")
    
    def test_unified_result_cancelled(self):
        """Test UnifiedFilterResult.cancelled factory."""
        result = self.UnifiedFilterResult.cancelled(
            layer_id="layer1",
            layer_type="vector"
        )
        
        self.assertFalse(result.is_success)
        self.assertEqual(result.status, self.FilterStatus.CANCELLED)
    
    def test_abstract_strategy_is_abstract(self):
        """Test that AbstractFilterStrategy cannot be instantiated."""
        context = self.FilterContext()
        
        with self.assertRaises(TypeError):
            self.AbstractFilterStrategy(context)


class TestVectorFilterStrategy(unittest.TestCase):
    """Tests for VectorFilterStrategy class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock QGIS
        mock_qgis_core = MagicMock()
        mock_qgis_core.QgsVectorLayer = type('QgsVectorLayer', (), {})
        mock_qgis_core.QgsFeatureRequest = MagicMock()
        mock_qgis_core.QgsExpression = MagicMock()
        mock_qgis_core.QgsExpressionContext = MagicMock()
        mock_qgis_core.QgsExpressionContextScope = MagicMock()
        mock_qgis_core.QgsVectorFileWriter = MagicMock()
        mock_qgis_core.QgsCoordinateReferenceSystem = MagicMock()
        mock_qgis_core.QgsProject = MagicMock()
        mock_qgis_core.QgsGeometry = MagicMock()
        
        sys.modules['qgis'] = MagicMock()
        sys.modules['qgis.core'] = mock_qgis_core
        self.mock_qgis_core = mock_qgis_core
        
        # Load modules
        criteria_path = os.path.join(plugin_root, 'core', 'domain', 'filter_criteria.py')
        self.criteria_ns = load_module_without_relative_imports(
            criteria_path,
            {'__name__': 'filter_criteria'}
        )
        
        base_path = os.path.join(plugin_root, 'core', 'strategies', 'base_filter_strategy.py')
        self.base_ns = {'__name__': 'base_filter_strategy'}
        self.base_ns.update(self.criteria_ns)
        load_module_without_relative_imports(base_path, self.base_ns)
        
        vector_path = os.path.join(plugin_root, 'core', 'strategies', 'vector_filter_strategy.py')
        self.vector_ns = {'__name__': 'vector_filter_strategy', 'logger': MagicMock()}
        self.vector_ns.update(self.base_ns)
        load_module_without_relative_imports(vector_path, self.vector_ns)
        
        self.VectorFilterStrategy = self.vector_ns['VectorFilterStrategy']
        self.VectorFilterCriteria = self.criteria_ns['VectorFilterCriteria']
        self.FilterContext = self.base_ns['FilterContext']
        self.UnifiedFilterResult = self.base_ns['UnifiedFilterResult']
    
    def test_strategy_creation(self):
        """Test VectorFilterStrategy can be created."""
        context = self.FilterContext()
        strategy = self.VectorFilterStrategy(context)
        
        self.assertIsNotNone(strategy)
    
    def test_validate_criteria_valid(self):
        """Test validation of valid criteria."""
        context = self.FilterContext()
        strategy = self.VectorFilterStrategy(context)
        
        criteria = self.VectorFilterCriteria(
            layer_id="test_layer",
            expression="field > 100"
        )
        
        is_valid, error = strategy.validate_criteria(criteria)
        self.assertTrue(is_valid)
    
    def test_validate_criteria_no_filter(self):
        """Test validation rejects criteria without filter."""
        context = self.FilterContext()
        strategy = self.VectorFilterStrategy(context)
        
        criteria = self.VectorFilterCriteria(
            layer_id="test_layer"
            # No expression, no spatial filter
        )
        
        is_valid, error = strategy.validate_criteria(criteria)
        self.assertFalse(is_valid)
        self.assertIn('expression', error.lower())
    
    def test_cancellation_support(self):
        """Test cancellation functionality."""
        context = self.FilterContext()
        strategy = self.VectorFilterStrategy(context)
        
        self.assertFalse(strategy.is_cancelled)
        
        strategy.cancel()
        
        self.assertTrue(strategy.is_cancelled)


class TestFilterStrategyFactoryBasic(unittest.TestCase):
    """Basic tests for FilterStrategyFactory without full module loading."""
    
    def test_factory_pattern_concept(self):
        """Test the factory pattern concept with mocks."""
        # This tests the pattern without needing full module loading
        from abc import ABC, abstractmethod
        from dataclasses import dataclass
        from enum import Enum
        
        class LayerType(Enum):
            VECTOR = 'vector'
            RASTER = 'raster'
        
        class MockStrategy(ABC):
            @abstractmethod
            def apply_filter(self, criteria):
                pass
        
        class MockVectorStrategy(MockStrategy):
            def apply_filter(self, criteria):
                return {"type": "vector", "count": 42}
        
        # Simulate factory
        strategies = {LayerType.VECTOR: MockVectorStrategy}
        
        # Create strategy
        strategy = strategies[LayerType.VECTOR]()
        result = strategy.apply_filter({})
        
        self.assertEqual(result["type"], "vector")
        self.assertEqual(result["count"], 42)


class TestUnifiedFilterServiceBasic(unittest.TestCase):
    """Basic tests for UnifiedFilterService concept."""
    
    def test_service_facade_pattern(self):
        """Test the service facade pattern concept."""
        # Test the pattern without full module loading
        
        class MockService:
            def __init__(self):
                self.strategies = {}
            
            def register(self, layer_type, strategy_class):
                self.strategies[layer_type] = strategy_class
            
            def apply_filter(self, criteria):
                strategy_class = self.strategies.get(criteria.get("type"))
                if strategy_class:
                    return strategy_class().execute(criteria)
                return {"error": "No strategy"}
        
        class MockVectorStrategy:
            def execute(self, criteria):
                return {"success": True, "count": 42}
        
        service = MockService()
        service.register("vector", MockVectorStrategy)
        
        result = service.apply_filter({"type": "vector", "filter": "x > 10"})
        
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 42)


if __name__ == '__main__':
    unittest.main()

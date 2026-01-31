# -*- coding: utf-8 -*-
"""
Tests for RasterFilterService - Bidirectional Raster↔Vector Filtering

FilterMate - Dual QToolBox Architecture
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRasterPredicate(unittest.TestCase):
    """Test RasterPredicate enum and predicate checking logic."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock QGIS imports
        self.qgis_mock = MagicMock()
        sys.modules['qgis'] = self.qgis_mock
        sys.modules['qgis.core'] = self.qgis_mock.core
        sys.modules['qgis.PyQt'] = self.qgis_mock.PyQt
        sys.modules['qgis.PyQt.QtCore'] = self.qgis_mock.PyQt.QtCore
        
        # Import after mocking
        from core.services.raster_filter_service import RasterPredicate
        self.RasterPredicate = RasterPredicate
    
    def test_predicate_values(self):
        """Test that all predicate values are defined."""
        predicates = [
            'WITHIN_RANGE',
            'OUTSIDE_RANGE', 
            'ABOVE_VALUE',
            'BELOW_VALUE',
            'EQUALS_VALUE',
            'IS_NODATA',
            'IS_NOT_NODATA'
        ]
        for p in predicates:
            self.assertTrue(hasattr(self.RasterPredicate, p), f"Missing predicate: {p}")


class TestSamplingMethod(unittest.TestCase):
    """Test SamplingMethod enum."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.qgis_mock = MagicMock()
        sys.modules['qgis'] = self.qgis_mock
        sys.modules['qgis.core'] = self.qgis_mock.core
        sys.modules['qgis.PyQt'] = self.qgis_mock.PyQt
        sys.modules['qgis.PyQt.QtCore'] = self.qgis_mock.PyQt.QtCore
        
        from core.services.raster_filter_service import SamplingMethod
        self.SamplingMethod = SamplingMethod
    
    def test_sampling_methods(self):
        """Test that all sampling methods are defined."""
        methods = ['CENTROID', 'MEAN', 'MIN', 'MAX', 'MEDIAN', 'ZONAL_STATS']
        for m in methods:
            self.assertTrue(hasattr(self.SamplingMethod, m), f"Missing method: {m}")


class TestRasterOperation(unittest.TestCase):
    """Test RasterOperation enum."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.qgis_mock = MagicMock()
        sys.modules['qgis'] = self.qgis_mock
        sys.modules['qgis.core'] = self.qgis_mock.core
        sys.modules['qgis.PyQt'] = self.qgis_mock.PyQt
        sys.modules['qgis.PyQt.QtCore'] = self.qgis_mock.PyQt.QtCore
        
        from core.services.raster_filter_service import RasterOperation
        self.RasterOperation = RasterOperation
    
    def test_raster_operations(self):
        """Test that all raster operations are defined."""
        operations = ['CLIP', 'MASK_OUTSIDE', 'MASK_INSIDE', 'ZONAL_STATS']
        for op in operations:
            self.assertTrue(hasattr(self.RasterOperation, op), f"Missing operation: {op}")


class TestPredicateChecking(unittest.TestCase):
    """Test the _check_predicate method logic."""
    
    def setUp(self):
        """Set up test fixtures with mocked QGIS."""
        self.qgis_mock = MagicMock()
        sys.modules['qgis'] = self.qgis_mock
        sys.modules['qgis.core'] = self.qgis_mock.core
        sys.modules['qgis.PyQt'] = self.qgis_mock.PyQt
        sys.modules['qgis.PyQt.QtCore'] = self.qgis_mock.PyQt.QtCore
        
        from core.services.raster_filter_service import RasterFilterService, RasterPredicate
        self.service = RasterFilterService()
        self.RasterPredicate = RasterPredicate
    
    def test_within_range_true(self):
        """Test WITHIN_RANGE predicate returns True for value in range."""
        result = self.service._check_predicate(
            value=50.0,
            predicate=self.RasterPredicate.WITHIN_RANGE,
            min_val=0.0,
            max_val=100.0
        )
        self.assertTrue(result)
    
    def test_within_range_false(self):
        """Test WITHIN_RANGE predicate returns False for value outside range."""
        result = self.service._check_predicate(
            value=150.0,
            predicate=self.RasterPredicate.WITHIN_RANGE,
            min_val=0.0,
            max_val=100.0
        )
        self.assertFalse(result)
    
    def test_within_range_boundary(self):
        """Test WITHIN_RANGE predicate includes boundary values."""
        result_min = self.service._check_predicate(
            value=0.0,
            predicate=self.RasterPredicate.WITHIN_RANGE,
            min_val=0.0,
            max_val=100.0
        )
        result_max = self.service._check_predicate(
            value=100.0,
            predicate=self.RasterPredicate.WITHIN_RANGE,
            min_val=0.0,
            max_val=100.0
        )
        self.assertTrue(result_min)
        self.assertTrue(result_max)
    
    def test_outside_range_true(self):
        """Test OUTSIDE_RANGE predicate returns True for value outside range."""
        result = self.service._check_predicate(
            value=150.0,
            predicate=self.RasterPredicate.OUTSIDE_RANGE,
            min_val=0.0,
            max_val=100.0
        )
        self.assertTrue(result)
    
    def test_outside_range_false(self):
        """Test OUTSIDE_RANGE predicate returns False for value in range."""
        result = self.service._check_predicate(
            value=50.0,
            predicate=self.RasterPredicate.OUTSIDE_RANGE,
            min_val=0.0,
            max_val=100.0
        )
        self.assertFalse(result)
    
    def test_above_value_true(self):
        """Test ABOVE_VALUE predicate returns True for value above threshold."""
        result = self.service._check_predicate(
            value=150.0,
            predicate=self.RasterPredicate.ABOVE_VALUE,
            min_val=100.0,
            max_val=100.0
        )
        self.assertTrue(result)
    
    def test_above_value_false(self):
        """Test ABOVE_VALUE predicate returns False for value at or below threshold."""
        result = self.service._check_predicate(
            value=100.0,
            predicate=self.RasterPredicate.ABOVE_VALUE,
            min_val=100.0,
            max_val=100.0
        )
        self.assertFalse(result)
    
    def test_below_value_true(self):
        """Test BELOW_VALUE predicate returns True for value below threshold."""
        result = self.service._check_predicate(
            value=50.0,
            predicate=self.RasterPredicate.BELOW_VALUE,
            min_val=0.0,
            max_val=100.0
        )
        self.assertTrue(result)
    
    def test_below_value_false(self):
        """Test BELOW_VALUE predicate returns False for value at or above threshold."""
        result = self.service._check_predicate(
            value=100.0,
            predicate=self.RasterPredicate.BELOW_VALUE,
            min_val=0.0,
            max_val=100.0
        )
        self.assertFalse(result)
    
    def test_equals_value_true(self):
        """Test EQUALS_VALUE predicate returns True for equal value."""
        result = self.service._check_predicate(
            value=100.0,
            predicate=self.RasterPredicate.EQUALS_VALUE,
            min_val=100.0,
            max_val=100.0,
            tolerance=0.001
        )
        self.assertTrue(result)
    
    def test_equals_value_with_tolerance(self):
        """Test EQUALS_VALUE predicate respects tolerance."""
        result = self.service._check_predicate(
            value=100.0005,
            predicate=self.RasterPredicate.EQUALS_VALUE,
            min_val=100.0,
            max_val=100.0,
            tolerance=0.001
        )
        self.assertTrue(result)
    
    def test_equals_value_false(self):
        """Test EQUALS_VALUE predicate returns False for different value."""
        result = self.service._check_predicate(
            value=101.0,
            predicate=self.RasterPredicate.EQUALS_VALUE,
            min_val=100.0,
            max_val=100.0,
            tolerance=0.001
        )
        self.assertFalse(result)
    
    def test_is_nodata_true(self):
        """Test IS_NODATA predicate returns True for None value."""
        result = self.service._check_predicate(
            value=None,
            predicate=self.RasterPredicate.IS_NODATA,
            min_val=0.0,
            max_val=100.0
        )
        self.assertTrue(result)
    
    def test_is_nodata_with_nodata_value(self):
        """Test IS_NODATA predicate detects nodata value."""
        result = self.service._check_predicate(
            value=-9999.0,
            predicate=self.RasterPredicate.IS_NODATA,
            min_val=0.0,
            max_val=100.0,
            nodata_value=-9999.0
        )
        self.assertTrue(result)
    
    def test_is_not_nodata_true(self):
        """Test IS_NOT_NODATA predicate returns True for valid value."""
        result = self.service._check_predicate(
            value=50.0,
            predicate=self.RasterPredicate.IS_NOT_NODATA,
            min_val=0.0,
            max_val=100.0
        )
        self.assertTrue(result)
    
    def test_is_not_nodata_false(self):
        """Test IS_NOT_NODATA predicate returns False for nodata value."""
        result = self.service._check_predicate(
            value=None,
            predicate=self.RasterPredicate.IS_NOT_NODATA,
            min_val=0.0,
            max_val=100.0
        )
        self.assertFalse(result)
    
    def test_nodata_values_excluded_from_range_predicates(self):
        """Test that nodata values are excluded from range predicates."""
        # None value should return False for WITHIN_RANGE
        result = self.service._check_predicate(
            value=None,
            predicate=self.RasterPredicate.WITHIN_RANGE,
            min_val=0.0,
            max_val=100.0
        )
        self.assertFalse(result)
        
        # Nodata value should return False for WITHIN_RANGE
        result = self.service._check_predicate(
            value=-9999.0,
            predicate=self.RasterPredicate.WITHIN_RANGE,
            min_val=0.0,
            max_val=100.0,
            nodata_value=-9999.0
        )
        self.assertFalse(result)


class TestBuildIdExpression(unittest.TestCase):
    """Test the _build_id_expression method."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.qgis_mock = MagicMock()
        sys.modules['qgis'] = self.qgis_mock
        sys.modules['qgis.core'] = self.qgis_mock.core
        sys.modules['qgis.PyQt'] = self.qgis_mock.PyQt
        sys.modules['qgis.PyQt.QtCore'] = self.qgis_mock.PyQt.QtCore
        
        from core.services.raster_filter_service import RasterFilterService
        self.service = RasterFilterService()
    
    def test_empty_ids_returns_false_expression(self):
        """Test that empty feature IDs returns a 'match nothing' expression."""
        mock_layer = MagicMock()
        mock_layer.primaryKeyAttributes.return_value = []
        
        result = self.service._build_id_expression([], mock_layer)
        self.assertEqual(result, "1=0")
    
    def test_small_id_set_with_pk(self):
        """Test expression building with primary key field."""
        mock_layer = MagicMock()
        mock_layer.primaryKeyAttributes.return_value = [0]
        mock_field = MagicMock()
        mock_field.name.return_value = "gid"
        mock_layer.fields.return_value.field.return_value = mock_field
        
        result = self.service._build_id_expression([1, 2, 3], mock_layer)
        self.assertIn("gid", result)
        self.assertIn("IN", result)
        self.assertIn("1, 2, 3", result)
    
    def test_small_id_set_without_pk(self):
        """Test expression building without primary key (uses $id)."""
        mock_layer = MagicMock()
        mock_layer.primaryKeyAttributes.return_value = []
        
        result = self.service._build_id_expression([1, 2, 3], mock_layer)
        self.assertIn("$id", result)
        self.assertIn("IN", result)


class TestRasterFilterRequest(unittest.TestCase):
    """Test RasterFilterRequest dataclass."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.qgis_mock = MagicMock()
        sys.modules['qgis'] = self.qgis_mock
        sys.modules['qgis.core'] = self.qgis_mock.core
        sys.modules['qgis.PyQt'] = self.qgis_mock.PyQt
        sys.modules['qgis.PyQt.QtCore'] = self.qgis_mock.PyQt.QtCore
        
        from core.services.raster_filter_service import (
            RasterFilterRequest, RasterPredicate, SamplingMethod
        )
        self.RasterFilterRequest = RasterFilterRequest
        self.RasterPredicate = RasterPredicate
        self.SamplingMethod = SamplingMethod
    
    def test_create_request_with_defaults(self):
        """Test creating a request with default values."""
        mock_raster = MagicMock()
        mock_vector = MagicMock()
        
        request = self.RasterFilterRequest(
            raster_layer=mock_raster,
            vector_layer=mock_vector
        )
        
        self.assertEqual(request.raster_layer, mock_raster)
        self.assertEqual(request.vector_layer, mock_vector)
        self.assertEqual(request.band, 1)
        self.assertEqual(request.predicate, self.RasterPredicate.WITHIN_RANGE)
        self.assertEqual(request.sampling_method, self.SamplingMethod.CENTROID)
    
    def test_create_request_with_custom_values(self):
        """Test creating a request with custom values."""
        mock_raster = MagicMock()
        mock_vector = MagicMock()
        
        request = self.RasterFilterRequest(
            raster_layer=mock_raster,
            vector_layer=mock_vector,
            band=2,
            min_value=10.0,
            max_value=50.0,
            predicate=self.RasterPredicate.OUTSIDE_RANGE,
            sampling_method=self.SamplingMethod.MEAN
        )
        
        self.assertEqual(request.band, 2)
        self.assertEqual(request.min_value, 10.0)
        self.assertEqual(request.max_value, 50.0)
        self.assertEqual(request.predicate, self.RasterPredicate.OUTSIDE_RANGE)
        self.assertEqual(request.sampling_method, self.SamplingMethod.MEAN)


class TestVectorFilterRequest(unittest.TestCase):
    """Test VectorFilterRequest dataclass."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.qgis_mock = MagicMock()
        sys.modules['qgis'] = self.qgis_mock
        sys.modules['qgis.core'] = self.qgis_mock.core
        sys.modules['qgis.PyQt'] = self.qgis_mock.PyQt
        sys.modules['qgis.PyQt.QtCore'] = self.qgis_mock.PyQt.QtCore
        
        from core.services.raster_filter_service import VectorFilterRequest, RasterOperation
        self.VectorFilterRequest = VectorFilterRequest
        self.RasterOperation = RasterOperation
    
    def test_create_request_with_defaults(self):
        """Test creating a request with default values."""
        mock_vector = MagicMock()
        mock_raster = MagicMock()
        
        request = self.VectorFilterRequest(
            vector_layer=mock_vector,
            raster_layer=mock_raster
        )
        
        self.assertEqual(request.vector_layer, mock_vector)
        self.assertEqual(request.raster_layer, mock_raster)
        self.assertEqual(request.operation, self.RasterOperation.CLIP)
        self.assertTrue(request.use_selected_features)
    
    def test_create_request_with_feature_ids(self):
        """Test creating a request with specific feature IDs."""
        mock_vector = MagicMock()
        mock_raster = MagicMock()
        
        request = self.VectorFilterRequest(
            vector_layer=mock_vector,
            raster_layer=mock_raster,
            feature_ids=[1, 5, 10],
            operation=self.RasterOperation.MASK_OUTSIDE
        )
        
        self.assertEqual(request.feature_ids, [1, 5, 10])
        self.assertEqual(request.operation, self.RasterOperation.MASK_OUTSIDE)


class TestRasterFilterResult(unittest.TestCase):
    """Test RasterFilterResult dataclass."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.qgis_mock = MagicMock()
        sys.modules['qgis'] = self.qgis_mock
        sys.modules['qgis.core'] = self.qgis_mock.core
        sys.modules['qgis.PyQt'] = self.qgis_mock.PyQt
        sys.modules['qgis.PyQt.QtCore'] = self.qgis_mock.PyQt.QtCore
        
        from core.services.raster_filter_service import RasterFilterResult
        self.RasterFilterResult = RasterFilterResult
    
    def test_successful_result(self):
        """Test creating a successful result."""
        result = self.RasterFilterResult(
            success=True,
            matched_count=100,
            total_count=500,
            expression="$id IN (1, 2, 3)"
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.matched_count, 100)
        self.assertEqual(result.total_count, 500)
        self.assertIsNone(result.error_message)
    
    def test_failed_result(self):
        """Test creating a failed result."""
        result = self.RasterFilterResult(
            success=False,
            error_message="Raster layer not valid"
        )
        
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Raster layer not valid")


if __name__ == '__main__':
    unittest.main()

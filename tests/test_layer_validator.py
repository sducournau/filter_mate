"""
Tests for LayerValidator

Unit tests for the extracted layer validation module.
Part of MIG-024 (God Class reduction).
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, PropertyMock


# Create a mock QgsVectorLayer class for testing
class MockQgsVectorLayer:
    """Mock class to simulate QgsVectorLayer for testing."""
    pass


class TestLayerValidator(unittest.TestCase):
    """Tests for LayerValidator class."""
    
    def _create_validator(self, postgresql_available=True):
        """Create validator with optional PostgreSQL flag."""
        from adapters.layer_validator import LayerValidator
        return LayerValidator(postgresql_available=postgresql_available)
    
    def _create_mock_layer(self, provider_type='ogr', name='TestLayer'):
        """Create a mock layer that behaves like QgsVectorLayer."""
        mock = MagicMock()
        mock.__class__ = MockQgsVectorLayer
        mock.providerType = Mock(return_value=provider_type)
        mock.name = Mock(return_value=name)
        mock.isValid = Mock(return_value=True)
        return mock
    
    def test_init_creates_validator(self):
        """Test validator initialization."""
        validator = self._create_validator()
        self.assertIsNotNone(validator)
        self.assertTrue(validator._postgresql_available)
        
    def test_init_without_postgresql(self):
        """Test validator initialization without PostgreSQL."""
        validator = self._create_validator(postgresql_available=False)
        self.assertFalse(validator._postgresql_available)
        
    @patch('adapters.layer_validator.is_sip_deleted', return_value=False)
    @patch('adapters.layer_validator.is_valid_layer', return_value=True)
    @patch('adapters.layer_validator.is_layer_source_available', return_value=True)
    @patch('adapters.layer_validator.QgsVectorLayer', MockQgsVectorLayer)
    def test_filter_usable_layers_all_valid(self, mock_source, mock_valid, mock_sip):
        """Test filter_usable_layers with all valid layers."""
        validator = self._create_validator()
        
        mock_layer1 = self._create_mock_layer('ogr', 'Layer1')
        mock_layer2 = self._create_mock_layer('spatialite', 'Layer2')
        
        result = validator.filter_usable_layers([mock_layer1, mock_layer2])
        
        self.assertEqual(len(result), 2)
        
    def test_filter_usable_layers_empty(self):
        """Test filter_usable_layers with empty list."""
        validator = self._create_validator()
        
        result = validator.filter_usable_layers([])
        
        self.assertEqual(result, [])
        
    def test_filter_usable_layers_none(self):
        """Test filter_usable_layers with None."""
        validator = self._create_validator()
        
        result = validator.filter_usable_layers(None)
        
        self.assertEqual(result, [])
        
    @patch('adapters.layer_validator.is_sip_deleted', return_value=True)
    def test_filter_usable_layers_deleted_object(self, mock_sip):
        """Test filter_usable_layers filters deleted C++ objects."""
        validator = self._create_validator()
        
        mock_layer = MagicMock()
        
        result = validator.filter_usable_layers([mock_layer])
        
        self.assertEqual(len(result), 0)
        
    @patch('adapters.layer_validator.is_sip_deleted', return_value=False)
    @patch('adapters.layer_validator.QgsVectorLayer', MockQgsVectorLayer)
    def test_filter_usable_layers_non_vector(self, mock_sip):
        """Test filter_usable_layers filters non-vector layers."""
        validator = self._create_validator()
        
        # Not a QgsVectorLayer instance - use different class
        RasterLayer = type('RasterLayer', (), {})
        mock_layer = MagicMock()
        mock_layer.__class__ = RasterLayer
        mock_layer.name = Mock(return_value='RasterLayer')
        
        result = validator.filter_usable_layers([mock_layer])
        
        self.assertEqual(len(result), 0)
        
    @patch('adapters.layer_validator.is_sip_deleted', return_value=False)
    @patch('adapters.layer_validator.is_valid_layer', return_value=True)
    @patch('adapters.layer_validator.QgsVectorLayer', MockQgsVectorLayer)
    def test_filter_usable_layers_postgres_always_included(self, mock_valid, mock_sip):
        """Test that PostgreSQL layers are always included if valid."""
        validator = self._create_validator()
        
        mock_layer = self._create_mock_layer('postgres', 'PostgresLayer')
        
        result = validator.filter_usable_layers([mock_layer])
        
        # PostgreSQL layer should be included even without source check
        self.assertEqual(len(result), 1)
        
    def test_is_layer_usable_returns_tuple(self):
        """Test is_layer_usable returns (bool, reason) tuple."""
        validator = self._create_validator()
        
        with patch('adapters.layer_validator.is_sip_deleted', return_value=True):
            is_usable, reason = validator.is_layer_usable(MagicMock())
        
        self.assertFalse(is_usable)
        self.assertIsNotNone(reason)
        
    @patch('adapters.layer_validator.is_sip_deleted', return_value=False)
    @patch('adapters.layer_validator.QgsVectorLayer', MockQgsVectorLayer)
    def test_is_vector_layer_true(self, mock_sip):
        """Test is_vector_layer returns True for vector layers."""
        validator = self._create_validator()
        
        mock_layer = self._create_mock_layer('ogr', 'VectorLayer')
        
        result = validator.is_vector_layer(mock_layer)
        
        self.assertTrue(result)
        
    @patch('adapters.layer_validator.is_sip_deleted', return_value=True)
    def test_is_vector_layer_deleted(self, mock_sip):
        """Test is_vector_layer returns False for deleted objects."""
        validator = self._create_validator()
        
        result = validator.is_vector_layer(MagicMock())
        
        self.assertFalse(result)
        
    @patch('adapters.layer_validator.is_sip_deleted', return_value=False)
    @patch('adapters.layer_validator.QgsVectorLayer', MockQgsVectorLayer)
    def test_is_postgres_layer(self, mock_sip):
        """Test is_postgres_layer detection."""
        validator = self._create_validator()
        
        mock_layer = self._create_mock_layer('postgres', 'PostgresLayer')
        self.assertTrue(validator.is_postgres_layer(mock_layer))
        
        mock_layer2 = self._create_mock_layer('spatialite', 'SpatialiteLayer')
        self.assertFalse(validator.is_postgres_layer(mock_layer2))
        
    @patch('adapters.layer_validator.is_sip_deleted', return_value=False)
    @patch('adapters.layer_validator.QgsVectorLayer', MockQgsVectorLayer)
    def test_is_spatialite_layer(self, mock_sip):
        """Test is_spatialite_layer detection."""
        validator = self._create_validator()
        
        mock_layer = self._create_mock_layer('spatialite', 'SpatialiteLayer')
        self.assertTrue(validator.is_spatialite_layer(mock_layer))
        
        mock_layer2 = self._create_mock_layer('postgres', 'PostgresLayer')
        self.assertFalse(validator.is_spatialite_layer(mock_layer2))
        
    @patch('adapters.layer_validator.is_sip_deleted', return_value=False)
    @patch('adapters.layer_validator.QgsVectorLayer', MockQgsVectorLayer)
    def test_get_provider_type_normalizes_postgres(self, mock_sip):
        """Test get_provider_type normalizes 'postgres' to 'postgresql'."""
        validator = self._create_validator()
        
        mock_layer = self._create_mock_layer('postgres', 'PostgresLayer')
        
        result = validator.get_provider_type(mock_layer)
        
        self.assertEqual(result, 'postgresql')
        
    @patch('adapters.layer_validator.is_sip_deleted', return_value=False)
    @patch('adapters.layer_validator.QgsVectorLayer', MockQgsVectorLayer)
    def test_get_provider_type_other(self, mock_sip):
        """Test get_provider_type for other providers."""
        validator = self._create_validator()
        
        mock_layer = self._create_mock_layer('ogr', 'OgrLayer')
        
        result = validator.get_provider_type(mock_layer)
        
        self.assertEqual(result, 'ogr')
        
    def test_get_provider_type_unknown(self):
        """Test get_provider_type returns 'unknown' for non-vector."""
        validator = self._create_validator()
        
        with patch('adapters.layer_validator.is_sip_deleted', return_value=True):
            result = validator.get_provider_type(MagicMock())
        
        self.assertEqual(result, 'unknown')


class TestLayerValidatorIntegration(unittest.TestCase):
    """Integration tests for layer validator module."""
    
    def test_module_imports(self):
        """Test that module can be imported."""
        try:
            from adapters.layer_validator import LayerValidator
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import layer_validator module: {e}")
            
    def test_validator_interface_complete(self):
        """Test that LayerValidator has all required methods."""
        from adapters.layer_validator import LayerValidator
        
        required_methods = [
            'filter_usable_layers',
            'is_layer_usable',
            'is_vector_layer',
            'is_postgres_layer',
            'is_spatialite_layer',
            'get_provider_type'
        ]
        
        for method in required_methods:
            self.assertTrue(
                hasattr(LayerValidator, method),
                f"Missing method: {method}"
            )


if __name__ == '__main__':
    unittest.main()

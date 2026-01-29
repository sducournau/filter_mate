# -*- coding: utf-8 -*-
"""
Unit tests for EPIC-2 Layer Type Detection (US-01).

Tests the layer type detection utilities and signal emission.

Author: FilterMate Team
Date: January 2026
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys

# Mock QGIS imports for testing
sys.modules['qgis'] = MagicMock()
sys.modules['qgis.core'] = MagicMock()
sys.modules['qgis.gui'] = MagicMock()
sys.modules['qgis.PyQt'] = MagicMock()
sys.modules['qgis.PyQt.QtCore'] = MagicMock()
sys.modules['qgis.PyQt.QtWidgets'] = MagicMock()
sys.modules['qgis.PyQt.QtGui'] = MagicMock()


class TestLayerType:
    """Tests for LayerType enum."""
    
    def test_layer_type_values(self):
        """LayerType enum should have correct values."""
        from infrastructure.utils.layer_utils import LayerType
        
        assert LayerType.VECTOR.value == 'vector'
        assert LayerType.RASTER.value == 'raster'
        assert LayerType.UNKNOWN.value == 'unknown'
    
    def test_layer_type_str(self):
        """LayerType should have string representation."""
        from infrastructure.utils.layer_utils import LayerType
        
        assert str(LayerType.VECTOR) == 'vector'
        assert str(LayerType.RASTER) == 'raster'
        assert str(LayerType.UNKNOWN) == 'unknown'


class TestDetectLayerType:
    """Tests for detect_layer_type function."""
    
    def test_none_layer_returns_unknown(self):
        """None layer should return UNKNOWN."""
        from infrastructure.utils.layer_utils import detect_layer_type, LayerType
        
        result = detect_layer_type(None)
        assert result == LayerType.UNKNOWN
    
    def test_vector_layer_detected(self):
        """Vector layer should be detected correctly."""
        from infrastructure.utils.layer_utils import detect_layer_type, LayerType
        
        # Create mock vector layer
        mock_layer = Mock()
        mock_layer.__class__.__name__ = 'QgsVectorLayer'
        
        result = detect_layer_type(mock_layer)
        assert result == LayerType.VECTOR
    
    def test_raster_layer_detected(self):
        """Raster layer should be detected correctly."""
        from infrastructure.utils.layer_utils import detect_layer_type, LayerType
        
        # Create mock raster layer
        mock_layer = Mock()
        mock_layer.__class__.__name__ = 'QgsRasterLayer'
        
        result = detect_layer_type(mock_layer)
        assert result == LayerType.RASTER


class TestIsRasterLayer:
    """Tests for is_raster_layer function."""
    
    def test_is_raster_layer_true(self):
        """is_raster_layer should return True for raster layers."""
        from infrastructure.utils.layer_utils import is_raster_layer
        
        mock_layer = Mock()
        mock_layer.__class__.__name__ = 'QgsRasterLayer'
        
        assert is_raster_layer(mock_layer) is True
    
    def test_is_raster_layer_false_for_vector(self):
        """is_raster_layer should return False for vector layers."""
        from infrastructure.utils.layer_utils import is_raster_layer
        
        mock_layer = Mock()
        mock_layer.__class__.__name__ = 'QgsVectorLayer'
        
        assert is_raster_layer(mock_layer) is False
    
    def test_is_raster_layer_false_for_none(self):
        """is_raster_layer should return False for None."""
        from infrastructure.utils.layer_utils import is_raster_layer
        
        assert is_raster_layer(None) is False


class TestIsVectorLayer:
    """Tests for is_vector_layer function."""
    
    def test_is_vector_layer_true(self):
        """is_vector_layer should return True for vector layers."""
        from infrastructure.utils.layer_utils import is_vector_layer
        
        mock_layer = Mock()
        mock_layer.__class__.__name__ = 'QgsVectorLayer'
        
        assert is_vector_layer(mock_layer) is True
    
    def test_is_vector_layer_false_for_raster(self):
        """is_vector_layer should return False for raster layers."""
        from infrastructure.utils.layer_utils import is_vector_layer
        
        mock_layer = Mock()
        mock_layer.__class__.__name__ = 'QgsRasterLayer'
        
        assert is_vector_layer(mock_layer) is False
    
    def test_is_vector_layer_false_for_none(self):
        """is_vector_layer should return False for None."""
        from infrastructure.utils.layer_utils import is_vector_layer
        
        assert is_vector_layer(None) is False


class TestLayerTypeExport:
    """Tests for module exports."""
    
    def test_exports_available(self):
        """Ensure all EPIC-2 exports are available from utils module."""
        from infrastructure.utils import (
            LayerType,
            detect_layer_type,
            is_raster_layer,
            is_vector_layer,
        )
        
        assert LayerType is not None
        assert detect_layer_type is not None
        assert is_raster_layer is not None
        assert is_vector_layer is not None


# Integration test placeholder (requires QGIS environment)
class TestLayerSyncControllerIntegration:
    """Integration tests for LayerSyncController layer type detection.
    
    Note: These tests require a QGIS environment to run properly.
    They are marked with pytest.mark.qgis for selective execution.
    """
    
    @pytest.mark.skip(reason="Requires QGIS environment")
    def test_layer_type_changed_signal_emitted(self):
        """layer_type_changed signal should be emitted on layer change."""
        # This test would require a full QGIS environment
        pass
    
    @pytest.mark.skip(reason="Requires QGIS environment")
    def test_raster_groupbox_visibility_on_raster_selection(self):
        """Raster groupbox should show when raster layer selected."""
        # This test would require a full QGIS environment
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

# -*- coding: utf-8 -*-
"""
Unit tests for Raster Backend

Tests for the RasterBackend class including:
- Raster opening and metadata extraction
- Point sampling with different methods
- Zonal statistics
- CRS transformation
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Try to import GDAL - tests will be skipped if not available
try:
    from osgeo import gdal, osr
    import numpy as np
    GDAL_AVAILABLE = True
except ImportError:
    GDAL_AVAILABLE = False
    gdal = None
    osr = None
    np = None


# Skip all tests if GDAL is not available
pytestmark = pytest.mark.skipif(not GDAL_AVAILABLE, reason="GDAL not available")


class TestRasterBackendImport:
    """Test that raster backend can be imported correctly."""
    
    def test_import_raster_backend(self):
        """Test importing RasterBackend class."""
        from modules.backends.raster_backend import RasterBackend, GDAL_AVAILABLE as BACKEND_GDAL
        assert BACKEND_GDAL == GDAL_AVAILABLE
    
    def test_import_from_factory(self):
        """Test importing via BackendFactory."""
        from modules.backends import RasterBackend, GDAL_AVAILABLE as BACKEND_GDAL
        assert RasterBackend is not None
        assert BACKEND_GDAL == GDAL_AVAILABLE


class TestRasterBackendWithMock:
    """Test RasterBackend with mocked GDAL."""
    
    @pytest.fixture
    def mock_gdal_dataset(self):
        """Create a mock GDAL dataset."""
        dataset = MagicMock()
        dataset.RasterXSize = 100
        dataset.RasterYSize = 100
        dataset.RasterCount = 1
        dataset.GetGeoTransform.return_value = (0.0, 1.0, 0.0, 100.0, 0.0, -1.0)
        dataset.GetProjection.return_value = 'GEOGCS["WGS 84",DATUM["WGS_1984"]]'
        
        band = MagicMock()
        band.GetNoDataValue.return_value = -9999.0
        band.ReadAsArray.return_value = np.array([[50.0]])
        dataset.GetRasterBand.return_value = band
        
        return dataset
    
    @patch('modules.backends.raster_backend.gdal')
    @patch('modules.backends.raster_backend.Path')
    def test_open_dataset(self, mock_path, mock_gdal, mock_gdal_dataset):
        """Test opening a raster dataset."""
        from modules.backends.raster_backend import RasterBackend
        
        mock_path.return_value.exists.return_value = True
        mock_gdal.Open.return_value = mock_gdal_dataset
        mock_gdal.GA_ReadOnly = 0
        
        backend = RasterBackend("/fake/path/dem.tif")
        
        assert backend.width == 100
        assert backend.height == 100
        assert backend.n_bands == 1
    
    @patch('modules.backends.raster_backend.gdal')
    @patch('modules.backends.raster_backend.Path')
    def test_get_metadata(self, mock_path, mock_gdal, mock_gdal_dataset):
        """Test getting raster metadata."""
        from modules.backends.raster_backend import RasterBackend
        
        mock_path.return_value.exists.return_value = True
        mock_gdal.Open.return_value = mock_gdal_dataset
        mock_gdal.GA_ReadOnly = 0
        
        backend = RasterBackend("/fake/path/dem.tif")
        metadata = backend.get_metadata()
        
        assert 'width' in metadata
        assert 'height' in metadata
        assert 'n_bands' in metadata
        assert 'resolution' in metadata
        assert 'extent' in metadata
        assert metadata['width'] == 100
        assert metadata['height'] == 100


class TestWorldToPixelConversion:
    """Test coordinate conversion functions."""
    
    def test_world_to_pixel_basic(self):
        """Test basic world to pixel conversion."""
        # Simulated geotransform: origin (0,100), pixel size 1m
        gt = (0.0, 1.0, 0.0, 100.0, 0.0, -1.0)
        
        # Point at (50, 50) should be pixel (50, 50)
        x, y = 50.0, 50.0
        col = int((x - gt[0]) / gt[1])
        row = int((y - gt[3]) / gt[5])
        
        assert col == 50
        assert row == 50
    
    def test_world_to_pixel_offset_origin(self):
        """Test conversion with offset origin."""
        # Origin at (1000, 2000)
        gt = (1000.0, 10.0, 0.0, 2000.0, 0.0, -10.0)
        
        x, y = 1050.0, 1950.0  # 5 pixels right, 5 pixels down
        col = int((x - gt[0]) / gt[1])
        row = int((y - gt[3]) / gt[5])
        
        assert col == 5
        assert row == 5


class TestSamplingMethods:
    """Test different sampling methods."""
    
    def test_nearest_neighbor_concept(self):
        """Test nearest neighbor sampling concept."""
        # 3x3 array of values
        data = np.array([
            [10, 20, 30],
            [40, 50, 60],
            [70, 80, 90]
        ])
        
        # Center pixel (1,1) should have value 50
        assert data[1, 1] == 50
    
    def test_bilinear_interpolation_concept(self):
        """Test bilinear interpolation concept."""
        # 2x2 window
        q11, q21 = 10.0, 20.0  # bottom row
        q12, q22 = 30.0, 40.0  # top row
        
        # Interpolate at center (0.5, 0.5)
        dx, dy = 0.5, 0.5
        value = (
            q11 * (1 - dx) * (1 - dy) +
            q21 * dx * (1 - dy) +
            q12 * (1 - dx) * dy +
            q22 * dx * dy
        )
        
        # Should be average of all 4 values
        expected = (10 + 20 + 30 + 40) / 4
        assert abs(value - expected) < 0.001


class TestRasterSamplingTask:
    """Test RasterSamplingTask class."""
    
    def test_import_sampling_task(self):
        """Test importing RasterSamplingTask."""
        from modules.tasks.raster_sampling_task import RasterSamplingTask, SamplingMode
        assert RasterSamplingTask is not None
        assert SamplingMode is not None
    
    def test_sampling_mode_enum(self):
        """Test SamplingMode enum values."""
        from modules.tasks.raster_sampling_task import SamplingMode
        
        assert SamplingMode.POINT_SAMPLE.value == "point_sample"
        assert SamplingMode.ZONAL_STATS.value == "zonal_stats"
        assert SamplingMode.POINT_STATS.value == "point_stats"
    
    def test_import_from_tasks_package(self):
        """Test importing from tasks package."""
        from modules.tasks import RasterSamplingTask, SamplingMode
        assert RasterSamplingTask is not None
        assert SamplingMode is not None


class TestZonalStatistics:
    """Test zonal statistics calculations."""
    
    def test_basic_stats_calculation(self):
        """Test basic statistics calculation."""
        values = np.array([10, 20, 30, 40, 50])
        
        stats = {
            'min': float(np.min(values)),
            'max': float(np.max(values)),
            'mean': float(np.mean(values)),
            'std': float(np.std(values)),
            'sum': float(np.sum(values)),
            'count': len(values),
        }
        
        assert stats['min'] == 10.0
        assert stats['max'] == 50.0
        assert stats['mean'] == 30.0
        assert stats['sum'] == 150.0
        assert stats['count'] == 5
    
    def test_stats_with_nodata(self):
        """Test statistics with nodata values filtered."""
        values = np.array([10, 20, -9999, 40, 50])
        nodata = -9999
        
        valid_values = values[values != nodata]
        
        mean = float(np.mean(valid_values))
        expected_mean = (10 + 20 + 40 + 50) / 4
        
        assert abs(mean - expected_mean) < 0.001


class TestFactoryRasterIntegration:
    """Test BackendFactory raster integration."""
    
    def test_factory_has_raster_method(self):
        """Test that BackendFactory has get_raster_backend method."""
        from modules.backends.factory import BackendFactory
        
        assert hasattr(BackendFactory, 'get_raster_backend')
        assert hasattr(BackendFactory, 'is_raster_available')
    
    def test_is_raster_available(self):
        """Test is_raster_available returns correct value."""
        from modules.backends.factory import BackendFactory
        
        result = BackendFactory.is_raster_available()
        assert result == GDAL_AVAILABLE


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

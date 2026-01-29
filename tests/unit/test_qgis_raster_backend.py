"""
Unit tests for QGIS Raster Backend.

EPIC-2: Raster Integration
US-03: QGIS Raster Backend

These tests use mocking to avoid QGIS runtime dependency.
Integration tests with real QGIS layers are in tests/integration/.
"""
import unittest
from unittest.mock import MagicMock, Mock, patch

# Mock QGIS imports before importing the backend
import sys
sys.modules['qgis'] = MagicMock()
sys.modules['qgis.core'] = MagicMock()

from core.ports.raster_port import (
    RasterDataType,
    RasterRendererType,
    HistogramBinMethod,
    RasterStats,
    BandStatistics,
    HistogramData,
    PixelIdentifyResult,
    TransparencySettings,
)


class TestQGISRasterBackendImport(unittest.TestCase):
    """Tests for QGIS Raster Backend import availability."""

    def test_backend_available_flag(self):
        """Test that backend availability flag exists."""
        from adapters.backends import QGIS_RASTER_BACKEND_AVAILABLE
        # Should be True or False depending on QGIS availability
        self.assertIsInstance(QGIS_RASTER_BACKEND_AVAILABLE, bool)

    def test_backend_class_exported(self):
        """Test that QGISRasterBackend is exported."""
        from adapters.backends import QGISRasterBackend
        # May be None if QGIS not available
        # Just verify import doesn't fail


class TestDataTypeMappingFunctions(unittest.TestCase):
    """Tests for data type mapping helper functions."""

    def test_raster_data_type_values(self):
        """Test all RasterDataType enum values are accessible."""
        expected_types = [
            'UNKNOWN', 'BYTE', 'INT16', 'UINT16', 'INT32', 'UINT32',
            'FLOAT32', 'FLOAT64', 'CINT16', 'CINT32', 'CFLOAT32', 'CFLOAT64'
        ]
        for dtype in expected_types:
            self.assertTrue(hasattr(RasterDataType, dtype))

    def test_renderer_type_values(self):
        """Test all RasterRendererType enum values are accessible."""
        expected_types = [
            'UNKNOWN', 'SINGLEBAND_GRAY', 'SINGLEBAND_PSEUDOCOLOR',
            'MULTIBAND_COLOR', 'PALETTED', 'HILLSHADE', 'CONTOUR'
        ]
        for rtype in expected_types:
            self.assertTrue(hasattr(RasterRendererType, rtype))


class TestRasterStatsDataclass(unittest.TestCase):
    """Tests for RasterStats dataclass properties."""

    def setUp(self):
        """Create test RasterStats instance."""
        self.band_stats = BandStatistics(
            band_number=1,
            min_value=0.0,
            max_value=255.0,
            mean=127.5,
            std_dev=50.0,
            no_data_value=-9999.0,
            valid_pixel_count=9000,
            total_pixel_count=10000,
            sum=1147500.0,
            data_type=RasterDataType.BYTE
        )
        
        self.raster_stats = RasterStats(
            layer_id="test_layer",
            layer_name="Test Raster",
            width=100,
            height=100,
            band_count=1,
            crs_auth_id="EPSG:4326",
            pixel_size_x=0.01,
            pixel_size_y=0.01,
            extent=(0.0, 0.0, 1.0, 1.0),
            band_statistics=(self.band_stats,),
            renderer_type=RasterRendererType.SINGLEBAND_GRAY,
            file_path="/path/to/raster.tif"
        )

    def test_total_pixels(self):
        """Test total_pixels property."""
        self.assertEqual(self.raster_stats.total_pixels, 10000)

    def test_is_singleband(self):
        """Test is_singleband property."""
        self.assertTrue(self.raster_stats.is_singleband)

    def test_extent_dimensions(self):
        """Test extent width and height."""
        self.assertEqual(self.raster_stats.extent_width, 1.0)
        self.assertEqual(self.raster_stats.extent_height, 1.0)

    def test_get_band_stats(self):
        """Test get_band_stats method."""
        band1 = self.raster_stats.get_band_stats(1)
        self.assertIsNotNone(band1)
        self.assertEqual(band1.mean, 127.5)
        
        band2 = self.raster_stats.get_band_stats(2)
        self.assertIsNone(band2)


class TestBandStatisticsProperties(unittest.TestCase):
    """Tests for BandStatistics dataclass properties."""

    def setUp(self):
        """Create test BandStatistics."""
        self.stats = BandStatistics(
            band_number=1,
            min_value=0.0,
            max_value=100.0,
            mean=50.0,
            std_dev=25.0,
            no_data_value=-9999.0,
            valid_pixel_count=900,
            total_pixel_count=1000,
            sum=45000.0,
            data_type=RasterDataType.FLOAT32
        )

    def test_has_no_data(self):
        """Test has_no_data property."""
        self.assertTrue(self.stats.has_no_data)
        
        stats_no_nodata = BandStatistics(
            band_number=1,
            min_value=0.0,
            max_value=100.0,
            mean=50.0,
            std_dev=25.0
        )
        self.assertFalse(stats_no_nodata.has_no_data)

    def test_null_percentage(self):
        """Test null_percentage calculation."""
        # 100 null out of 1000 = 10%
        self.assertEqual(self.stats.null_percentage, 10.0)

    def test_value_range(self):
        """Test value_range calculation."""
        self.assertEqual(self.stats.value_range, 100.0)


class TestHistogramDataMethods(unittest.TestCase):
    """Tests for HistogramData dataclass methods."""

    def setUp(self):
        """Create test HistogramData."""
        self.histogram = HistogramData(
            band_number=1,
            bin_count=10,
            bin_edges=tuple(float(i * 10) for i in range(11)),
            counts=(10, 20, 30, 40, 50, 50, 40, 30, 20, 10),
            min_value=0.0,
            max_value=100.0,
            include_no_data=False,
            method=HistogramBinMethod.EQUAL_INTERVAL
        )

    def test_total_count(self):
        """Test total_count property."""
        self.assertEqual(self.histogram.total_count, 300)

    def test_bin_width(self):
        """Test bin_width property."""
        self.assertEqual(self.histogram.bin_width, 10.0)

    def test_get_percentile_median(self):
        """Test percentile calculation for median."""
        median = self.histogram.get_percentile_value(50.0)
        # Should be around 50 given symmetric distribution
        self.assertGreater(median, 40.0)
        self.assertLess(median, 60.0)


class TestPixelIdentifyResult(unittest.TestCase):
    """Tests for PixelIdentifyResult dataclass."""

    def test_get_value_default_band(self):
        """Test get_value with default band."""
        result = PixelIdentifyResult(
            x=100.0,
            y=200.0,
            row=10,
            col=20,
            band_values={1: 127.0, 2: 64.0},
            is_valid=True,
            is_no_data=False
        )
        self.assertEqual(result.get_value(), 127.0)
        self.assertEqual(result.get_value(2), 64.0)
        self.assertIsNone(result.get_value(3))

    def test_invalid_result(self):
        """Test invalid pixel result."""
        result = PixelIdentifyResult(
            x=-100.0,
            y=-200.0,
            row=-1,
            col=-1,
            is_valid=False
        )
        self.assertFalse(result.is_valid)
        self.assertIsNone(result.get_value())


class TestTransparencySettings(unittest.TestCase):
    """Tests for TransparencySettings dataclass."""

    def test_default_values(self):
        """Test default transparency settings."""
        settings = TransparencySettings()
        self.assertEqual(settings.global_opacity, 1.0)
        self.assertTrue(settings.no_data_transparent)
        self.assertEqual(len(settings.transparent_pixel_list), 0)

    def test_opacity_clamping_high(self):
        """Test opacity clamping for values > 1.0."""
        settings = TransparencySettings(global_opacity=1.5)
        self.assertEqual(settings.global_opacity, 1.0)

    def test_opacity_clamping_low(self):
        """Test opacity clamping for values < 0.0."""
        settings = TransparencySettings(global_opacity=-0.5)
        self.assertEqual(settings.global_opacity, 0.0)

    def test_custom_transparent_pixels(self):
        """Test custom transparent pixel list."""
        settings = TransparencySettings(
            global_opacity=0.8,
            transparent_pixel_list=[(255, 255, 255, 0)]
        )
        self.assertEqual(settings.global_opacity, 0.8)
        self.assertEqual(len(settings.transparent_pixel_list), 1)


class TestBackendExports(unittest.TestCase):
    """Tests for backend module exports."""

    def test_all_exports_available(self):
        """Test that all expected exports are in __all__."""
        from adapters import backends
        
        expected_exports = [
            'BackendFactory',
            'BackendSelector',
            'POSTGRESQL_AVAILABLE',
            'QGISRasterBackend',
            'get_qgis_raster_backend',
            'QGIS_RASTER_BACKEND_AVAILABLE',
        ]
        
        for export in expected_exports:
            self.assertTrue(
                hasattr(backends, export),
                f"Missing export: {export}"
            )


if __name__ == '__main__':
    unittest.main()

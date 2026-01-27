"""
Unit tests for Raster Port Interface.

EPIC-2: Raster Integration
US-02: Raster Port Interface

Tests the abstract interface and data classes without QGIS dependencies.
"""
import unittest
from dataclasses import FrozenInstanceError

from core.ports.raster_port import (
    RasterPort,
    RasterStats,
    BandStatistics,
    HistogramData,
    PixelIdentifyResult,
    TransparencySettings,
    RasterDataType,
    RasterRendererType,
    HistogramBinMethod,
)


class TestRasterDataType(unittest.TestCase):
    """Tests for RasterDataType enum."""

    def test_data_types_exist(self):
        """Verify all expected data types are defined."""
        expected_types = [
            'UNKNOWN', 'BYTE', 'INT16', 'UINT16', 'INT32', 'UINT32',
            'FLOAT32', 'FLOAT64', 'CINT16', 'CINT32', 'CFLOAT32', 'CFLOAT64'
        ]
        for dtype in expected_types:
            self.assertTrue(hasattr(RasterDataType, dtype), f"Missing {dtype}")

    def test_data_type_values_unique(self):
        """Verify all data type values are unique."""
        values = [dt.value for dt in RasterDataType]
        self.assertEqual(len(values), len(set(values)))


class TestRasterRendererType(unittest.TestCase):
    """Tests for RasterRendererType enum."""

    def test_renderer_types_exist(self):
        """Verify all expected renderer types are defined."""
        expected_types = [
            'UNKNOWN', 'SINGLEBAND_GRAY', 'SINGLEBAND_PSEUDOCOLOR',
            'MULTIBAND_COLOR', 'PALETTED', 'HILLSHADE', 'CONTOUR'
        ]
        for rtype in expected_types:
            self.assertTrue(hasattr(RasterRendererType, rtype), f"Missing {rtype}")


class TestHistogramBinMethod(unittest.TestCase):
    """Tests for HistogramBinMethod enum."""

    def test_bin_methods_exist(self):
        """Verify all expected bin methods are defined."""
        expected_methods = ['EQUAL_INTERVAL', 'QUANTILE', 'NATURAL_BREAKS', 'CUSTOM']
        for method in expected_methods:
            self.assertTrue(hasattr(HistogramBinMethod, method), f"Missing {method}")


class TestBandStatistics(unittest.TestCase):
    """Tests for BandStatistics dataclass."""

    def setUp(self):
        """Create sample band statistics."""
        self.stats = BandStatistics(
            band_number=1,
            min_value=0.0,
            max_value=255.0,
            mean=127.5,
            std_dev=50.0,
            no_data_value=-9999.0,
            valid_pixel_count=90000,
            total_pixel_count=100000,
            sum=11475000.0,
            data_type=RasterDataType.BYTE
        )

    def test_band_statistics_creation(self):
        """Test basic creation of BandStatistics."""
        self.assertEqual(self.stats.band_number, 1)
        self.assertEqual(self.stats.min_value, 0.0)
        self.assertEqual(self.stats.max_value, 255.0)
        self.assertEqual(self.stats.mean, 127.5)

    def test_has_no_data_property(self):
        """Test has_no_data property."""
        self.assertTrue(self.stats.has_no_data)
        
        stats_no_nodata = BandStatistics(
            band_number=1,
            min_value=0.0,
            max_value=255.0,
            mean=127.5,
            std_dev=50.0
        )
        self.assertFalse(stats_no_nodata.has_no_data)

    def test_null_percentage_property(self):
        """Test null_percentage calculation."""
        # 10000 null out of 100000 = 10%
        self.assertEqual(self.stats.null_percentage, 10.0)

    def test_null_percentage_zero_total(self):
        """Test null_percentage with zero total pixels."""
        stats = BandStatistics(
            band_number=1,
            min_value=0.0,
            max_value=255.0,
            mean=0.0,
            std_dev=0.0,
            total_pixel_count=0
        )
        self.assertEqual(stats.null_percentage, 0.0)

    def test_value_range_property(self):
        """Test value_range calculation."""
        self.assertEqual(self.stats.value_range, 255.0)

    def test_frozen_dataclass(self):
        """Test that BandStatistics is immutable."""
        with self.assertRaises(FrozenInstanceError):
            self.stats.band_number = 2


class TestRasterStats(unittest.TestCase):
    """Tests for RasterStats dataclass."""

    def setUp(self):
        """Create sample raster stats."""
        band1 = BandStatistics(
            band_number=1,
            min_value=0.0,
            max_value=255.0,
            mean=127.5,
            std_dev=50.0
        )
        band2 = BandStatistics(
            band_number=2,
            min_value=0.0,
            max_value=255.0,
            mean=100.0,
            std_dev=45.0
        )
        self.stats = RasterStats(
            layer_id="test_layer_001",
            layer_name="Test Raster",
            width=1000,
            height=1000,
            band_count=2,
            crs_auth_id="EPSG:4326",
            pixel_size_x=0.001,
            pixel_size_y=0.001,
            extent=(0.0, 0.0, 1.0, 1.0),
            band_statistics=(band1, band2),
            renderer_type=RasterRendererType.MULTIBAND_COLOR,
            file_path="/path/to/raster.tif"
        )

    def test_raster_stats_creation(self):
        """Test basic creation of RasterStats."""
        self.assertEqual(self.stats.layer_id, "test_layer_001")
        self.assertEqual(self.stats.band_count, 2)
        self.assertEqual(self.stats.width, 1000)
        self.assertEqual(self.stats.height, 1000)

    def test_total_pixels_property(self):
        """Test total_pixels calculation."""
        self.assertEqual(self.stats.total_pixels, 1000000)

    def test_is_singleband_property(self):
        """Test is_singleband detection."""
        self.assertFalse(self.stats.is_singleband)
        
        single_band_stats = RasterStats(
            layer_id="test",
            layer_name="Test",
            width=100,
            height=100,
            band_count=1,
            crs_auth_id="EPSG:4326",
            pixel_size_x=1.0,
            pixel_size_y=1.0,
            extent=(0, 0, 100, 100)
        )
        self.assertTrue(single_band_stats.is_singleband)

    def test_is_multiband_property(self):
        """Test is_multiband detection."""
        self.assertTrue(self.stats.is_multiband)

    def test_extent_dimensions(self):
        """Test extent width and height properties."""
        self.assertEqual(self.stats.extent_width, 1.0)
        self.assertEqual(self.stats.extent_height, 1.0)

    def test_get_band_stats(self):
        """Test get_band_stats method."""
        band1_stats = self.stats.get_band_stats(1)
        self.assertIsNotNone(band1_stats)
        self.assertEqual(band1_stats.band_number, 1)
        self.assertEqual(band1_stats.mean, 127.5)

        band2_stats = self.stats.get_band_stats(2)
        self.assertIsNotNone(band2_stats)
        self.assertEqual(band2_stats.mean, 100.0)

        # Non-existent band
        band3_stats = self.stats.get_band_stats(3)
        self.assertIsNone(band3_stats)

    def test_frozen_dataclass(self):
        """Test that RasterStats is immutable."""
        with self.assertRaises(FrozenInstanceError):
            self.stats.layer_id = "new_id"


class TestHistogramData(unittest.TestCase):
    """Tests for HistogramData dataclass."""

    def setUp(self):
        """Create sample histogram data."""
        self.histogram = HistogramData(
            band_number=1,
            bin_count=5,
            bin_edges=(0.0, 50.0, 100.0, 150.0, 200.0, 250.0),
            counts=(100, 200, 300, 250, 150),
            min_value=0.0,
            max_value=250.0
        )

    def test_histogram_creation(self):
        """Test basic creation of HistogramData."""
        self.assertEqual(self.histogram.band_number, 1)
        self.assertEqual(self.histogram.bin_count, 5)
        self.assertEqual(len(self.histogram.bin_edges), 6)
        self.assertEqual(len(self.histogram.counts), 5)

    def test_total_count_property(self):
        """Test total_count calculation."""
        self.assertEqual(self.histogram.total_count, 1000)

    def test_bin_width_property(self):
        """Test bin_width calculation."""
        self.assertEqual(self.histogram.bin_width, 50.0)

    def test_bin_width_zero_bins(self):
        """Test bin_width with zero bins."""
        histogram = HistogramData(
            band_number=1,
            bin_count=0,
            bin_edges=(),
            counts=(),
            min_value=0.0,
            max_value=0.0
        )
        self.assertEqual(histogram.bin_width, 0.0)

    def test_get_percentile_value(self):
        """Test percentile calculation from histogram."""
        # Test 50th percentile (median)
        median = self.histogram.get_percentile_value(50.0)
        # Should be around 100-150 range based on cumulative counts
        self.assertGreater(median, 50.0)
        self.assertLess(median, 200.0)

        # Test edge cases
        p0 = self.histogram.get_percentile_value(0.0)
        p100 = self.histogram.get_percentile_value(100.0)
        self.assertGreaterEqual(p0, 0.0)
        self.assertLessEqual(p100, 250.0)

    def test_get_percentile_empty_histogram(self):
        """Test percentile calculation with empty histogram."""
        histogram = HistogramData(
            band_number=1,
            bin_count=0,
            bin_edges=(),
            counts=(),
            min_value=0.0,
            max_value=0.0
        )
        self.assertEqual(histogram.get_percentile_value(50.0), 0.0)


class TestPixelIdentifyResult(unittest.TestCase):
    """Tests for PixelIdentifyResult dataclass."""

    def test_pixel_identify_creation(self):
        """Test basic creation of PixelIdentifyResult."""
        result = PixelIdentifyResult(
            x=100.5,
            y=200.5,
            row=100,
            col=200,
            band_values={1: 127.0, 2: 64.0, 3: 255.0},
            is_valid=True,
            is_no_data=False
        )
        self.assertEqual(result.x, 100.5)
        self.assertEqual(result.row, 100)
        self.assertEqual(len(result.band_values), 3)

    def test_get_value_method(self):
        """Test get_value method."""
        result = PixelIdentifyResult(
            x=0.0,
            y=0.0,
            row=0,
            col=0,
            band_values={1: 100.0, 2: 200.0}
        )
        self.assertEqual(result.get_value(1), 100.0)
        self.assertEqual(result.get_value(2), 200.0)
        self.assertIsNone(result.get_value(3))

    def test_default_band(self):
        """Test default band parameter."""
        result = PixelIdentifyResult(
            x=0.0,
            y=0.0,
            row=0,
            col=0,
            band_values={1: 42.0}
        )
        self.assertEqual(result.get_value(), 42.0)

    def test_invalid_result(self):
        """Test result for invalid location."""
        result = PixelIdentifyResult(
            x=-100.0,
            y=-100.0,
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
        self.assertEqual(settings.transparent_pixel_list, [])

    def test_custom_opacity(self):
        """Test custom opacity settings."""
        settings = TransparencySettings(global_opacity=0.5)
        self.assertEqual(settings.global_opacity, 0.5)

    def test_opacity_clamping(self):
        """Test that opacity is clamped to valid range."""
        # Test value above 1.0
        settings_high = TransparencySettings(global_opacity=1.5)
        self.assertEqual(settings_high.global_opacity, 1.0)

        # Test value below 0.0
        settings_low = TransparencySettings(global_opacity=-0.5)
        self.assertEqual(settings_low.global_opacity, 0.0)

    def test_transparent_pixel_list(self):
        """Test RGB transparency list."""
        settings = TransparencySettings(
            transparent_pixel_list=[(255, 255, 255, 0), (0, 0, 0, 0)]
        )
        self.assertEqual(len(settings.transparent_pixel_list), 2)


class TestRasterPortInterface(unittest.TestCase):
    """Tests for RasterPort abstract interface."""

    def test_raster_port_is_abstract(self):
        """Verify RasterPort cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            RasterPort()

    def test_abstract_methods_defined(self):
        """Verify all abstract methods are defined."""
        abstract_methods = [
            'get_statistics',
            'get_band_statistics',
            'get_histogram',
            'identify_pixel',
            'get_pixel_value',
            'get_transparency_settings',
            'apply_transparency',
            'set_opacity',
            'get_extent',
            'get_crs',
            'get_band_count',
            'get_data_type',
            'is_valid',
            'supports_statistics',
        ]
        for method_name in abstract_methods:
            self.assertTrue(
                hasattr(RasterPort, method_name),
                f"Missing abstract method: {method_name}"
            )


class TestRasterPortExports(unittest.TestCase):
    """Tests for raster port exports."""

    def test_imports_from_ports_module(self):
        """Test that all classes can be imported from core.ports."""
        from core.ports import (
            RasterPort,
            RasterStats,
            BandStatistics,
            HistogramData,
            PixelIdentifyResult,
            TransparencySettings,
            RasterDataType,
            RasterRendererType,
            HistogramBinMethod,
        )
        # Verify they're the correct types
        self.assertTrue(hasattr(RasterPort, '__abstractmethods__'))
        self.assertIsNotNone(RasterStats)
        self.assertIsNotNone(BandStatistics)


if __name__ == '__main__':
    unittest.main()

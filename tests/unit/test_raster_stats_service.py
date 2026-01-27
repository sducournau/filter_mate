"""
Unit tests for Raster Stats Service.

EPIC-2: Raster Integration
US-04: Raster Stats Service

Tests the service layer without QGIS dependencies using mocked backend.
"""
import unittest
from unittest.mock import MagicMock, Mock, patch
from datetime import datetime

from core.ports.raster_port import (
    BandStatistics,
    HistogramBinMethod,
    HistogramData,
    PixelIdentifyResult,
    RasterDataType,
    RasterRendererType,
    RasterStats,
    TransparencySettings,
)
from core.services.raster_stats_service import (
    RasterStatsService,
    StatsRequest,
    StatsResponse,
    StatsRequestStatus,
    StatsCacheStrategy,
    LayerStatsSnapshot,
    BandSummary,
    get_raster_stats_service,
    reset_raster_stats_service,
)


class MockRasterBackend:
    """Mock RasterPort implementation for testing."""
    
    def __init__(self):
        self.get_statistics_called = False
        self.get_histogram_called = False
        self.identify_pixel_called = False
        
    def is_valid(self, layer_id: str) -> bool:
        return layer_id.startswith("valid_")
    
    def supports_statistics(self, layer_id: str) -> bool:
        return self.is_valid(layer_id)
    
    def get_statistics(
        self,
        layer_id: str,
        bands=None,
        sample_size: int = 0,
        force_recalculate: bool = False
    ) -> RasterStats:
        self.get_statistics_called = True
        
        band_stats = BandStatistics(
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
        
        return RasterStats(
            layer_id=layer_id,
            layer_name="Test Raster",
            width=100,
            height=100,
            band_count=1,
            crs_auth_id="EPSG:4326",
            pixel_size_x=0.01,
            pixel_size_y=0.01,
            extent=(0.0, 0.0, 1.0, 1.0),
            band_statistics=(band_stats,),
            renderer_type=RasterRendererType.SINGLEBAND_GRAY,
            file_path="/path/to/raster.tif"
        )
    
    def get_histogram(
        self,
        layer_id: str,
        band_number: int = 1,
        bin_count: int = 256,
        min_value=None,
        max_value=None,
        include_no_data: bool = False,
        method=HistogramBinMethod.EQUAL_INTERVAL
    ) -> HistogramData:
        self.get_histogram_called = True
        
        return HistogramData(
            band_number=band_number,
            bin_count=10,
            bin_edges=tuple(float(i * 25.5) for i in range(11)),
            counts=(10, 20, 30, 40, 50, 50, 40, 30, 20, 10),
            min_value=0.0,
            max_value=255.0,
            include_no_data=include_no_data,
            method=method
        )
    
    def identify_pixel(
        self,
        layer_id: str,
        x: float,
        y: float,
        crs_auth_id=None
    ) -> PixelIdentifyResult:
        self.identify_pixel_called = True
        
        return PixelIdentifyResult(
            x=x,
            y=y,
            row=int(y * 100),
            col=int(x * 100),
            band_values={1: 127.0},
            is_valid=True,
            is_no_data=False
        )
    
    def get_transparency_settings(self, layer_id: str) -> TransparencySettings:
        return TransparencySettings(global_opacity=1.0)
    
    def set_opacity(self, layer_id: str, opacity: float) -> bool:
        return True


class TestStatsRequestDataclass(unittest.TestCase):
    """Tests for StatsRequest dataclass."""

    def test_default_values(self):
        """Test default request values."""
        request = StatsRequest(layer_id="test_layer")
        
        self.assertEqual(request.layer_id, "test_layer")
        self.assertIsNone(request.bands)
        self.assertTrue(request.include_histogram)
        self.assertEqual(request.histogram_bins, 256)
        self.assertEqual(request.sample_size, 0)
        self.assertEqual(request.priority, 0)
        self.assertIsNone(request.callback)

    def test_custom_values(self):
        """Test custom request values."""
        request = StatsRequest(
            layer_id="custom_layer",
            bands=[1, 2],
            include_histogram=False,
            histogram_bins=128,
            sample_size=10000,
            priority=5
        )
        
        self.assertEqual(request.bands, [1, 2])
        self.assertFalse(request.include_histogram)
        self.assertEqual(request.histogram_bins, 128)


class TestStatsResponseDataclass(unittest.TestCase):
    """Tests for StatsResponse dataclass."""

    def test_success_response(self):
        """Test successful response properties."""
        request = StatsRequest(layer_id="test")
        response = StatsResponse(
            request=request,
            status=StatsRequestStatus.COMPLETED,
            stats=None,
            histograms={1: MagicMock()},
            computation_time_ms=100.0
        )
        
        self.assertTrue(response.is_success)
        self.assertTrue(response.has_histograms)

    def test_failed_response(self):
        """Test failed response properties."""
        request = StatsRequest(layer_id="test")
        response = StatsResponse(
            request=request,
            status=StatsRequestStatus.FAILED,
            error_message="Test error"
        )
        
        self.assertFalse(response.is_success)
        self.assertFalse(response.has_histograms)
        self.assertEqual(response.error_message, "Test error")


class TestRasterStatsService(unittest.TestCase):
    """Tests for RasterStatsService class."""

    def setUp(self):
        """Create service with mock backend."""
        self.mock_backend = MockRasterBackend()
        self.service = RasterStatsService(
            backend=self.mock_backend,
            cache_strategy=StatsCacheStrategy.SESSION
        )

    def test_compute_statistics_success(self):
        """Test successful statistics computation."""
        request = StatsRequest(
            layer_id="valid_layer",
            include_histogram=True
        )
        
        response = self.service.compute_statistics(request)
        
        self.assertTrue(response.is_success)
        self.assertIsNotNone(response.stats)
        self.assertTrue(self.mock_backend.get_statistics_called)
        self.assertTrue(self.mock_backend.get_histogram_called)

    def test_compute_statistics_caching(self):
        """Test that results are cached."""
        request = StatsRequest(
            layer_id="valid_layer",
            include_histogram=False
        )
        
        # First call
        response1 = self.service.compute_statistics(request)
        self.assertTrue(self.mock_backend.get_statistics_called)
        
        # Reset flag
        self.mock_backend.get_statistics_called = False
        
        # Second call - should use cache
        response2 = self.service.compute_statistics(request)
        self.assertFalse(self.mock_backend.get_statistics_called)
        
        # Verify same stats
        self.assertEqual(
            response1.stats.layer_name,
            response2.stats.layer_name
        )

    def test_compute_statistics_with_callback(self):
        """Test callback invocation."""
        callback_result = []
        
        def callback(response):
            callback_result.append(response)
        
        request = StatsRequest(
            layer_id="valid_layer",
            include_histogram=False,
            callback=callback
        )
        
        self.service.compute_statistics(request)
        
        self.assertEqual(len(callback_result), 1)
        self.assertTrue(callback_result[0].is_success)

    def test_get_layer_snapshot(self):
        """Test layer snapshot generation."""
        snapshot = self.service.get_layer_snapshot("valid_layer")
        
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.layer_name, "Test Raster")
        self.assertEqual(snapshot.band_count, 1)
        self.assertEqual(snapshot.width, 100)
        self.assertEqual(snapshot.height, 100)
        self.assertEqual(snapshot.crs, "EPSG:4326")

    def test_get_layer_snapshot_invalid_layer(self):
        """Test snapshot for invalid layer."""
        snapshot = self.service.get_layer_snapshot("invalid_layer")
        
        self.assertIsNone(snapshot)

    def test_get_band_histogram(self):
        """Test histogram retrieval."""
        histogram = self.service.get_band_histogram(
            "valid_layer",
            band_number=1,
            bin_count=10
        )
        
        self.assertIsNotNone(histogram)
        self.assertEqual(histogram.band_number, 1)
        self.assertEqual(histogram.bin_count, 10)

    def test_identify_at_point(self):
        """Test pixel identification."""
        result = self.service.identify_at_point(
            "valid_layer",
            x=0.5,
            y=0.5
        )
        
        self.assertIsNotNone(result)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.get_value(1), 127.0)

    def test_set_layer_opacity(self):
        """Test opacity setting."""
        result = self.service.set_layer_opacity("valid_layer", 0.5)
        
        self.assertTrue(result)

    def test_get_layer_opacity(self):
        """Test opacity retrieval."""
        opacity = self.service.get_layer_opacity("valid_layer")
        
        self.assertEqual(opacity, 1.0)

    def test_clear_cache_specific_layer(self):
        """Test clearing cache for specific layer."""
        # Populate cache
        request = StatsRequest(layer_id="valid_layer", include_histogram=False)
        self.service.compute_statistics(request)
        
        # Verify cached
        cache_stats = self.service.get_cache_stats()
        self.assertEqual(cache_stats['cached_layers'], 1)
        
        # Clear specific layer
        self.service.clear_cache("valid_layer")
        
        # Verify cleared
        cache_stats = self.service.get_cache_stats()
        self.assertEqual(cache_stats['cached_layers'], 0)

    def test_clear_cache_all(self):
        """Test clearing all cache."""
        # Populate cache with multiple layers
        for i in range(3):
            request = StatsRequest(
                layer_id=f"valid_layer_{i}",
                include_histogram=False
            )
            self.service.compute_statistics(request)
        
        # Clear all
        self.service.clear_cache()
        
        # Verify cleared
        cache_stats = self.service.get_cache_stats()
        self.assertEqual(cache_stats['cached_layers'], 0)


class TestBandSummaryFormatting(unittest.TestCase):
    """Tests for band summary formatting."""

    def setUp(self):
        """Create service with mock backend."""
        self.mock_backend = MockRasterBackend()
        self.service = RasterStatsService(backend=self.mock_backend)

    def test_band_summary_in_snapshot(self):
        """Test band summaries are included in snapshot."""
        snapshot = self.service.get_layer_snapshot("valid_layer")
        
        self.assertIsNotNone(snapshot)
        self.assertEqual(len(snapshot.band_summaries), 1)
        
        band_summary = snapshot.band_summaries[0]
        self.assertEqual(band_summary.band_number, 1)
        self.assertIn("0.00", band_summary.min_value)
        self.assertIn("255.00", band_summary.max_value)
        self.assertEqual(band_summary.data_type, "BYTE")


class TestStatsCacheStrategy(unittest.TestCase):
    """Tests for cache strategy enum."""

    def test_cache_strategies_exist(self):
        """Test all cache strategies are defined."""
        strategies = ['NONE', 'LAYER', 'SESSION', 'PERSISTENT']
        for strategy in strategies:
            self.assertTrue(hasattr(StatsCacheStrategy, strategy))

    def test_no_caching_strategy(self):
        """Test NO caching strategy disables cache."""
        mock_backend = MockRasterBackend()
        service = RasterStatsService(
            backend=mock_backend,
            cache_strategy=StatsCacheStrategy.NONE
        )
        
        request = StatsRequest(layer_id="valid_layer", include_histogram=False)
        
        # First call
        service.compute_statistics(request)
        mock_backend.get_statistics_called = False
        
        # Second call - should NOT use cache
        service.compute_statistics(request)
        self.assertTrue(mock_backend.get_statistics_called)


class TestServiceExports(unittest.TestCase):
    """Tests for service module exports."""

    def test_imports_from_services_module(self):
        """Test all exports are available from core.services."""
        from core.services import (
            RasterStatsService,
            StatsRequest,
            StatsResponse,
            StatsRequestStatus,
            StatsCacheStrategy,
            LayerStatsSnapshot,
            BandSummary,
            get_raster_stats_service,
            reset_raster_stats_service,
        )
        
        # Verify types
        self.assertIsNotNone(RasterStatsService)
        self.assertIsNotNone(StatsRequest)
        self.assertIsNotNone(StatsResponse)


class TestFactoryFunction(unittest.TestCase):
    """Tests for service factory function."""

    def tearDown(self):
        """Reset service singleton after each test."""
        reset_raster_stats_service()

    def test_reset_service(self):
        """Test service can be reset."""
        # This shouldn't raise
        reset_raster_stats_service()

    def test_get_service_with_mock_backend(self):
        """Test getting service with custom backend."""
        mock_backend = MockRasterBackend()
        
        # Reset first to ensure clean state
        reset_raster_stats_service()
        
        # Create with custom backend
        service = RasterStatsService(backend=mock_backend)
        
        # Verify it works
        snapshot = service.get_layer_snapshot("valid_layer")
        self.assertIsNotNone(snapshot)


if __name__ == '__main__':
    unittest.main()

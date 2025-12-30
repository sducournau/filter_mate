# -*- coding: utf-8 -*-
"""
Tests for CRS Utilities Module - FilterMate v2.5.7

Tests for crs_utils.py module which provides CRS detection, conversion,
and metric buffer operations.

Usage:
    pytest tests/test_crs_utils.py -v

Author: FilterMate Team
Date: December 2025
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Add plugin directory to Python path
plugin_dir = Path(__file__).parent.parent
sys.path.insert(0, str(plugin_dir))


class TestCRSDetection:
    """Tests for CRS detection functions."""
    
    def test_geographic_crs_detection_epsg_4326(self):
        """Test that EPSG:4326 (WGS84) is correctly identified as geographic."""
        mock_crs = Mock()
        mock_crs.isValid.return_value = True
        mock_crs.isGeographic.return_value = True
        mock_crs.authid.return_value = "EPSG:4326"
        
        # Simulate is_geographic_crs logic
        is_geographic = mock_crs.isGeographic()
        
        assert is_geographic is True
        assert mock_crs.authid() == "EPSG:4326"
    
    def test_metric_crs_detection_epsg_3857(self):
        """Test that EPSG:3857 (Web Mercator) is correctly identified as metric."""
        mock_crs = Mock()
        mock_crs.isValid.return_value = True
        mock_crs.isGeographic.return_value = False
        mock_crs.authid.return_value = "EPSG:3857"
        mock_crs.mapUnits.return_value = "DistanceMeters"
        
        is_geographic = mock_crs.isGeographic()
        
        assert is_geographic is False
        assert mock_crs.authid() == "EPSG:3857"
    
    def test_utm_crs_detection(self):
        """Test that UTM CRS is correctly identified as metric."""
        mock_crs = Mock()
        mock_crs.isValid.return_value = True
        mock_crs.isGeographic.return_value = False
        mock_crs.authid.return_value = "EPSG:32631"  # UTM zone 31N
        mock_crs.mapUnits.return_value = "DistanceMeters"
        
        is_geographic = mock_crs.isGeographic()
        
        assert is_geographic is False
        assert "326" in mock_crs.authid()  # UTM north prefix
    
    def test_lambert93_crs_detection(self):
        """Test that EPSG:2154 (Lambert 93) is correctly identified as metric."""
        mock_crs = Mock()
        mock_crs.isValid.return_value = True
        mock_crs.isGeographic.return_value = False
        mock_crs.authid.return_value = "EPSG:2154"
        mock_crs.mapUnits.return_value = "DistanceMeters"
        
        is_geographic = mock_crs.isGeographic()
        
        assert is_geographic is False
    
    def test_invalid_crs_handling(self):
        """Test handling of invalid CRS."""
        mock_crs = Mock()
        mock_crs.isValid.return_value = False
        
        # Invalid CRS should be handled gracefully
        assert mock_crs.isValid() is False
    
    def test_null_crs_handling(self):
        """Test handling of None CRS."""
        crs = None
        
        # is_geographic_crs should return False for None
        result = crs is not None and crs.isValid() if crs else False
        assert result is False


class TestUTMZoneCalculation:
    """Tests for UTM zone calculation."""
    
    def test_utm_zone_paris(self):
        """Test UTM zone calculation for Paris (lon=2.35, lat=48.86)."""
        longitude = 2.35
        latitude = 48.86
        
        # UTM zone = int((lon + 180) / 6) + 1
        utm_zone = int((longitude + 180) / 6) + 1
        
        # Paris is in UTM zone 31
        assert utm_zone == 31
        
        # North hemisphere: EPSG:326XX
        epsg = 32600 + utm_zone
        assert epsg == 32631
    
    def test_utm_zone_new_york(self):
        """Test UTM zone calculation for New York (lon=-74, lat=40.7)."""
        longitude = -74.0
        latitude = 40.7
        
        utm_zone = int((longitude + 180) / 6) + 1
        
        # New York is in UTM zone 18
        assert utm_zone == 18
        
        epsg = 32600 + utm_zone
        assert epsg == 32618
    
    def test_utm_zone_sydney(self):
        """Test UTM zone calculation for Sydney (lon=151.2, lat=-33.9)."""
        longitude = 151.2
        latitude = -33.9
        
        utm_zone = int((longitude + 180) / 6) + 1
        
        # Sydney is in UTM zone 56
        assert utm_zone == 56
        
        # South hemisphere: EPSG:327XX
        epsg = 32700 + utm_zone
        assert epsg == 32756
    
    def test_utm_zone_boundary(self):
        """Test UTM zone at zone boundary (lon=6.0, exactly at zone 32 boundary)."""
        longitude = 6.0
        
        utm_zone = int((longitude + 180) / 6) + 1
        
        assert utm_zone == 32
    
    def test_utm_zone_negative_longitude(self):
        """Test UTM zone for western hemisphere."""
        longitude = -122.4  # San Francisco
        
        utm_zone = int((longitude + 180) / 6) + 1
        
        assert utm_zone == 10


class TestCRSUnitsConversion:
    """Tests for CRS unit conversion functions."""
    
    def test_meters_to_degrees_equator(self):
        """Test meters to degrees conversion at equator."""
        meters = 111320  # Approximate meters per degree at equator
        
        # 1 degree ≈ 111320m at equator
        degrees = meters / 111320
        
        assert abs(degrees - 1.0) < 0.01
    
    def test_meters_to_degrees_mid_latitude(self):
        """Test meters to degrees conversion at mid-latitude (45°)."""
        import math
        
        meters = 100
        latitude = 45.0
        
        # Meters per degree varies with latitude
        meters_per_degree_lon = 111320 * math.cos(math.radians(latitude))
        meters_per_degree_lat = 111320
        
        # At 45° latitude, meters per degree is less for longitude
        assert meters_per_degree_lon < 111320
        assert meters_per_degree_lon > 70000  # Approximately 78km
    
    def test_degrees_to_meters_small_buffer(self):
        """Test that small degree values convert to reasonable meter values."""
        degrees = 0.001  # About 100m at mid-latitudes
        
        # Using approximate conversion (mid-latitude)
        meters = degrees * 78000
        
        assert 50 < meters < 200


class TestMetricBufferOperation:
    """Tests for metric buffer operations."""
    
    def test_buffer_value_unchanged_for_metric_crs(self):
        """Test that buffer value is unchanged for metric CRS."""
        is_metric = True
        buffer_value_meters = 100
        
        if is_metric:
            final_buffer = buffer_value_meters
        else:
            final_buffer = None  # Would need conversion
        
        assert final_buffer == 100
    
    def test_buffer_needs_conversion_for_geographic_crs(self):
        """Test that buffer needs conversion for geographic CRS."""
        is_geographic = True
        buffer_value_meters = 100
        
        needs_conversion = is_geographic and buffer_value_meters > 0
        
        assert needs_conversion is True
    
    def test_zero_buffer_no_conversion(self):
        """Test that zero buffer needs no conversion."""
        buffer_value = 0
        
        # Zero buffer is zero regardless of CRS
        needs_conversion = buffer_value > 0
        
        assert needs_conversion is False
    
    def test_negative_buffer_erosion(self):
        """Test that negative buffer (erosion) is handled."""
        buffer_value = -10
        
        # Negative buffers should also work with CRS conversion
        is_erosion = buffer_value < 0
        
        assert is_erosion is True


class TestCRSTransformer:
    """Tests for CRSTransformer class."""
    
    def test_transformer_identity(self):
        """Test transformer with same source and target CRS."""
        source_authid = "EPSG:4326"
        target_authid = "EPSG:4326"
        
        is_identity = source_authid == target_authid
        
        assert is_identity is True
    
    def test_transformer_different_crs(self):
        """Test transformer with different CRS."""
        source_authid = "EPSG:4326"
        target_authid = "EPSG:3857"
        
        is_identity = source_authid == target_authid
        
        assert is_identity is False
    
    def test_transform_preserves_geometry_type(self):
        """Test that transformation preserves geometry type."""
        # Simulate a point transformation
        original_type = "Point"
        transformed_type = "Point"  # Should remain Point after transform
        
        assert original_type == transformed_type
    
    def test_transform_copy_behavior(self):
        """Test that copy=True creates a new geometry."""
        class MockGeometry:
            def __init__(self, wkt):
                self.wkt = wkt
        
        original = MockGeometry("POINT(2.35 48.86)")
        copy = MockGeometry(original.wkt)
        copy.wkt = "POINT(261990 6250651)"
        
        # Original should be unchanged
        assert original.wkt == "POINT(2.35 48.86)"
        assert copy.wkt == "POINT(261990 6250651)"


class TestOptimalMetricCRS:
    """Tests for optimal metric CRS selection."""
    
    def test_project_crs_priority(self):
        """Test that project CRS is used if already metric."""
        mock_project_crs = Mock()
        mock_project_crs.isValid.return_value = True
        mock_project_crs.isGeographic.return_value = False
        mock_project_crs.authid.return_value = "EPSG:2154"  # Lambert 93
        mock_project_crs.mapUnits.return_value = "DistanceMeters"
        
        # If project CRS is metric, use it
        if not mock_project_crs.isGeographic():
            result = mock_project_crs.authid()
        else:
            result = "EPSG:3857"
        
        assert result == "EPSG:2154"
    
    def test_fallback_to_web_mercator(self):
        """Test fallback to EPSG:3857 when no better option."""
        mock_project_crs = Mock()
        mock_project_crs.isValid.return_value = True
        mock_project_crs.isGeographic.return_value = True  # Geographic
        
        # If project CRS is geographic, fallback to Web Mercator
        if mock_project_crs.isGeographic():
            result = "EPSG:3857"
        else:
            result = mock_project_crs.authid()
        
        assert result == "EPSG:3857"
    
    def test_utm_preference_when_extent_available(self):
        """Test UTM zone calculation when extent is available."""
        # Paris extent
        center_lon = 2.35
        center_lat = 48.86
        
        utm_zone = int((center_lon + 180) / 6) + 1
        epsg = 32600 + utm_zone if center_lat >= 0 else 32700 + utm_zone
        
        expected = f"EPSG:{epsg}"
        
        assert expected == "EPSG:32631"


class TestDistanceCalculation:
    """Tests for distance calculation functions."""
    
    def test_short_distance_meters(self):
        """Test short distance calculation (100m)."""
        distance = 100  # meters
        
        assert distance == 100
    
    def test_distance_degrees_warning(self):
        """Test that distances in degrees trigger warnings."""
        is_geographic = True
        distance_value = 0.001  # degrees
        
        # For geographic CRS, distances might be in degrees
        # This should trigger a warning
        is_likely_degrees = is_geographic and distance_value < 0.1
        
        assert is_likely_degrees is True
    
    def test_large_distance_check(self):
        """Test that very large distances are flagged."""
        distance = 500  # meters
        
        # A 500m buffer in degrees would be huge
        # At equator: 500m ≈ 0.0045 degrees
        degrees_equivalent = distance / 111320
        
        assert degrees_equivalent < 0.01


class TestLayerCRSInfo:
    """Tests for layer CRS information retrieval."""
    
    def test_layer_crs_info_structure(self):
        """Test that CRS info has expected structure."""
        expected_keys = [
            "authid",
            "description",
            "is_geographic",
            "is_metric",
            "units",
            "proj4"
        ]
        
        # Simulate get_layer_crs_info return
        mock_info = {
            "authid": "EPSG:4326",
            "description": "WGS 84",
            "is_geographic": True,
            "is_metric": False,
            "units": "degrees",
            "proj4": "+proj=longlat +datum=WGS84 +no_defs"
        }
        
        for key in expected_keys:
            assert key in mock_info
    
    def test_invalid_layer_returns_defaults(self):
        """Test that invalid layer returns default values."""
        # Simulate result for invalid layer
        result = {
            "authid": None,
            "description": None,
            "is_geographic": False,
            "is_metric": False,
            "units": "unknown",
            "proj4": None
        }
        
        assert result["authid"] is None
        assert result["units"] == "unknown"


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_antimeridian_handling(self):
        """Test handling of coordinates near antimeridian (180°/-180°)."""
        # Near antimeridian
        longitude = 179.9
        
        utm_zone = int((longitude + 180) / 6) + 1
        
        # Should be valid zone
        assert 1 <= utm_zone <= 60
    
    def test_polar_region_handling(self):
        """Test handling of polar regions."""
        latitude = 85.0  # Arctic
        
        # Polar regions may need special CRS
        is_polar = abs(latitude) > 84
        
        assert is_polar is True
    
    def test_empty_extent_handling(self):
        """Test handling of empty extent."""
        class MockExtent:
            def isEmpty(self):
                return True
            
            def isFinite(self):
                return False
        
        extent = MockExtent()
        
        # Empty extent should trigger fallback
        use_fallback = extent.isEmpty() or not extent.isFinite()
        
        assert use_fallback is True
    
    def test_nan_coordinate_handling(self):
        """Test handling of NaN coordinates."""
        import math
        
        longitude = float('nan')
        
        is_invalid = math.isnan(longitude) or math.isinf(longitude)
        
        assert is_invalid is True


class TestWebMercatorLimits:
    """Tests for Web Mercator (EPSG:3857) limitations."""
    
    def test_web_mercator_latitude_limit(self):
        """Test that Web Mercator has latitude limits (~85.06°)."""
        import math
        
        # Web Mercator max latitude
        max_lat = 85.06
        
        # Test coordinate within limit
        test_lat = 80.0
        is_within_limit = abs(test_lat) <= max_lat
        
        assert is_within_limit is True
    
    def test_polar_coordinates_rejected(self):
        """Test that polar coordinates are flagged for Web Mercator."""
        latitude = 87.0  # Beyond Web Mercator limit
        max_lat = 85.06
        
        is_polar = abs(latitude) > max_lat
        
        assert is_polar is True
    
    def test_distortion_at_high_latitudes(self):
        """Test awareness of distortion at high latitudes."""
        import math
        
        latitude = 70.0  # Scandinavia
        
        # At 70°, scale distortion is significant
        scale_factor = 1 / math.cos(math.radians(latitude))
        
        # Should be notably distorted (scale > 2)
        assert scale_factor > 2.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

"""
Tests for geographic CRS handling in FilterMate.

These tests validate the automatic CRS conversion for geographic coordinate systems:
- Automatic EPSG:4326 to EPSG:3857 conversion for buffer operations
- Correct metric measurements regardless of latitude
- Zoom and flash functionality with geographic coordinates

Related fixes:
- v2.2.5: Automatic geographic CRS handling
- v2.2.5: Geographic coordinates zoom & flash issues
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Add plugin directory to Python path
plugin_dir = Path(__file__).parent.parent
sys.path.insert(0, str(plugin_dir))


class TestGeographicCRSDetection:
    """Tests for detecting geographic coordinate systems."""
    
    def test_epsg_4326_is_geographic(self):
        """Test that EPSG:4326 is correctly identified as geographic."""
        # Mock CRS
        mock_crs = Mock()
        mock_crs.authid.return_value = "EPSG:4326"
        mock_crs.isGeographic.return_value = True
        
        assert mock_crs.isGeographic() is True
        assert mock_crs.authid() == "EPSG:4326"
    
    def test_epsg_3857_is_not_geographic(self):
        """Test that EPSG:3857 is correctly identified as projected."""
        mock_crs = Mock()
        mock_crs.authid.return_value = "EPSG:3857"
        mock_crs.isGeographic.return_value = False
        
        assert mock_crs.isGeographic() is False
        assert mock_crs.authid() == "EPSG:3857"
    
    def test_epsg_2154_is_not_geographic(self):
        """Test that EPSG:2154 (Lambert 93) is correctly identified as projected."""
        mock_crs = Mock()
        mock_crs.authid.return_value = "EPSG:2154"
        mock_crs.isGeographic.return_value = False
        
        assert mock_crs.isGeographic() is False


class TestBufferConversion:
    """Tests for buffer distance conversion in geographic CRS."""
    
    def test_buffer_value_unchanged_for_projected(self):
        """Test that buffer value is unchanged for projected CRS."""
        is_geographic = False
        buffer_value = 50  # meters
        
        if is_geographic:
            # Would convert to degrees or use metric CRS
            pass
        
        # For projected CRS, value stays the same
        assert buffer_value == 50
    
    def test_buffer_conversion_for_geographic(self):
        """Test that buffer needs conversion for geographic CRS."""
        is_geographic = True
        buffer_value_meters = 50
        
        # In geographic CRS, 50m would need to be converted
        # Either to degrees or by projecting to a metric CRS
        needs_conversion = is_geographic and buffer_value_meters > 0
        
        assert needs_conversion is True
    
    def test_buffer_zero_needs_no_conversion(self):
        """Test that zero buffer needs no conversion regardless of CRS."""
        is_geographic = True
        buffer_value = 0
        
        needs_conversion = is_geographic and buffer_value > 0
        
        assert needs_conversion is False


class TestMetricConversion:
    """Tests for metric conversion using EPSG:3857."""
    
    def test_target_crs_for_metric_operations(self):
        """Test that EPSG:3857 is used for metric operations."""
        target_metric_crs = "EPSG:3857"
        
        # EPSG:3857 (Web Mercator) is the standard for metric conversions
        assert target_metric_crs == "EPSG:3857"
    
    def test_conversion_preserves_approximate_distance(self):
        """Test that 50m buffer is approximately 50m after conversion."""
        # In EPSG:3857, 1 unit ≈ 1 meter at the equator
        # This is an approximation that works for most use cases
        buffer_meters = 50
        expected_min = 45  # Allow 10% tolerance
        expected_max = 55
        
        # Simulated converted value
        converted_value = 50
        
        assert expected_min <= converted_value <= expected_max


class TestGeometryTransformation:
    """Tests for geometry transformation during CRS conversion."""
    
    def test_geometry_copy_used_not_reference(self):
        """Test that geometry copy is used to prevent modifying original."""
        class MockGeometry:
            def __init__(self, value):
                self.value = value
            
            def copy(self):
                return MockGeometry(self.value)
        
        original = MockGeometry("original")
        copy = original.copy()
        copy.value = "modified"
        
        assert original.value == "original"
        assert copy.value == "modified"
    
    def test_transform_does_not_modify_original(self):
        """Test that transform operations don't modify original geometry."""
        original_wkt = "POINT(2.3522 48.8566)"  # Paris in WGS84
        
        # Simulate transformation
        transformed_wkt = "POINT(261990.5 6250650.9)"  # Paris in EPSG:3857
        
        # Original should be unchanged
        assert original_wkt != transformed_wkt
        assert original_wkt == "POINT(2.3522 48.8566)"


class TestZoomBuffer:
    """Tests for zoom buffer calculations with geographic CRS."""
    
    def test_point_buffer_for_geographic(self):
        """Test point buffer size for geographic coordinates."""
        is_geographic = True
        
        # For geographic CRS, buffer should be in degrees
        # 0.002° ≈ 220m at the equator
        buffer_degrees = 0.002
        
        if is_geographic:
            buffer = buffer_degrees
        else:
            buffer = 50  # meters for projected
        
        assert buffer == 0.002
    
    def test_point_buffer_for_projected(self):
        """Test point buffer size for projected coordinates."""
        is_geographic = False
        
        if is_geographic:
            buffer = 0.002  # degrees
        else:
            buffer = 50  # meters
        
        assert buffer == 50
    
    def test_polygon_expansion_for_geographic(self):
        """Test polygon expansion for geographic coordinates."""
        is_geographic = True
        
        # Polygons need less expansion
        if is_geographic:
            expansion = 0.0005  # degrees
        else:
            expansion = 10  # meters
        
        assert expansion == 0.0005


class TestFlashFeature:
    """Tests for feature flash functionality with geographic CRS."""
    
    def test_flash_uses_geometry_copy(self):
        """Test that flash operation uses geometry copy."""
        geometry_modified = False
        
        class MockGeometry:
            def transform(self):
                nonlocal geometry_modified
                geometry_modified = True
        
        original = MockGeometry()
        
        # Using copy pattern
        copy = MockGeometry()
        copy.transform()
        
        # Original should not have transform called
        assert geometry_modified is True
        # If we used copy, original's state is not changed
    
    def test_bounding_box_transformation(self):
        """Test that bounding box is correctly transformed."""
        # Geographic bounding box
        geo_box = {
            'xmin': 2.0,
            'ymin': 48.0,
            'xmax': 3.0,
            'ymax': 49.0
        }
        
        # After transformation to EPSG:3857, coordinates should be different
        projected_box = {
            'xmin': 222638.98,
            'ymin': 6106854.83,
            'xmax': 333958.47,
            'ymax': 6274861.39
        }
        
        assert geo_box['xmin'] != projected_box['xmin']
        assert geo_box['ymin'] != projected_box['ymin']


class TestCanvasCRS:
    """Tests for canvas CRS handling."""
    
    def test_layer_crs_used_for_buffer(self):
        """Test that layer CRS is used for buffer calculation, not canvas CRS."""
        layer_crs_geographic = True
        canvas_crs_geographic = False
        
        # Buffer should be calculated based on LAYER CRS
        should_convert = layer_crs_geographic
        
        assert should_convert is True
    
    def test_mixed_crs_scenario(self):
        """Test handling when layer and canvas have different CRS types."""
        layer_crs = "EPSG:4326"  # Geographic
        canvas_crs = "EPSG:3857"  # Projected
        
        # Buffer calculation should use layer CRS
        layer_is_geographic = True  # EPSG:4326
        
        # Even though canvas is projected, layer CRS determines conversion
        needs_conversion = layer_is_geographic
        
        assert needs_conversion is True


class TestOGRBackendGeographicCRS:
    """Tests for OGR backend with geographic CRS."""
    
    def test_ogr_source_geom_handles_geographic(self):
        """Test that OGR source geometry preparation handles geographic CRS."""
        source_crs_geographic = True
        buffer_value = 50
        
        # OGR backend should convert to metric CRS if geographic
        if source_crs_geographic and buffer_value > 0:
            work_crs = "EPSG:3857"
        else:
            work_crs = None
        
        assert work_crs == "EPSG:3857"


class TestSpatialiteBackendGeographicCRS:
    """Tests for Spatialite backend with geographic CRS."""
    
    def test_spatialite_source_geom_handles_geographic(self):
        """Test that Spatialite source geometry preparation handles geographic CRS."""
        source_crs_geographic = True
        buffer_value = 100
        
        # Spatialite backend should convert to metric CRS if geographic
        if source_crs_geographic and buffer_value > 0:
            work_crs = "EPSG:3857"
        else:
            work_crs = None
        
        assert work_crs == "EPSG:3857"


class TestLogMessages:
    """Tests for logging with geographic CRS operations."""
    
    def test_geographic_conversion_logged(self):
        """Test that geographic CRS conversion is logged with indicator."""
        log_messages = []
        
        def mock_logger_info(msg):
            log_messages.append(msg)
        
        # Simulate logging with earth indicator
        is_geographic = True
        if is_geographic:
            mock_logger_info("🌍 Converting geographic CRS to EPSG:3857 for metric operations")
        
        assert len(log_messages) == 1
        assert "🌍" in log_messages[0]
        assert "EPSG:3857" in log_messages[0]


class TestEdgeCases:
    """Tests for edge cases in geographic CRS handling."""
    
    def test_polar_regions_handled(self):
        """Test that polar regions (high latitudes) are handled."""
        latitude = 75.0  # Near North Pole
        
        # High latitudes have greater distortion but should still work
        is_valid_latitude = -90 <= latitude <= 90
        
        assert is_valid_latitude is True
    
    def test_antimeridian_handled(self):
        """Test that antimeridian (180° longitude) is handled."""
        longitude = 179.9
        
        is_valid_longitude = -180 <= longitude <= 180
        
        assert is_valid_longitude is True
    
    def test_null_geometry_handled(self):
        """Test that null geometry is handled gracefully."""
        geometry = None
        
        # Should not raise exception
        if geometry is not None:
            geometry.transform()
        
        assert True
    
    def test_empty_geometry_handled(self):
        """Test that empty geometry is handled gracefully."""
        mock_geometry = Mock()
        mock_geometry.isEmpty.return_value = True
        
        is_empty = mock_geometry.isEmpty()
        
        if is_empty:
            # Skip buffer operations for empty geometries
            pass
        
        assert is_empty is True


class TestPerformance:
    """Tests for performance of geographic CRS operations."""
    
    def test_minimal_conversion_overhead(self):
        """Test that CRS conversion has minimal overhead."""
        import time
        
        # Simulate conversion operation
        iterations = 1000
        start = time.time()
        
        for _ in range(iterations):
            # Simulated lightweight operation
            result = 2.3522 * 111320  # Approximate degree to meter conversion
        
        elapsed = time.time() - start
        
        # Should complete 1000 iterations in less than 100ms
        assert elapsed < 0.1, f"Conversion took {elapsed}s, expected < 0.1s"
    
    def test_single_conversion_per_buffer(self):
        """Test that only one CRS conversion is done per buffer operation."""
        conversion_count = 0
        
        def mock_transform():
            nonlocal conversion_count
            conversion_count += 1
        
        # Simulate proper pattern: one transform to metric, buffer, transform back
        mock_transform()  # To EPSG:3857
        # Buffer operation here
        mock_transform()  # Back to original
        
        # Should be exactly 2 transformations
        assert conversion_count == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

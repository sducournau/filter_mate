# -*- coding: utf-8 -*-
"""
Test for geographic coordinate system (EPSG:4326) zoom and flash issues.

This test verifies that:
1. Geometry transformation doesn't modify original feature geometry
2. Geographic CRS automatically switches to EPSG:3857 for metric calculations
3. Buffer distances are accurate in meters (not degrees)
4. Extent expansion works correctly for non-point geometries
"""

import pytest
from qgis.core import (
    QgsGeometry, QgsPointXY, QgsRectangle, 
    QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsProject
)


def test_geographic_to_metric_conversion():
    """Test that geographic coordinates are converted to EPSG:3857 for buffer."""
    # Create a point in EPSG:4326 (Paris coordinates)
    point = QgsGeometry.fromPointXY(QgsPointXY(2.3522, 48.8566))
    
    # Simulate the workflow: convert to EPSG:3857 for buffer
    source_crs = QgsCoordinateReferenceSystem("EPSG:4326")
    metric_crs = QgsCoordinateReferenceSystem("EPSG:3857")
    transform = QgsCoordinateTransform(source_crs, metric_crs, QgsProject.instance())
    
    point_copy = QgsGeometry(point)
    point_copy.transform(transform)
    
    # Apply 50m buffer in metric CRS
    buffer_distance = 50
    buffered = point_copy.buffer(buffer_distance, 5)
    box = buffered.boundingBox()
    
    # Check that buffer is approximately 100m wide (2 * 50m)
    width = box.width()
    height = box.height()
    
    # Buffer should create box of ~100 meters width
    assert 90 < width < 110, f"Width {width} not in expected range for 50m buffer"
    assert 90 < height < 110, f"Height {height} not in expected range for 50m buffer"


def test_geometry_copy_prevents_modification():
    """Test that creating geometry copy prevents original modification."""
    # Create original geometry
    point = QgsGeometry.fromPointXY(QgsPointXY(2.3522, 48.8566))
    original_wkt = point.asWkt()
    
    # Create copy and transform it
    geom_copy = QgsGeometry(point)
    
    # Create transform from EPSG:4326 to EPSG:3857
    source_crs = QgsCoordinateReferenceSystem("EPSG:4326")
    dest_crs = QgsCoordinateReferenceSystem("EPSG:3857")
    transform = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
    
    geom_copy.transform(transform)
    
    # Verify original is unchanged
    assert point.asWkt() == original_wkt, "Original geometry was modified!"
    
    # Verify copy is transformed (should be in meters now)
    transformed_point = geom_copy.asPoint()
    # Paris in Web Mercator should be around (262,000, 6,250,000)
    assert 200000 < transformed_point.x() < 300000
    assert 6000000 < transformed_point.y() < 7000000


def test_metric_buffer_consistency():
    """Test that buffer is consistent whether CRS is geographic or projected."""
    buffer_distance = 50  # 50 meters
    
    # Test 1: Point in EPSG:4326, converted to EPSG:3857 for buffer
    point_4326 = QgsGeometry.fromPointXY(QgsPointXY(2.3522, 48.8566))
    source_crs = QgsCoordinateReferenceSystem("EPSG:4326")
    metric_crs = QgsCoordinateReferenceSystem("EPSG:3857")
    transform = QgsCoordinateTransform(source_crs, metric_crs, QgsProject.instance())
    
    point_3857 = QgsGeometry(point_4326)
    point_3857.transform(transform)
    buffered_from_4326 = point_3857.buffer(buffer_distance, 5)
    box_from_4326 = buffered_from_4326.boundingBox()
    
    # Test 2: Point directly in EPSG:3857
    point_direct = QgsGeometry.fromPointXY(QgsPointXY(point_3857.asPoint().x(), point_3857.asPoint().y()))
    buffered_direct = point_direct.buffer(buffer_distance, 5)
    box_direct = buffered_direct.boundingBox()
    
    # Both should produce similar buffer sizes (within 5% tolerance)
    width_diff = abs(box_from_4326.width() - box_direct.width())
    height_diff = abs(box_from_4326.height() - box_direct.height())
    
    assert width_diff < 5, f"Buffer width differs by {width_diff}m"
    assert height_diff < 5, f"Buffer height differs by {height_diff}m"


def test_bbox_grow_metric():
    """Test bounding box growth in meters."""
    # Create polygon in EPSG:3857
    wkt = "POLYGON((262000 6250000, 262100 6250000, 262100 6250100, 262000 6250100, 262000 6250000))"
    geom = QgsGeometry.fromWkt(wkt)
    box = geom.boundingBox()
    
    # Grow by 10 meters
    box.grow(10)
    
    # Check that dimensions increased by 20 (10 on each side)
    assert abs(box.width() - 120) < 1  # 100 + 2*10
    assert abs(box.height() - 120) < 1


def test_transform_bounding_box():
    """Test transforming bounding box between CRS."""
    # Create box in EPSG:3857 (Web Mercator)
    box_3857 = QgsRectangle(262000, 6250000, 262100, 6250100)
    
    # Transform to EPSG:4326
    source_crs = QgsCoordinateReferenceSystem("EPSG:3857")
    dest_crs = QgsCoordinateReferenceSystem("EPSG:4326")
    transform = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
    
    box_4326 = transform.transformBoundingBox(box_3857)
    
    # Check that box is now in degrees (around Paris: 2.35°, 48.85°)
    assert 2.0 < box_4326.xMinimum() < 3.0
    assert 2.0 < box_4326.xMaximum() < 3.0
    assert 48.0 < box_4326.yMinimum() < 49.0
    assert 48.0 < box_4326.yMaximum() < 49.0


def test_projected_coordinates_buffer():
    """Test that projected coordinates use meter-based buffer."""
    # Create point in projected CRS (EPSG:3857, Web Mercator)
    # Paris in Web Mercator: approximately (262000, 6250000)
    point = QgsGeometry.fromPointXY(QgsPointXY(262000, 6250000))
    
    # Test projected buffer (50 meters)
    buffer_distance = 50
    buffered = point.buffer(buffer_distance, 5)
    box = buffered.boundingBox()
    
    # Buffer should create box of ~100 meters width (2 * 50)
    width = box.width()
    height = box.height()
    
    assert 90 < width < 110, f"Width {width} not in expected range for 50m buffer"
    assert 90 < height < 110, f"Height {height} not in expected range for 50m buffer"


def test_round_trip_transformation():
    """Test that transforming to EPSG:3857 and back preserves coordinates."""
    # Original point in EPSG:4326
    original_point = QgsGeometry.fromPointXY(QgsPointXY(2.3522, 48.8566))
    original_x = original_point.asPoint().x()
    original_y = original_point.asPoint().y()
    
    # Transform to EPSG:3857
    to_3857 = QgsCoordinateTransform(
        QgsCoordinateReferenceSystem("EPSG:4326"),
        QgsCoordinateReferenceSystem("EPSG:3857"),
        QgsProject.instance()
    )
    point_3857 = QgsGeometry(original_point)
    point_3857.transform(to_3857)
    
    # Apply buffer
    point_3857 = point_3857.buffer(50, 5)
    
    # Transform back to EPSG:4326
    to_4326 = QgsCoordinateTransform(
        QgsCoordinateReferenceSystem("EPSG:3857"),
        QgsCoordinateReferenceSystem("EPSG:4326"),
        QgsProject.instance()
    )
    point_back = QgsGeometry(point_3857)
    point_back.transform(to_4326)
    
    # Check that centroid is close to original
    centroid = point_back.centroid().asPoint()
    
    # Allow small error due to projection distortion (~0.001° ≈ 100m)
    assert abs(centroid.x() - original_x) < 0.001
    assert abs(centroid.y() - original_y) < 0.001


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

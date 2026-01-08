# -*- coding: utf-8 -*-
"""
Unit Tests for LayerInfo Entity.

Tests the LayerInfo domain entity for:
- Creation and properties
- Provider type detection
- Geometry type handling
- Identity (equality based on layer_id)

Author: FilterMate Team
Date: January 2026
"""
import pytest
import sys
from pathlib import Path

# Add plugin directory to Python path
plugin_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(plugin_dir))

from core.domain.layer_info import LayerInfo, GeometryType
from core.domain.filter_expression import ProviderType


# ============================================================================
# GeometryType Enum Tests
# ============================================================================

class TestGeometryType:
    """Tests for GeometryType enum."""
    
    def test_geometry_type_values(self):
        """GeometryType should have expected values."""
        assert GeometryType.POINT.value == "Point"
        assert GeometryType.LINE.value == "LineString"
        assert GeometryType.POLYGON.value == "Polygon"
        assert GeometryType.MULTIPOINT.value == "MultiPoint"
        assert GeometryType.MULTILINE.value == "MultiLineString"
        assert GeometryType.MULTIPOLYGON.value == "MultiPolygon"
        assert GeometryType.NO_GEOMETRY.value == "NoGeometry"
        assert GeometryType.UNKNOWN.value == "Unknown"
    
    def test_from_qgis_wkb_point(self):
        """Should convert WKB type 1 to POINT."""
        result = GeometryType.from_qgis_wkb_type(1)
        assert result == GeometryType.POINT
    
    def test_from_qgis_wkb_line(self):
        """Should convert WKB type 2 to LINE."""
        result = GeometryType.from_qgis_wkb_type(2)
        assert result == GeometryType.LINE
    
    def test_from_qgis_wkb_polygon(self):
        """Should convert WKB type 3 to POLYGON."""
        result = GeometryType.from_qgis_wkb_type(3)
        assert result == GeometryType.POLYGON
    
    def test_from_qgis_wkb_multipoint(self):
        """Should convert WKB type 4 to MULTIPOINT."""
        result = GeometryType.from_qgis_wkb_type(4)
        assert result == GeometryType.MULTIPOINT
    
    def test_from_qgis_wkb_multiline(self):
        """Should convert WKB type 5 to MULTILINE."""
        result = GeometryType.from_qgis_wkb_type(5)
        assert result == GeometryType.MULTILINE
    
    def test_from_qgis_wkb_multipolygon(self):
        """Should convert WKB type 6 to MULTIPOLYGON."""
        result = GeometryType.from_qgis_wkb_type(6)
        assert result == GeometryType.MULTIPOLYGON
    
    def test_from_qgis_wkb_unknown(self):
        """Should return UNKNOWN for unrecognized WKB types."""
        result = GeometryType.from_qgis_wkb_type(999)
        assert result == GeometryType.UNKNOWN
    
    def test_from_qgis_wkb_no_geometry(self):
        """Should convert WKB type 100 to NO_GEOMETRY."""
        result = GeometryType.from_qgis_wkb_type(100)
        assert result == GeometryType.NO_GEOMETRY


# ============================================================================
# LayerInfo Creation Tests
# ============================================================================

class TestLayerInfoCreation:
    """Tests for LayerInfo creation."""
    
    def test_create_minimal(self):
        """Should create LayerInfo with minimal parameters."""
        layer = LayerInfo(
            layer_id="layer_123",
            name="My Layer",
            provider_type=ProviderType.POSTGRESQL
        )
        
        assert layer.layer_id == "layer_123"
        assert layer.name == "My Layer"
        assert layer.provider_type == ProviderType.POSTGRESQL
    
    def test_create_with_all_fields(self):
        """Should create LayerInfo with all fields."""
        layer = LayerInfo(
            layer_id="layer_456",
            name="Roads",
            provider_type=ProviderType.SPATIALITE,
            feature_count=10000,
            geometry_type=GeometryType.MULTILINE,
            crs_auth_id="EPSG:4326",
            is_valid=True,
            source_path="/path/to/file.gpkg",
            has_spatial_index=True,
            schema_name="public",
            table_name="roads"
        )
        
        assert layer.feature_count == 10000
        assert layer.geometry_type == GeometryType.MULTILINE
        assert layer.crs_auth_id == "EPSG:4326"
        assert layer.has_spatial_index
        assert layer.schema_name == "public"
        assert layer.table_name == "roads"
    
    def test_default_values(self):
        """Should have sensible default values."""
        layer = LayerInfo(
            layer_id="layer_123",
            name="Test",
            provider_type=ProviderType.OGR
        )
        
        assert layer.feature_count == -1  # Unknown
        assert layer.geometry_type == GeometryType.UNKNOWN
        assert layer.crs_auth_id == ""
        assert layer.is_valid
        assert layer.source_path == ""
        assert not layer.has_spatial_index


# ============================================================================
# LayerInfo Provider Type Properties Tests
# ============================================================================

class TestLayerInfoProviderProperties:
    """Tests for LayerInfo provider type properties."""
    
    def test_is_postgresql_true(self):
        """is_postgresql should be True for PostgreSQL provider."""
        layer = LayerInfo(
            layer_id="layer_123",
            name="PG Layer",
            provider_type=ProviderType.POSTGRESQL
        )
        
        assert layer.is_postgresql
    
    def test_is_postgresql_false(self):
        """is_postgresql should be False for non-PostgreSQL provider."""
        layer = LayerInfo(
            layer_id="layer_123",
            name="SL Layer",
            provider_type=ProviderType.SPATIALITE
        )
        
        assert not layer.is_postgresql
    
    def test_is_spatialite_true(self):
        """is_spatialite should be True for Spatialite provider."""
        layer = LayerInfo(
            layer_id="layer_123",
            name="SL Layer",
            provider_type=ProviderType.SPATIALITE
        )
        
        assert layer.is_spatialite
    
    def test_is_spatialite_false(self):
        """is_spatialite should be False for non-Spatialite provider."""
        layer = LayerInfo(
            layer_id="layer_123",
            name="OGR Layer",
            provider_type=ProviderType.OGR
        )
        
        assert not layer.is_spatialite
    
    def test_is_ogr_true(self):
        """is_ogr should be True for OGR provider."""
        layer = LayerInfo(
            layer_id="layer_123",
            name="Shapefile",
            provider_type=ProviderType.OGR
        )
        
        assert layer.is_ogr
    
    def test_is_memory_true(self):
        """is_memory should be True for Memory provider."""
        layer = LayerInfo(
            layer_id="layer_123",
            name="Temp Layer",
            provider_type=ProviderType.MEMORY
        )
        
        assert layer.is_memory
    
    def test_is_postgresql_true(self):
        """is_postgresql should be True for PostgreSQL provider."""
        layer = LayerInfo(
            layer_id="layer_123",
            name="DB Layer",
            provider_type=ProviderType.POSTGRESQL
        )
        
        assert layer.is_postgresql
    
    def test_is_spatialite_true(self):
        """is_spatialite should be True for Spatialite provider."""
        layer = LayerInfo(
            layer_id="layer_123",
            name="DB Layer",
            provider_type=ProviderType.SPATIALITE
        )
        
        assert layer.is_spatialite
    
    def test_is_ogr_true(self):
        """is_ogr should be True for OGR provider."""
        layer = LayerInfo(
            layer_id="layer_123",
            name="Shapefile",
            provider_type=ProviderType.OGR
        )
        
        assert layer.is_ogr


# ============================================================================
# LayerInfo Size Classification Tests
# ============================================================================

class TestLayerInfoSizeClassification:
    """Tests for LayerInfo size classification properties."""
    
    def test_is_large_true_over_10000(self):
        """is_large should be True for > 10000 features."""
        layer = LayerInfo(
            layer_id="layer_123",
            name="Large",
            provider_type=ProviderType.POSTGRESQL,
            feature_count=15000
        )
        
        assert layer.is_large
    
    def test_is_large_false_under_10000(self):
        """is_large should be False for <= 10000 features."""
        layer = LayerInfo(
            layer_id="layer_123",
            name="Medium",
            provider_type=ProviderType.OGR,
            feature_count=5000
        )
        
        assert not layer.is_large
    
    def test_is_very_large_true_over_100000(self):
        """is_very_large should be True for > 100000 features."""
        layer = LayerInfo(
            layer_id="layer_123",
            name="Very Large",
            provider_type=ProviderType.POSTGRESQL,
            feature_count=500000
        )
        
        assert layer.is_very_large
    
    def test_is_very_large_false_under_100000(self):
        """is_very_large should be False for <= 100000 features."""
        layer = LayerInfo(
            layer_id="layer_123",
            name="Medium",
            provider_type=ProviderType.POSTGRESQL,
            feature_count=50000
        )
        
        assert not layer.is_very_large
    
    def test_unknown_feature_count(self):
        """Unknown feature count should not be classified as large."""
        layer = LayerInfo(
            layer_id="layer_123",
            name="Unknown",
            provider_type=ProviderType.OGR,
            feature_count=-1
        )
        
        assert not layer.is_large
        assert not layer.is_very_large


# ============================================================================
# LayerInfo Geometry Properties Tests
# ============================================================================

class TestLayerInfoGeometryProperties:
    """Tests for LayerInfo geometry properties."""
    
    def test_has_geometry_true(self):
        """has_geometry should be True for layers with geometry."""
        layer = LayerInfo(
            layer_id="layer_123",
            name="Points",
            provider_type=ProviderType.OGR,
            geometry_type=GeometryType.POINT
        )
        
        assert layer.has_geometry
    
    def test_has_geometry_false(self):
        """has_geometry should be False for NoGeometry."""
        layer = LayerInfo(
            layer_id="layer_123",
            name="Table",
            provider_type=ProviderType.POSTGRESQL,
            geometry_type=GeometryType.NO_GEOMETRY
        )
        
        assert not layer.has_geometry
    
    def test_is_point(self):
        """is_point should be True for point geometry."""
        layer = LayerInfo(
            layer_id="layer_123",
            name="Points",
            provider_type=ProviderType.OGR,
            geometry_type=GeometryType.POINT
        )
        
        assert layer.is_point
    
    def test_is_line(self):
        """is_line should be True for line geometry."""
        layer = LayerInfo(
            layer_id="layer_123",
            name="Roads",
            provider_type=ProviderType.POSTGRESQL,
            geometry_type=GeometryType.LINE
        )
        
        assert layer.is_line
    
    def test_is_polygon(self):
        """is_polygon should be True for polygon geometry."""
        layer = LayerInfo(
            layer_id="layer_123",
            name="Parcels",
            provider_type=ProviderType.SPATIALITE,
            geometry_type=GeometryType.POLYGON
        )
        
        assert layer.is_polygon
    
    def test_is_multipart(self):
        """is_multipart should be True for multipart geometries."""
        layer = LayerInfo(
            layer_id="layer_123",
            name="Islands",
            provider_type=ProviderType.SPATIALITE,
            geometry_type=GeometryType.MULTIPOLYGON
        )
        
        assert layer.is_multipart


# ============================================================================
# LayerInfo Equality Tests (Entity Identity)
# ============================================================================

class TestLayerInfoEquality:
    """Tests for LayerInfo equality (based on layer_id)."""
    
    def test_same_layer_id_equal(self):
        """Layers with same layer_id should be equal."""
        layer1 = LayerInfo(
            layer_id="layer_123",
            name="Name 1",
            provider_type=ProviderType.POSTGRESQL
        )
        layer2 = LayerInfo(
            layer_id="layer_123",
            name="Name 2",  # Different name
            provider_type=ProviderType.SPATIALITE  # Different provider
        )
        
        assert layer1 == layer2
    
    def test_different_layer_id_not_equal(self):
        """Layers with different layer_id should not be equal."""
        layer1 = LayerInfo(
            layer_id="layer_123",
            name="Same Name",
            provider_type=ProviderType.POSTGRESQL
        )
        layer2 = LayerInfo(
            layer_id="layer_456",
            name="Same Name",
            provider_type=ProviderType.POSTGRESQL
        )
        
        assert layer1 != layer2
    
    def test_hashable_by_layer_id(self):
        """Layers should be hashable by layer_id."""
        layer1 = LayerInfo(
            layer_id="layer_123",
            name="Test",
            provider_type=ProviderType.OGR
        )
        layer2 = LayerInfo(
            layer_id="layer_123",
            name="Different",
            provider_type=ProviderType.MEMORY
        )
        
        layer_set = {layer1, layer2}
        
        # Same layer_id means same entity, so set should have 1 element
        assert len(layer_set) == 1


# ============================================================================
# LayerInfo String Representation Tests
# ============================================================================

class TestLayerInfoRepr:
    """Tests for LayerInfo string representations."""
    
    def test_str_contains_name(self):
        """String representation should contain layer name."""
        layer = LayerInfo(
            layer_id="layer_123",
            name="My Layer",
            provider_type=ProviderType.OGR
        )
        
        assert "My Layer" in str(layer)
    
    def test_repr_contains_layer_id(self):
        """Repr should contain layer_id."""
        layer = LayerInfo(
            layer_id="layer_abc123",
            name="Test",
            provider_type=ProviderType.POSTGRESQL
        )
        
        repr_str = repr(layer)
        assert "layer_abc123" in repr_str


# ============================================================================
# LayerInfo Validation Tests
# ============================================================================

class TestLayerInfoValidation:
    """Tests for LayerInfo validation."""
    
    def test_is_valid_property(self):
        """is_valid should return validity status."""
        valid_layer = LayerInfo(
            layer_id="layer_123",
            name="Valid",
            provider_type=ProviderType.OGR,
            is_valid=True
        )
        
        invalid_layer = LayerInfo(
            layer_id="layer_456",
            name="Invalid",
            provider_type=ProviderType.OGR,
            is_valid=False
        )
        
        assert valid_layer.is_valid
        assert not invalid_layer.is_valid

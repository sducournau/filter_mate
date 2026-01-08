"""
Tests for LayerInfo Entity.

Part of Phase 3 Core Domain Layer implementation.
"""
import pytest
from core.domain.layer_info import LayerInfo, GeometryType
from core.domain.filter_expression import ProviderType


class TestLayerInfoCreation:
    """Tests for LayerInfo creation and validation."""

    def test_create_simple_layer(self):
        """Test creating a simple layer info."""
        layer = LayerInfo.create(
            layer_id="layer_123",
            name="Roads",
            provider_type=ProviderType.POSTGRESQL
        )
        assert layer.layer_id == "layer_123"
        assert layer.name == "Roads"
        assert layer.provider_type == ProviderType.POSTGRESQL
        assert layer.is_valid

    def test_create_with_all_attributes(self):
        """Test creating layer with all attributes."""
        layer = LayerInfo.create(
            layer_id="layer_456",
            name="Buildings",
            provider_type=ProviderType.SPATIALITE,
            feature_count=5000,
            geometry_type=GeometryType.POLYGON,
            crs_auth_id="EPSG:4326",
            source_path="/data/buildings.sqlite",
            has_spatial_index=True,
            schema_name="public",
            table_name="buildings"
        )
        assert layer.feature_count == 5000
        assert layer.geometry_type == GeometryType.POLYGON
        assert layer.crs_auth_id == "EPSG:4326"
        assert layer.has_spatial_index

    def test_empty_layer_id_raises_error(self):
        """Test that empty layer_id raises ValueError."""
        with pytest.raises(ValueError, match="layer_id cannot be empty"):
            LayerInfo(
                layer_id="",
                name="Test",
                provider_type=ProviderType.OGR
            )

    def test_empty_name_raises_error(self):
        """Test that empty name raises ValueError."""
        with pytest.raises(ValueError, match="name cannot be empty"):
            LayerInfo(
                layer_id="layer_123",
                name="",
                provider_type=ProviderType.OGR
            )

    def test_invalid_provider_type_raises_error(self):
        """Test that invalid provider_type raises TypeError."""
        with pytest.raises(TypeError, match="provider_type must be ProviderType"):
            LayerInfo(
                layer_id="layer_123",
                name="Test",
                provider_type="invalid"
            )


class TestLayerInfoEquality:
    """Tests for LayerInfo entity equality semantics."""

    def test_equality_based_on_layer_id(self):
        """Test that equality is based on layer_id only."""
        layer1 = LayerInfo.create(
            layer_id="layer_123",
            name="Roads",
            provider_type=ProviderType.POSTGRESQL,
            feature_count=100
        )
        layer2 = LayerInfo.create(
            layer_id="layer_123",
            name="Different Name",  # Different name
            provider_type=ProviderType.SPATIALITE,  # Different provider
            feature_count=999  # Different count
        )
        # Same layer_id = equal entities
        assert layer1 == layer2

    def test_inequality_different_layer_id(self):
        """Test that different layer_ids are not equal."""
        layer1 = LayerInfo.create(
            layer_id="layer_123",
            name="Roads",
            provider_type=ProviderType.POSTGRESQL
        )
        layer2 = LayerInfo.create(
            layer_id="layer_456",
            name="Roads",  # Same name
            provider_type=ProviderType.POSTGRESQL  # Same provider
        )
        assert layer1 != layer2

    def test_hash_based_on_layer_id(self):
        """Test that hash is based on layer_id."""
        layer1 = LayerInfo.create(
            layer_id="layer_123",
            name="Roads",
            provider_type=ProviderType.POSTGRESQL
        )
        layer2 = LayerInfo.create(
            layer_id="layer_123",
            name="Different",
            provider_type=ProviderType.OGR
        )
        # Same hash = can be used in sets/dicts
        assert hash(layer1) == hash(layer2)
        
        # Can use in set
        layer_set = {layer1, layer2}
        assert len(layer_set) == 1


class TestLayerInfoProperties:
    """Tests for LayerInfo property methods."""

    def test_is_postgresql(self):
        """Test is_postgresql property."""
        layer = LayerInfo.create(
            layer_id="layer_123",
            name="Test",
            provider_type=ProviderType.POSTGRESQL
        )
        assert layer.is_postgresql
        assert not layer.is_spatialite
        assert not layer.is_ogr

    def test_is_spatialite(self):
        """Test is_spatialite property."""
        layer = LayerInfo.create(
            layer_id="layer_123",
            name="Test",
            provider_type=ProviderType.SPATIALITE
        )
        assert layer.is_spatialite
        assert not layer.is_postgresql

    def test_is_ogr(self):
        """Test is_ogr property."""
        layer = LayerInfo.create(
            layer_id="layer_123",
            name="Test",
            provider_type=ProviderType.OGR
        )
        assert layer.is_ogr

    def test_is_memory(self):
        """Test is_memory property."""
        layer = LayerInfo.create(
            layer_id="layer_123",
            name="Test",
            provider_type=ProviderType.MEMORY
        )
        assert layer.is_memory


class TestLayerInfoGeometry:
    """Tests for LayerInfo geometry properties."""

    def test_has_geometry_true(self):
        """Test has_geometry for layers with geometry."""
        layer = LayerInfo.create(
            layer_id="layer_123",
            name="Test",
            provider_type=ProviderType.OGR,
            geometry_type=GeometryType.POLYGON
        )
        assert layer.has_geometry

    def test_has_geometry_false(self):
        """Test has_geometry for layers without geometry."""
        layer = LayerInfo.create(
            layer_id="layer_123",
            name="Test",
            provider_type=ProviderType.OGR,
            geometry_type=GeometryType.NO_GEOMETRY
        )
        assert not layer.has_geometry

    def test_is_polygon(self):
        """Test is_polygon for polygon layers."""
        layer = LayerInfo.create(
            layer_id="layer_123",
            name="Test",
            provider_type=ProviderType.OGR,
            geometry_type=GeometryType.POLYGON
        )
        assert layer.is_polygon
        assert not layer.is_line
        assert not layer.is_point

    def test_is_polygon_multipolygon(self):
        """Test is_polygon includes multipolygon."""
        layer = LayerInfo.create(
            layer_id="layer_123",
            name="Test",
            provider_type=ProviderType.OGR,
            geometry_type=GeometryType.MULTIPOLYGON
        )
        assert layer.is_polygon

    def test_is_line(self):
        """Test is_line for line layers."""
        layer = LayerInfo.create(
            layer_id="layer_123",
            name="Test",
            provider_type=ProviderType.OGR,
            geometry_type=GeometryType.LINE
        )
        assert layer.is_line

    def test_is_point(self):
        """Test is_point for point layers."""
        layer = LayerInfo.create(
            layer_id="layer_123",
            name="Test",
            provider_type=ProviderType.OGR,
            geometry_type=GeometryType.POINT
        )
        assert layer.is_point

    def test_is_multipart(self):
        """Test is_multipart for multipart geometries."""
        for geom_type in [GeometryType.MULTIPOINT, GeometryType.MULTILINE,
                          GeometryType.MULTIPOLYGON, GeometryType.GEOMETRY_COLLECTION]:
            layer = LayerInfo.create(
                layer_id="layer_123",
                name="Test",
                provider_type=ProviderType.OGR,
                geometry_type=geom_type
            )
            assert layer.is_multipart


class TestLayerInfoSize:
    """Tests for LayerInfo size properties."""

    def test_is_large(self):
        """Test is_large for large layers."""
        large_layer = LayerInfo.create(
            layer_id="layer_123",
            name="Test",
            provider_type=ProviderType.OGR,
            feature_count=50000
        )
        small_layer = LayerInfo.create(
            layer_id="layer_456",
            name="Test",
            provider_type=ProviderType.OGR,
            feature_count=5000
        )
        assert large_layer.is_large
        assert not small_layer.is_large

    def test_is_very_large(self):
        """Test is_very_large for very large layers."""
        very_large = LayerInfo.create(
            layer_id="layer_123",
            name="Test",
            provider_type=ProviderType.OGR,
            feature_count=500000
        )
        assert very_large.is_very_large


class TestLayerInfoQualifiedName:
    """Tests for qualified table name."""

    def test_qualified_name_with_schema(self):
        """Test qualified name with schema and table."""
        layer = LayerInfo.create(
            layer_id="layer_123",
            name="Test",
            provider_type=ProviderType.POSTGRESQL,
            schema_name="public",
            table_name="roads"
        )
        assert layer.qualified_table_name == "public.roads"

    def test_qualified_name_without_schema(self):
        """Test qualified name without schema."""
        layer = LayerInfo.create(
            layer_id="layer_123",
            name="Test",
            provider_type=ProviderType.SPATIALITE,
            table_name="roads"
        )
        assert layer.qualified_table_name == "roads"

    def test_qualified_name_fallback_to_name(self):
        """Test qualified name fallback to layer name."""
        layer = LayerInfo.create(
            layer_id="layer_123",
            name="Roads Layer",
            provider_type=ProviderType.OGR
        )
        assert layer.qualified_table_name == "Roads Layer"


class TestLayerInfoWithMethods:
    """Tests for LayerInfo with_* methods."""

    def test_with_feature_count(self):
        """Test with_feature_count creates new instance."""
        layer1 = LayerInfo.create(
            layer_id="layer_123",
            name="Test",
            provider_type=ProviderType.OGR,
            feature_count=100
        )
        layer2 = layer1.with_feature_count(500)
        
        # Original unchanged
        assert layer1.feature_count == 100
        # New instance has updated count
        assert layer2.feature_count == 500
        # Same identity
        assert layer1 == layer2

    def test_with_spatial_index(self):
        """Test with_spatial_index creates new instance."""
        layer1 = LayerInfo.create(
            layer_id="layer_123",
            name="Test",
            provider_type=ProviderType.OGR,
            has_spatial_index=False
        )
        layer2 = layer1.with_spatial_index(True)
        
        assert not layer1.has_spatial_index
        assert layer2.has_spatial_index


class TestGeometryType:
    """Tests for GeometryType enum."""

    def test_all_types_exist(self):
        """Test all geometry types are defined."""
        expected_types = [
            'POINT', 'LINE', 'POLYGON', 'MULTIPOINT',
            'MULTILINE', 'MULTIPOLYGON', 'GEOMETRY_COLLECTION',
            'NO_GEOMETRY', 'UNKNOWN'
        ]
        for type_name in expected_types:
            assert hasattr(GeometryType, type_name)

    def test_from_qgis_wkb_type_point(self):
        """Test conversion from QGIS WKB type for point."""
        result = GeometryType.from_qgis_wkb_type(1)
        assert result == GeometryType.POINT

    def test_from_qgis_wkb_type_polygon(self):
        """Test conversion from QGIS WKB type for polygon."""
        result = GeometryType.from_qgis_wkb_type(3)
        assert result == GeometryType.POLYGON

    def test_from_qgis_wkb_type_unknown(self):
        """Test conversion from unknown WKB type."""
        result = GeometryType.from_qgis_wkb_type(999)
        assert result == GeometryType.UNKNOWN

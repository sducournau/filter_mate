"""
Layer Info Entity.

Entity representing QGIS layer metadata without QGIS dependencies.
Identity is based on layer_id.

This is a PURE PYTHON module with NO QGIS dependencies,
enabling true unit testing and clear separation of concerns.
"""
from dataclasses import dataclass
from enum import Enum

from .filter_expression import ProviderType


class GeometryType(Enum):
    """
    Geometry types supported.
    
    Maps to QGIS geometry types but defined here
    to maintain domain independence.
    """
    POINT = "Point"
    LINE = "LineString"
    POLYGON = "Polygon"
    MULTIPOINT = "MultiPoint"
    MULTILINE = "MultiLineString"
    MULTIPOLYGON = "MultiPolygon"
    GEOMETRY_COLLECTION = "GeometryCollection"
    NO_GEOMETRY = "NoGeometry"
    UNKNOWN = "Unknown"
    
    @classmethod
    def from_qgis_wkb_type(cls, wkb_type: int) -> 'GeometryType':
        """
        Convert QGIS WKB type to GeometryType.
        
        Args:
            wkb_type: QGIS QgsWkbTypes value
            
        Returns:
            Corresponding GeometryType enum value
        """
        # QGIS WKB types (simplified mapping)
        # Full mapping would require checking QgsWkbTypes constants
        wkb_mapping = {
            0: cls.UNKNOWN,
            1: cls.POINT,
            2: cls.LINE,
            3: cls.POLYGON,
            4: cls.MULTIPOINT,
            5: cls.MULTILINE,
            6: cls.MULTIPOLYGON,
            7: cls.GEOMETRY_COLLECTION,
            100: cls.NO_GEOMETRY,  # NoGeometry
        }
        return wkb_mapping.get(wkb_type, cls.UNKNOWN)


@dataclass
class LayerInfo:
    """
    Entity representing layer information.

    This is an Entity (not Value Object) because it has identity
    based on layer_id. Two LayerInfo objects with the same layer_id
    are considered equal, regardless of other attribute values.

    Attributes:
        layer_id: Unique QGIS layer identifier
        name: Layer display name
        provider_type: Data provider type
        feature_count: Number of features (may be -1 if unknown)
        geometry_type: Geometry type
        crs_auth_id: CRS authority ID (e.g., "EPSG:4326")
        is_valid: Whether layer is valid
        source_path: Data source path or connection string
        has_spatial_index: Whether layer has spatial index
        schema_name: Database schema name (PostgreSQL/Spatialite)
        table_name: Database table name
        pk_attr: Primary key attribute name (e.g., "id", "fid")
        geometry_column: Geometry column name (e.g., "geom", "geometry")
        
    Example:
        >>> layer = LayerInfo.create(
        ...     layer_id="layer_abc123",
        ...     name="Roads",
        ...     provider_type=ProviderType.POSTGRESQL
        ... )
        >>> layer.is_postgresql
        True
    """
    layer_id: str
    name: str
    provider_type: ProviderType
    feature_count: int = -1
    geometry_type: GeometryType = GeometryType.UNKNOWN
    crs_auth_id: str = ""
    is_valid: bool = True
    source_path: str = ""
    has_spatial_index: bool = False
    schema_name: str = ""
    table_name: str = ""
    pk_attr: str = ""
    geometry_column: str = "geom"

    def __eq__(self, other: object) -> bool:
        """
        Equality based on layer_id (entity semantics).
        
        Two LayerInfo entities with the same layer_id are considered
        equal, even if other attributes differ.
        """
        if not isinstance(other, LayerInfo):
            return NotImplemented
        return self.layer_id == other.layer_id

    def __hash__(self) -> int:
        """Hash based on layer_id."""
        return hash(self.layer_id)

    def __post_init__(self) -> None:
        """Validate layer info after initialization."""
        if not self.layer_id:
            raise ValueError("layer_id cannot be empty")
        if not self.name:
            raise ValueError("name cannot be empty")
        if not isinstance(self.provider_type, ProviderType):
            raise TypeError(f"provider_type must be ProviderType, got {type(self.provider_type)}")

    @classmethod
    def create(
        cls,
        layer_id: str,
        name: str,
        provider_type: ProviderType,
        **kwargs
    ) -> 'LayerInfo':
        """
        Factory method for creating LayerInfo.

        Args:
            layer_id: Unique layer identifier
            name: Layer display name
            provider_type: Data provider type
            **kwargs: Additional optional attributes

        Returns:
            LayerInfo instance
            
        Example:
            >>> info = LayerInfo.create(
            ...     layer_id="abc123",
            ...     name="Buildings",
            ...     provider_type=ProviderType.SPATIALITE,
            ...     feature_count=5000,
            ...     geometry_type=GeometryType.POLYGON
            ... )
        """
        return cls(
            layer_id=layer_id,
            name=name,
            provider_type=provider_type,
            **kwargs
        )

    @property
    def is_postgresql(self) -> bool:
        """Check if layer is PostgreSQL."""
        return self.provider_type == ProviderType.POSTGRESQL

    @property
    def is_spatialite(self) -> bool:
        """Check if layer is Spatialite."""
        return self.provider_type == ProviderType.SPATIALITE

    @property
    def is_ogr(self) -> bool:
        """Check if layer is OGR."""
        return self.provider_type == ProviderType.OGR

    @property
    def is_memory(self) -> bool:
        """Check if layer is memory layer."""
        return self.provider_type == ProviderType.MEMORY

    @property
    def has_geometry(self) -> bool:
        """Check if layer has geometry."""
        return self.geometry_type != GeometryType.NO_GEOMETRY

    @property
    def is_polygon(self) -> bool:
        """Check if layer has polygon geometry."""
        return self.geometry_type in (
            GeometryType.POLYGON,
            GeometryType.MULTIPOLYGON
        )

    @property
    def is_line(self) -> bool:
        """Check if layer has line geometry."""
        return self.geometry_type in (
            GeometryType.LINE,
            GeometryType.MULTILINE
        )

    @property
    def is_point(self) -> bool:
        """Check if layer has point geometry."""
        return self.geometry_type in (
            GeometryType.POINT,
            GeometryType.MULTIPOINT
        )

    @property
    def is_multipart(self) -> bool:
        """Check if layer has multipart geometry."""
        return self.geometry_type in (
            GeometryType.MULTIPOINT,
            GeometryType.MULTILINE,
            GeometryType.MULTIPOLYGON,
            GeometryType.GEOMETRY_COLLECTION
        )

    @property
    def is_large(self) -> bool:
        """Check if layer is considered large (>10000 features)."""
        return self.feature_count > 10000

    @property
    def is_very_large(self) -> bool:
        """Check if layer is very large (>100000 features)."""
        return self.feature_count > 100000

    @property
    def qualified_table_name(self) -> str:
        """
        Get fully qualified table name for database layers.
        
        Returns:
            schema.table for PostgreSQL, table for others
        """
        if self.schema_name and self.table_name:
            return f"{self.schema_name}.{self.table_name}"
        return self.table_name or self.name

    def with_feature_count(self, count: int) -> 'LayerInfo':
        """Return new LayerInfo with updated feature count."""
        return LayerInfo(
            layer_id=self.layer_id,
            name=self.name,
            provider_type=self.provider_type,
            feature_count=count,
            geometry_type=self.geometry_type,
            crs_auth_id=self.crs_auth_id,
            is_valid=self.is_valid,
            source_path=self.source_path,
            has_spatial_index=self.has_spatial_index,
            schema_name=self.schema_name,
            table_name=self.table_name
        )

    def with_spatial_index(self, has_index: bool) -> 'LayerInfo':
        """Return new LayerInfo with updated spatial index status."""
        return LayerInfo(
            layer_id=self.layer_id,
            name=self.name,
            provider_type=self.provider_type,
            feature_count=self.feature_count,
            geometry_type=self.geometry_type,
            crs_auth_id=self.crs_auth_id,
            is_valid=self.is_valid,
            source_path=self.source_path,
            has_spatial_index=has_index,
            schema_name=self.schema_name,
            table_name=self.table_name
        )

    def __str__(self) -> str:
        """Human-readable representation."""
        geom = f", {self.geometry_type.value}" if self.has_geometry else ", no geometry"
        count = f", {self.feature_count} features" if self.feature_count >= 0 else ""
        return f"LayerInfo({self.name}, {self.provider_type.value}{geom}{count})"

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"LayerInfo(layer_id={self.layer_id!r}, name={self.name!r}, "
            f"provider_type={self.provider_type}, feature_count={self.feature_count}, "
            f"geometry_type={self.geometry_type})"
        )

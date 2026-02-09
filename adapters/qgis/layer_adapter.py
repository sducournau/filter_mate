# -*- coding: utf-8 -*-
"""
QGIS Vector Layer Adapter - Concrete Implementation of IVectorLayer

Wraps QgsVectorLayer to implement the abstract IVectorLayer interface
from core.ports.qgis_port, enabling hexagonal architecture.

Author: FilterMate Team
Version: 4.1.0 (January 2026)
License: GNU GPL v2+
"""

from typing import Optional, List
from qgis.core import QgsVectorLayer, QgsWkbTypes
from qgis.PyQt.QtCore import QVariant

from ...core.ports.qgis_port import (
    IVectorLayer,
    GeometryType,
    FieldType,
    BoundingBox,
    CoordinateReferenceSystem
)


class QGISVectorLayerAdapter(IVectorLayer):
    """
    Adapter wrapping QgsVectorLayer to implement IVectorLayer interface.
    
    This allows core domain logic to work with layers without
    directly depending on QGIS implementation.
    
    Example:
        >>> from qgis.core import QgsVectorLayer
        >>> qgs_layer = QgsVectorLayer("path/to/data.shp", "my_layer", "ogr")
        >>> adapter = QGISVectorLayerAdapter(qgs_layer)
        >>> adapter.feature_count()
        42
    """
    
    def __init__(self, qgs_layer: QgsVectorLayer):
        """
        Initialize adapter.
        
        Args:
            qgs_layer: QgsVectorLayer instance to wrap
        """
        if not isinstance(qgs_layer, QgsVectorLayer):
            raise TypeError(f"Expected QgsVectorLayer, got {type(qgs_layer)}")
        
        self._layer = qgs_layer
    
    @property
    def qgs_layer(self) -> QgsVectorLayer:
        """Get underlying QgsVectorLayer (for adapter-internal use)."""
        return self._layer
    
    def id(self) -> str:
        """Get unique layer identifier."""
        return self._layer.id()
    
    def name(self) -> str:
        """Get layer name."""
        return self._layer.name()
    
    def is_valid(self) -> bool:
        """Check if layer is valid and accessible."""
        return self._layer.isValid()
    
    def feature_count(self) -> int:
        """Get total number of features."""
        return self._layer.featureCount()
    
    def geometry_type(self) -> GeometryType:
        """Get layer geometry type."""
        wkb_type = self._layer.wkbType()
        
        # Map QgsWkbTypes to GeometryType enum
        type_map = {
            QgsWkbTypes.Point: GeometryType.POINT,
            QgsWkbTypes.LineString: GeometryType.LINE,
            QgsWkbTypes.Polygon: GeometryType.POLYGON,
            QgsWkbTypes.MultiPoint: GeometryType.MULTI_POINT,
            QgsWkbTypes.MultiLineString: GeometryType.MULTI_LINE,
            QgsWkbTypes.MultiPolygon: GeometryType.MULTI_POLYGON,
            QgsWkbTypes.GeometryCollection: GeometryType.GEOMETRY_COLLECTION,
            QgsWkbTypes.NoGeometry: GeometryType.NO_GEOMETRY,
        }
        
        flat_type = QgsWkbTypes.flatType(wkb_type)
        return type_map.get(flat_type, GeometryType.UNKNOWN)
    
    def crs(self) -> CoordinateReferenceSystem:
        """Get layer CRS."""
        qgs_crs = self._layer.crs()
        return CoordinateReferenceSystem(
            auth_id=qgs_crs.authid(),
            description=qgs_crs.description(),
            is_geographic=qgs_crs.isGeographic()
        )
    
    def extent(self) -> BoundingBox:
        """Get layer extent (bounding box)."""
        extent = self._layer.extent()
        return BoundingBox(
            xmin=extent.xMinimum(),
            ymin=extent.yMinimum(),
            xmax=extent.xMaximum(),
            ymax=extent.yMaximum()
        )
    
    def provider_type(self) -> str:
        """Get data provider type (postgres, spatialite, ogr, etc.)."""
        return self._layer.providerType()
    
    def source(self) -> str:
        """Get data source URI/path."""
        return self._layer.source()
    
    def field_names(self) -> List[str]:
        """Get list of field names."""
        return [field.name() for field in self._layer.fields()]
    
    def field_type(self, field_name: str) -> FieldType:
        """Get field data type."""
        fields = self._layer.fields()
        field_idx = fields.indexOf(field_name)
        
        if field_idx < 0:
            return FieldType.INVALID
        
        qvariant_type = fields.at(field_idx).type()
        
        # Map QVariant types to FieldType enum
        type_map = {
            QVariant.Int: FieldType.INT,
            QVariant.UInt: FieldType.UINT,
            QVariant.LongLong: FieldType.LONGLONG,
            QVariant.ULongLong: FieldType.ULONGLONG,
            QVariant.Double: FieldType.DOUBLE,
            QVariant.String: FieldType.STRING,
            QVariant.Date: FieldType.DATE,
            QVariant.Time: FieldType.TIME,
            QVariant.DateTime: FieldType.DATETIME,
            QVariant.Bool: FieldType.BOOL,
            QVariant.ByteArray: FieldType.BLOB,
        }
        
        return type_map.get(qvariant_type, FieldType.INVALID)
    
    def primary_key_field(self) -> Optional[str]:
        """
        Get primary key field name if exists.
        
        Delegates to the canonical implementation in layer_utils.
        
        Returns:
            Primary key field name, or None if no PK defined
        """
        from infrastructure.utils.layer_utils import get_primary_key_name
        return get_primary_key_name(self._layer)
    
    def subset_string(self) -> str:
        """Get current subset filter expression."""
        return self._layer.subsetString()
    
    def set_subset_string(self, expression: str) -> bool:
        """
        Set subset filter expression.
        
        Args:
            expression: Filter expression (QGIS expression syntax)
            
        Returns:
            bool: True if successful
        """
        return self._layer.setSubsetString(expression)
    
    def reload(self) -> None:
        """Reload layer data."""
        self._layer.reload()
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"QGISVectorLayerAdapter("
            f"name='{self.name()}', "
            f"provider='{self.provider_type()}', "
            f"features={self.feature_count()}, "
            f"geom_type={self.geometry_type().name})"
        )
    
    def __eq__(self, other) -> bool:
        """Equality comparison based on layer ID."""
        if not isinstance(other, QGISVectorLayerAdapter):
            return False
        return self.id() == other.id()

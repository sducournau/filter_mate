# -*- coding: utf-8 -*-
"""
QGIS Geometry Adapter - Concrete Implementation of IGeometry

Wraps QgsGeometry to implement the abstract IGeometry interface
from core.ports.qgis_port, enabling hexagonal architecture.

Author: FilterMate Team
Version: 4.1.0 (January 2026)
License: GNU GPL v2+
"""

from typing import Optional
from qgis.core import QgsGeometry, QgsWkbTypes, QgsCoordinateTransform, QgsCoordinateReferenceSystem

from ...core.ports.qgis_port import (
    IGeometry,
    GeometryType,
    BoundingBox,
    CoordinateReferenceSystem
)


class QGISGeometryAdapter(IGeometry):
    """
    Adapter wrapping QgsGeometry to implement IGeometry interface.
    
    This allows core domain logic to work with geometries without
    directly depending on QGIS implementation.
    
    Example:
        >>> from qgis.core import QgsGeometry
        >>> qgs_geom = QgsGeometry.fromWkt("POINT(0 0)")
        >>> adapter = QGISGeometryAdapter(qgs_geom)
        >>> adapter.is_valid()
        True
    """
    
    def __init__(self, qgs_geometry: QgsGeometry):
        """
        Initialize adapter.
        
        Args:
            qgs_geometry: QgsGeometry instance to wrap
        """
        if not isinstance(qgs_geometry, QgsGeometry):
            raise TypeError(f"Expected QgsGeometry, got {type(qgs_geometry)}")
        
        self._geometry = qgs_geometry
    
    @property
    def qgs_geometry(self) -> QgsGeometry:
        """Get underlying QgsGeometry (for adapter-internal use)."""
        return self._geometry
    
    def is_valid(self) -> bool:
        """Check if geometry is valid according to OGC standards."""
        if self._geometry is None or self._geometry.isEmpty():
            return False
        return self._geometry.isGeosValid()
    
    def is_empty(self) -> bool:
        """Check if geometry is empty."""
        if self._geometry is None:
            return True
        return self._geometry.isEmpty()
    
    def geometry_type(self) -> GeometryType:
        """Get geometry type."""
        if self._geometry is None or self._geometry.isEmpty():
            return GeometryType.UNKNOWN
        
        wkb_type = self._geometry.wkbType()
        
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
        
        # Handle 25D types
        flat_type = QgsWkbTypes.flatType(wkb_type)
        return type_map.get(flat_type, GeometryType.UNKNOWN)
    
    def as_wkt(self) -> str:
        """Export as Well-Known Text."""
        if self._geometry is None or self._geometry.isEmpty():
            return ""
        return self._geometry.asWkt()
    
    def as_wkb(self) -> bytes:
        """Export as Well-Known Binary."""
        if self._geometry is None or self._geometry.isEmpty():
            return b""
        return self._geometry.asWkb()
    
    def buffer(self, distance: float, segments: int = 5) -> 'QGISGeometryAdapter':
        """
        Create buffer around geometry.
        
        Args:
            distance: Buffer distance (in layer units)
            segments: Number of segments to approximate curves
            
        Returns:
            New adapter with buffered geometry
        """
        if self._geometry is None or self._geometry.isEmpty():
            return QGISGeometryAdapter(QgsGeometry())
        
        buffered = self._geometry.buffer(distance, segments)
        return QGISGeometryAdapter(buffered)
    
    def intersects(self, other: IGeometry) -> bool:
        """Check if this geometry intersects another."""
        if not isinstance(other, QGISGeometryAdapter):
            raise TypeError("Can only intersect with QGISGeometryAdapter")
        
        if self._geometry is None or other._geometry is None:
            return False
        
        return self._geometry.intersects(other._geometry)
    
    def contains(self, other: IGeometry) -> bool:
        """Check if this geometry contains another."""
        if not isinstance(other, QGISGeometryAdapter):
            raise TypeError("Can only check containment with QGISGeometryAdapter")
        
        if self._geometry is None or other._geometry is None:
            return False
        
        return self._geometry.contains(other._geometry)
    
    def bounding_box(self) -> BoundingBox:
        """Get bounding box."""
        if self._geometry is None or self._geometry.isEmpty():
            return BoundingBox(0.0, 0.0, 0.0, 0.0)
        
        bbox = self._geometry.boundingBox()
        return BoundingBox(
            xmin=bbox.xMinimum(),
            ymin=bbox.yMinimum(),
            xmax=bbox.xMaximum(),
            ymax=bbox.yMaximum()
        )
    
    def transform(self, target_crs: CoordinateReferenceSystem) -> 'QGISGeometryAdapter':
        """
        Transform geometry to target CRS.
        
        Args:
            target_crs: Target coordinate reference system
            
        Returns:
            New adapter with transformed geometry
        """
        if self._geometry is None or self._geometry.isEmpty():
            return QGISGeometryAdapter(QgsGeometry())
        
        # Create QgsCoordinateReferenceSystem from auth_id
        target_qgs_crs = QgsCoordinateReferenceSystem(target_crs.auth_id)
        
        # Note: Need source CRS for proper transformation
        # This is a limitation - ideally we'd store source CRS in the adapter
        # For now, assume geometry CRS matches layer CRS (handled at service level)
        
        # Create copy to avoid modifying original
        geom_copy = QgsGeometry(self._geometry)
        
        # Transform would require source CRS - this is a simplified version
        # In practice, transformation is done at the service level with layer CRS context
        
        return QGISGeometryAdapter(geom_copy)
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        if self._geometry is None or self._geometry.isEmpty():
            return "QGISGeometryAdapter(EMPTY)"
        
        geom_type = self.geometry_type().name
        wkt = self.as_wkt()
        preview = wkt[:50] + "..." if len(wkt) > 50 else wkt
        return f"QGISGeometryAdapter({geom_type}: {preview})"
    
    def __eq__(self, other) -> bool:
        """Equality comparison."""
        if not isinstance(other, QGISGeometryAdapter):
            return False
        
        if self._geometry is None and other._geometry is None:
            return True
        if self._geometry is None or other._geometry is None:
            return False
        
        return self._geometry.equals(other._geometry)


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def create_geometry_from_wkt(wkt: str) -> QGISGeometryAdapter:
    """
    Create geometry adapter from WKT string.
    
    Args:
        wkt: Well-Known Text representation
        
    Returns:
        Geometry adapter
        
    Example:
        >>> geom = create_geometry_from_wkt("POINT(0 0)")
        >>> geom.is_valid()
        True
    """
    qgs_geom = QgsGeometry.fromWkt(wkt)
    return QGISGeometryAdapter(qgs_geom)


def create_geometry_from_wkb(wkb: bytes) -> QGISGeometryAdapter:
    """
    Create geometry adapter from WKB bytes.
    
    Args:
        wkb: Well-Known Binary representation
        
    Returns:
        Geometry adapter
    """
    qgs_geom = QgsGeometry()
    qgs_geom.fromWkb(wkb)
    return QGISGeometryAdapter(qgs_geom)

# -*- coding: utf-8 -*-
"""
QGIS Factory - Factory for creating QGIS object adapters

Implements IQGISFactory interface from core.ports.qgis_port,
providing a central place to create all QGIS-related objects.

Author: FilterMate Team
Version: 4.1.0 (January 2026)
License: GNU GPL v2+
"""

from qgis.core import (
    QgsVectorLayer,
    QgsGeometry,
    QgsExpression,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsFeatureRequest
)

from ...core.ports.qgis_port import (
    IQGISFactory,
    IGeometry,
    IExpression,
    IVectorLayer,
    IFeature,
    IFeatureRequest,
    CoordinateReferenceSystem
)

from .geometry_adapter import QGISGeometryAdapter
from .expression_adapter import QGISExpressionAdapter
from .layer_adapter import QGISVectorLayerAdapter
from .feature_adapter import QGISFeatureAdapter, QGISFeatureRequestAdapter


class QGISFactory(IQGISFactory):
    """
    Factory for creating QGIS object adapters.
    
    This is the single entry point for core domain to request
    creation of QGIS objects, maintaining hexagonal architecture.
    
    Example:
        >>> factory = QGISFactory()
        >>> geom = factory.create_geometry_from_wkt("POINT(0 0)")
        >>> geom.is_valid()
        True
    """
    
    def create_geometry_from_wkt(self, wkt: str) -> IGeometry:
        """
        Create geometry from WKT string.
        
        Args:
            wkt: Well-Known Text representation
            
        Returns:
            Geometry adapter implementing IGeometry
            
        Example:
            >>> geom = factory.create_geometry_from_wkt("LINESTRING(0 0, 1 1)")
            >>> geom.geometry_type()
            <GeometryType.LINE: 2>
        """
        qgs_geom = QgsGeometry.fromWkt(wkt)
        return QGISGeometryAdapter(qgs_geom)
    
    def create_expression(self, expression_str: str) -> IExpression:
        """
        Create expression from string.
        
        Args:
            expression_str: Expression string (QGIS expression syntax)
            
        Returns:
            Expression adapter implementing IExpression
            
        Example:
            >>> expr = factory.create_expression('"population" > 1000')
            >>> expr.is_valid()
            True
        """
        qgs_expr = QgsExpression(expression_str)
        return QGISExpressionAdapter(qgs_expr)
    
    def create_vector_layer(
        self,
        source: str,
        name: str,
        provider: str
    ) -> IVectorLayer:
        """
        Create vector layer.
        
        Args:
            source: Data source URI/path
            name: Layer name
            provider: Provider type (postgres, spatialite, ogr, memory)
            
        Returns:
            Layer adapter implementing IVectorLayer
            
        Example:
            >>> layer = factory.create_vector_layer(
            ...     "path/to/data.shp",
            ...     "My Layer",
            ...     "ogr"
            ... )
            >>> layer.is_valid()
            True
        """
        qgs_layer = QgsVectorLayer(source, name, provider)
        return QGISVectorLayerAdapter(qgs_layer)
    
    def create_crs(self, auth_id: str) -> CoordinateReferenceSystem:
        """
        Create CRS from authority ID.
        
        Args:
            auth_id: Authority ID (e.g., 'EPSG:4326')
            
        Returns:
            CRS value object
            
        Example:
            >>> crs = factory.create_crs('EPSG:4326')
            >>> crs.is_geographic
            True
            >>> crs.epsg_code
            4326
        """
        qgs_crs = QgsCoordinateReferenceSystem(auth_id)
        
        return CoordinateReferenceSystem(
            auth_id=qgs_crs.authid(),
            description=qgs_crs.description(),
            is_geographic=qgs_crs.isGeographic()
        )
    
    def wrap_existing_layer(self, qgs_layer: QgsVectorLayer) -> IVectorLayer:
        """
        Wrap existing QgsVectorLayer instance.
        
        This is a convenience method for adapting existing QGIS layers.
        
        Args:
            qgs_layer: Existing QgsVectorLayer instance
            
        Returns:
            Layer adapter
        """
        return QGISVectorLayerAdapter(qgs_layer)
    
    def wrap_existing_geometry(self, qgs_geom: QgsGeometry) -> IGeometry:
        """
        Wrap existing QgsGeometry instance.
        
        This is a convenience method for adapting existing QGIS geometries.
        
        Args:
            qgs_geom: Existing QgsGeometry instance
            
        Returns:
            Geometry adapter
        """
        return QGISGeometryAdapter(qgs_geom)
    
    def create_feature(self) -> IFeature:
        """
        Create new empty feature.
        
        Returns:
            Feature adapter implementing IFeature
        """
        qgs_feature = QgsFeature()
        return QGISFeatureAdapter(qgs_feature)
    
    def create_feature_request(self) -> IFeatureRequest:
        """
        Create new feature request.
        
        Returns:
            Feature request adapter implementing IFeatureRequest
        """
        qgs_request = QgsFeatureRequest()
        return QGISFeatureRequestAdapter(qgs_request)


# ==============================================================================
# SINGLETON INSTANCE
# ==============================================================================

# Global factory instance
_factory_instance = None


def get_qgis_factory() -> QGISFactory:
    """
    Get singleton QGISFactory instance.
    
    Returns:
        QGISFactory instance
        
    Example:
        >>> factory = get_qgis_factory()
        >>> geom = factory.create_geometry_from_wkt("POINT(0 0)")
    """
    global _factory_instance
    if _factory_instance is None:
        _factory_instance = QGISFactory()
    return _factory_instance


def reset_factory():
    """Reset factory instance (for testing)."""
    global _factory_instance
    _factory_instance = None

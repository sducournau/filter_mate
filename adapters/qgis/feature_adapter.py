# -*- coding: utf-8 -*-
"""
QGIS Feature Adapter - Hexagonal Architecture

Adapts QgsFeature to IFeature interface for core domain layer.

Author: FilterMate Team
Version: 4.1.0 (January 2026)
License: GNU GPL v2+
"""

from typing import List, Any, Optional

from qgis.core import QgsFeature, QgsFeatureRequest

from ...core.ports.qgis_port import IFeature, IFeatureRequest, IGeometry
from .geometry_adapter import QGISGeometryAdapter


class QGISFeatureAdapter(IFeature):
    """
    Adapter for QgsFeature implementing IFeature interface.
    
    Wraps QgsFeature to provide hexagonal architecture compliance.
    """
    
    def __init__(self, qgs_feature: QgsFeature):
        """
        Initialize feature adapter.
        
        Args:
            qgs_feature: QgsFeature instance to wrap
        """
        self._feature = qgs_feature
    
    def id(self) -> int:
        """Get feature ID."""
        return self._feature.id()
    
    def attributes(self) -> List[Any]:
        """Get all feature attributes as list."""
        return self._feature.attributes()
    
    def attribute(self, field_name: str) -> Any:
        """Get attribute value by field name."""
        return self._feature.attribute(field_name)
    
    def set_attribute(self, field_name: str, value: Any) -> bool:
        """Set attribute value."""
        return self._feature.setAttribute(field_name, value)
    
    def geometry(self) -> Optional[IGeometry]:
        """Get feature geometry."""
        qgs_geom = self._feature.geometry()
        if qgs_geom and not qgs_geom.isNull():
            return QGISGeometryAdapter(qgs_geom)
        return None
    
    def set_geometry(self, geometry: IGeometry) -> None:
        """Set feature geometry."""
        if isinstance(geometry, QGISGeometryAdapter):
            self._feature.setGeometry(geometry._geometry)
    
    def fields(self) -> List[str]:
        """Get field names."""
        return [field.name() for field in self._feature.fields()]
    
    def is_valid(self) -> bool:
        """Check if feature is valid."""
        return self._feature.isValid()
    
    @property
    def qgs_feature(self) -> QgsFeature:
        """Get underlying QgsFeature (for adapter use only)."""
        return self._feature


class QGISFeatureRequestAdapter(IFeatureRequest):
    """
    Adapter for QgsFeatureRequest implementing IFeatureRequest interface.
    
    Wraps QgsFeatureRequest to provide hexagonal architecture compliance.
    """
    
    def __init__(self, qgs_request: Optional[QgsFeatureRequest] = None):
        """
        Initialize feature request adapter.
        
        Args:
            qgs_request: QgsFeatureRequest instance to wrap, or None to create new
        """
        self._request = qgs_request if qgs_request else QgsFeatureRequest()
    
    def set_filter_expression(self, expression: str) -> 'QGISFeatureRequestAdapter':
        """Set filter expression."""
        self._request.setFilterExpression(expression)
        return self
    
    def set_limit(self, limit: int) -> 'QGISFeatureRequestAdapter':
        """Set maximum number of features to return."""
        self._request.setLimit(limit)
        return self
    
    def set_flags(self, flags: int) -> 'QGISFeatureRequestAdapter':
        """Set request flags (e.g., NoGeometry)."""
        self._request.setFlags(flags)
        return self
    
    def filter_expression(self) -> str:
        """Get current filter expression."""
        expr = self._request.filterExpression()
        return expr.expression() if expr else ""
    
    @property
    def qgs_request(self) -> QgsFeatureRequest:
        """Get underlying QgsFeatureRequest (for adapter use only)."""
        return self._request

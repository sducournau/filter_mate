# -*- coding: utf-8 -*-
"""
CRS Utilities Module

EPIC-1 Migration: Created from orphan modules/crs_utils.pyc
Date: January 2026

Provides coordinate reference system utilities for:
- CRS type detection (geographic vs metric)
- CRS transformation
- Optimal metric CRS selection

Usage:
    from ...core.geometry.crs_utils import (        is_geographic_crs,
        is_metric_crs,
        get_optimal_metric_crs
    )
"""

import logging
from typing import Optional, Tuple

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsUnitTypes
)

logger = logging.getLogger('FilterMate.Core.Geometry.CRS')

# Default metric CRS (Web Mercator)
DEFAULT_METRIC_CRS = "EPSG:3857"


def is_geographic_crs(crs: Optional[QgsCoordinateReferenceSystem]) -> bool:
    """
    Check if CRS uses geographic coordinates (degrees).
    
    Args:
        crs: Coordinate reference system to check
        
    Returns:
        bool: True if CRS is geographic (lat/lon)
    """
    if crs is None or not crs.isValid():
        return False
    return crs.isGeographic()


def is_metric_crs(crs: Optional[QgsCoordinateReferenceSystem]) -> bool:
    """
    Check if CRS uses metric units (meters, km).
    
    Args:
        crs: Coordinate reference system to check
        
    Returns:
        bool: True if CRS uses metric units
    """
    if crs is None or not crs.isValid():
        return False
    
    units = crs.mapUnits()
    return units in (
        QgsUnitTypes.DistanceMeters,
        QgsUnitTypes.DistanceKilometers,
        QgsUnitTypes.DistanceCentimeters,
        QgsUnitTypes.DistanceMillimeters
    )


def get_crs_units(crs: Optional[QgsCoordinateReferenceSystem]) -> str:
    """
    Get human-readable unit name for CRS.
    
    Args:
        crs: Coordinate reference system
        
    Returns:
        str: Unit name (e.g., "meters", "degrees")
    """
    if crs is None or not crs.isValid():
        return "unknown"
    
    units = crs.mapUnits()
    unit_names = {
        QgsUnitTypes.DistanceMeters: "meters",
        QgsUnitTypes.DistanceKilometers: "kilometers",
        QgsUnitTypes.DistanceFeet: "feet",
        QgsUnitTypes.DistanceNauticalMiles: "nautical miles",
        QgsUnitTypes.DistanceYards: "yards",
        QgsUnitTypes.DistanceMiles: "miles",
        QgsUnitTypes.DistanceDegrees: "degrees",
        QgsUnitTypes.DistanceCentimeters: "centimeters",
        QgsUnitTypes.DistanceMillimeters: "millimeters",
    }
    return unit_names.get(units, "unknown")


def get_optimal_metric_crs(
    geometry: Optional[QgsGeometry] = None,
    source_crs: Optional[QgsCoordinateReferenceSystem] = None
) -> QgsCoordinateReferenceSystem:
    """
    Get optimal metric CRS for a geometry or location.
    
    Attempts to select an appropriate UTM zone based on geometry centroid.
    Falls back to Web Mercator (EPSG:3857) if UTM cannot be determined.
    
    Args:
        geometry: Optional geometry to determine location
        source_crs: CRS of the geometry (needed for reprojection)
        
    Returns:
        QgsCoordinateReferenceSystem: Metric CRS (UTM zone or Web Mercator)
    """
    # Default fallback
    default_crs = QgsCoordinateReferenceSystem(DEFAULT_METRIC_CRS)
    
    if geometry is None or geometry.isEmpty():
        return default_crs
    
    try:
        # Get centroid in WGS84
        centroid = geometry.centroid().asPoint()
        
        # If source CRS is provided and not WGS84, transform centroid
        if source_crs is not None and source_crs.isValid():
            wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
            if source_crs.authid() != "EPSG:4326":
                transform = QgsCoordinateTransform(source_crs, wgs84, QgsProject.instance())
                centroid = transform.transform(centroid)
        
        lon = centroid.x()
        lat = centroid.y()
        
        # Calculate UTM zone
        utm_zone = int((lon + 180) / 6) + 1
        
        # Determine hemisphere
        if lat >= 0:
            epsg_code = 32600 + utm_zone  # Northern hemisphere
        else:
            epsg_code = 32700 + utm_zone  # Southern hemisphere
        
        utm_crs = QgsCoordinateReferenceSystem(f"EPSG:{epsg_code}")
        if utm_crs.isValid():
            logger.debug(f"Selected UTM zone: EPSG:{epsg_code}")
            return utm_crs
            
    except Exception as e:
        logger.warning(f"Could not determine optimal UTM zone: {e}")
    
    return default_crs


def get_layer_crs_info(layer) -> dict:
    """
    Get CRS information for a layer.
    
    Args:
        layer: QgsVectorLayer or QgsRasterLayer
        
    Returns:
        dict: CRS info with keys: authid, is_geographic, is_metric, units
    """
    try:
        crs = layer.crs()
        return {
            'authid': crs.authid(),
            'is_geographic': is_geographic_crs(crs),
            'is_metric': is_metric_crs(crs),
            'units': get_crs_units(crs),
            'description': crs.description()
        }
    except Exception:
        return {
            'authid': 'unknown',
            'is_geographic': False,
            'is_metric': False,
            'units': 'unknown',
            'description': 'Invalid CRS'
        }


class CRSTransformer:
    """
    Utility class for CRS transformations.
    
    Caches transforms for efficiency when processing many features.
    """
    
    def __init__(
        self,
        source_crs: QgsCoordinateReferenceSystem,
        dest_crs: QgsCoordinateReferenceSystem,
        project: Optional[QgsProject] = None
    ):
        """
        Initialize transformer.
        
        Args:
            source_crs: Source coordinate reference system
            dest_crs: Destination coordinate reference system
            project: QGIS project for transformation context
        """
        self.source_crs = source_crs
        self.dest_crs = dest_crs
        self.project = project or QgsProject.instance()
        
        self._forward_transform = QgsCoordinateTransform(
            source_crs, dest_crs, self.project
        )
        self._reverse_transform = QgsCoordinateTransform(
            dest_crs, source_crs, self.project
        )
    
    def transform(self, geometry: QgsGeometry) -> Optional[QgsGeometry]:
        """
        Transform geometry from source to destination CRS.
        
        Args:
            geometry: Geometry to transform
            
        Returns:
            QgsGeometry or None if transformation fails
        """
        if geometry is None or geometry.isEmpty():
            return None
            
        try:
            result = QgsGeometry(geometry)
            result.transform(self._forward_transform)
            return result
        except Exception as e:
            logger.error(f"CRS transformation failed: {e}")
            return None
    
    def transform_back(self, geometry: QgsGeometry) -> Optional[QgsGeometry]:
        """
        Transform geometry from destination back to source CRS.
        
        Args:
            geometry: Geometry to transform back
            
        Returns:
            QgsGeometry or None if transformation fails
        """
        if geometry is None or geometry.isEmpty():
            return None
            
        try:
            result = QgsGeometry(geometry)
            result.transform(self._reverse_transform)
            return result
        except Exception as e:
            logger.error(f"Reverse CRS transformation failed: {e}")
            return None


def create_metric_buffer(
    geometry: QgsGeometry,
    distance_meters: float,
    source_crs: QgsCoordinateReferenceSystem,
    segments: int = 5
) -> Optional[QgsGeometry]:
    """
    Create buffer with metric distance, auto-handling CRS.
    
    Args:
        geometry: Geometry to buffer
        distance_meters: Buffer distance in meters
        source_crs: CRS of the geometry
        segments: Number of segments for round corners
        
    Returns:
        QgsGeometry buffer in original CRS or None
    """
    if geometry is None or geometry.isEmpty():
        return None
    
    try:
        if is_metric_crs(source_crs):
            # Already metric, buffer directly
            return geometry.buffer(distance_meters, segments)
        
        # Need to transform to metric CRS
        metric_crs = get_optimal_metric_crs(geometry, source_crs)
        transformer = CRSTransformer(source_crs, metric_crs)
        
        # Transform -> buffer -> transform back
        projected = transformer.transform(geometry)
        if projected is None:
            return None
            
        buffered = projected.buffer(distance_meters, segments)
        if buffered is None or buffered.isEmpty():
            return None
            
        return transformer.transform_back(buffered)
        
    except Exception as e:
        logger.error(f"create_metric_buffer failed: {e}")
        return None


__all__ = [
    'DEFAULT_METRIC_CRS',
    'is_geographic_crs',
    'is_metric_crs',
    'get_crs_units',
    'get_optimal_metric_crs',
    'get_layer_crs_info',
    'CRSTransformer',
    'create_metric_buffer',
]

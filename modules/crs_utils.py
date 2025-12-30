# -*- coding: utf-8 -*-
"""
CRS Utilities Module - FilterMate v2.5.7

Provides utilities for handling coordinate reference systems (CRS) in FilterMate.
Ensures compatibility between different CRS and provides automatic conversion
to metric CRS (EPSG:3857) when meter-based calculations are needed.

Key Features:
- Detect if CRS is geographic (lat/lon in degrees)
- Determine optimal metric CRS for layer extent
- Transform geometries between CRS with proper error handling
- Buffer operations with automatic CRS conversion
- Distance calculations in meters regardless of source CRS

Usage:
    from modules.crs_utils import (
        is_geographic_crs,
        get_optimal_metric_crs,
        transform_geometry,
        create_metric_buffer,
        calculate_distance_meters,
        CRSTransformer
    )

Constants:
    DEFAULT_METRIC_CRS = "EPSG:3857"  # Web Mercator - global metric projection
    METRIC_BUFFER_FALLBACK = "EPSG:3857"  # Fallback for buffer operations

Author: FilterMate Team
Date: December 2025
"""

import logging
import math
from typing import Optional, Tuple, Union, List

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsUnitTypes,
    QgsFeature,
    QgsVectorLayer,
    QgsWkbTypes,
    QgsMemoryProviderUtils,
    QgsDistanceArea
)

# Setup logger
logger = logging.getLogger('FilterMate.CRS')

# =============================================================================
# Constants
# =============================================================================

# Default metric CRS for global use (Web Mercator)
# Good for most use cases where approximate metric distances are sufficient
DEFAULT_METRIC_CRS = "EPSG:3857"

# Fallback CRS for metric buffer operations
METRIC_BUFFER_FALLBACK = "EPSG:3857"

# Common geographic CRS that need conversion
GEOGRAPHIC_CRS_LIST = [
    "EPSG:4326",  # WGS84
    "EPSG:4269",  # NAD83
    "EPSG:4267",  # NAD27
    "EPSG:4258",  # ETRS89
]

# Regional metric CRS suggestions (for better accuracy)
REGIONAL_METRIC_CRS = {
    # France
    "FR": "EPSG:2154",  # Lambert 93
    # UK
    "GB": "EPSG:27700",  # British National Grid
    # Germany
    "DE": "EPSG:25832",  # ETRS89 / UTM zone 32N
    # Spain
    "ES": "EPSG:25830",  # ETRS89 / UTM zone 30N
    # USA
    "US": "EPSG:3857",  # Web Mercator (general) - or use UTM zones
    # Global default
    "DEFAULT": "EPSG:3857"
}


# =============================================================================
# CRS Detection Functions
# =============================================================================

def is_geographic_crs(crs: Optional[QgsCoordinateReferenceSystem]) -> bool:
    """
    Check if a CRS is geographic (uses degrees as units).
    
    Geographic CRS have coordinates in latitude/longitude (degrees),
    which are not suitable for metric operations like buffers or distance
    calculations that expect meters.
    
    Args:
        crs: QgsCoordinateReferenceSystem to check
        
    Returns:
        bool: True if CRS is geographic, False otherwise
        
    Example:
        >>> crs = QgsCoordinateReferenceSystem("EPSG:4326")
        >>> is_geographic_crs(crs)
        True
        >>> crs = QgsCoordinateReferenceSystem("EPSG:3857")
        >>> is_geographic_crs(crs)
        False
    """
    if crs is None or not crs.isValid():
        return False
    
    try:
        # Primary check: QGIS built-in method
        if crs.isGeographic():
            return True
        
        # Secondary check: map units
        map_units = crs.mapUnits()
        if map_units == QgsUnitTypes.DistanceUnit.DistanceDegrees:
            return True
        
        # Fallback: check authid against known geographic CRS
        authid = crs.authid()
        if authid in GEOGRAPHIC_CRS_LIST:
            return True
            
        return False
        
    except Exception as e:
        logger.debug(f"is_geographic_crs error: {e}")
        return False


def is_metric_crs(crs: Optional[QgsCoordinateReferenceSystem]) -> bool:
    """
    Check if a CRS uses metric units (meters).
    
    Args:
        crs: QgsCoordinateReferenceSystem to check
        
    Returns:
        bool: True if CRS uses meters, False otherwise
    """
    if crs is None or not crs.isValid():
        return False
    
    try:
        if crs.isGeographic():
            return False
        
        map_units = crs.mapUnits()
        return map_units == QgsUnitTypes.DistanceUnit.DistanceMeters
        
    except Exception as e:
        logger.debug(f"is_metric_crs error: {e}")
        return False


def get_crs_units(crs: Optional[QgsCoordinateReferenceSystem]) -> str:
    """
    Get human-readable unit name for a CRS.
    
    Args:
        crs: QgsCoordinateReferenceSystem
        
    Returns:
        str: Unit name (e.g., "meters", "degrees", "feet", "unknown")
    """
    if crs is None or not crs.isValid():
        return "unknown"
    
    try:
        map_units = crs.mapUnits()
        
        unit_names = {
            QgsUnitTypes.DistanceUnit.DistanceMeters: "meters",
            QgsUnitTypes.DistanceUnit.DistanceKilometers: "kilometers",
            QgsUnitTypes.DistanceUnit.DistanceFeet: "feet",
            QgsUnitTypes.DistanceUnit.DistanceNauticalMiles: "nautical miles",
            QgsUnitTypes.DistanceUnit.DistanceYards: "yards",
            QgsUnitTypes.DistanceUnit.DistanceMiles: "miles",
            QgsUnitTypes.DistanceUnit.DistanceDegrees: "degrees",
            QgsUnitTypes.DistanceUnit.DistanceCentimeters: "centimeters",
            QgsUnitTypes.DistanceUnit.DistanceMillimeters: "millimeters",
        }
        
        return unit_names.get(map_units, "unknown")
        
    except Exception as e:
        logger.debug(f"get_crs_units error: {e}")
        return "unknown"


# =============================================================================
# CRS Selection Functions
# =============================================================================

def get_optimal_metric_crs(
    project: Optional[QgsProject] = None,
    source_crs: Optional[QgsCoordinateReferenceSystem] = None,
    extent: Optional[QgsRectangle] = None,
    prefer_utm: bool = True
) -> str:
    """
    Determine the optimal metric CRS for calculations.
    
    Priority:
    1. Project CRS if it's already metric
    2. UTM zone based on extent center (if prefer_utm=True)
    3. EPSG:3857 (Web Mercator) as default
    
    Args:
        project: QgsProject instance (optional, uses current if None)
        source_crs: Source CRS of the data (for extent transformation)
        extent: Geographic extent to consider (optional)
        prefer_utm: If True, calculate optimal UTM zone (more accurate)
        
    Returns:
        str: authid of optimal metric CRS (e.g., 'EPSG:3857', 'EPSG:32632')
        
    Example:
        >>> crs_authid = get_optimal_metric_crs(
        ...     extent=QgsRectangle(2.0, 48.5, 3.0, 49.0)  # Paris area
        ... )
        >>> print(crs_authid)
        'EPSG:32631'  # UTM zone 31N
    """
    if project is None:
        project = QgsProject.instance()
    
    # Priority 1: Check project CRS
    if project:
        project_crs = project.crs()
        if project_crs and project_crs.isValid() and is_metric_crs(project_crs):
            logger.info(f"Using project CRS for metric calculations: {project_crs.authid()}")
            return project_crs.authid()
    
    # Priority 2: Calculate UTM zone from extent
    if prefer_utm and extent is not None:
        try:
            # If extent is in geographic CRS, use it directly
            # Otherwise, transform it first
            work_extent = extent
            
            if source_crs and source_crs.isValid() and not source_crs.isGeographic():
                # Transform extent to WGS84 for UTM calculation
                wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
                transform = QgsCoordinateTransform(source_crs, wgs84, project)
                work_extent = transform.transformBoundingBox(extent)
            
            # Calculate UTM zone from center
            if work_extent.isFinite() and not work_extent.isEmpty():
                center_lon = work_extent.center().x()
                center_lat = work_extent.center().y()
                
                # Validate coordinates are in valid range
                if -180 <= center_lon <= 180 and -90 <= center_lat <= 90:
                    utm_crs = calculate_utm_zone(center_lon, center_lat)
                    if utm_crs:
                        logger.info(f"Using calculated UTM CRS for metric calculations: {utm_crs}")
                        return utm_crs
                        
        except Exception as e:
            logger.debug(f"Could not calculate optimal UTM CRS: {e}")
    
    # Priority 3: Default to Web Mercator
    logger.info(f"Using default Web Mercator ({DEFAULT_METRIC_CRS}) for metric calculations")
    return DEFAULT_METRIC_CRS


def calculate_utm_zone(longitude: float, latitude: float) -> Optional[str]:
    """
    Calculate the optimal UTM zone for given coordinates.
    
    Args:
        longitude: Longitude in degrees (-180 to 180)
        latitude: Latitude in degrees (-90 to 90)
        
    Returns:
        str or None: EPSG code for UTM zone (e.g., 'EPSG:32631')
    """
    try:
        # Validate input
        if not (-180 <= longitude <= 180) or not (-90 <= latitude <= 90):
            logger.warning(f"Invalid coordinates for UTM calculation: lon={longitude}, lat={latitude}")
            return None
        
        # Special cases for Norway and Svalbard
        if 56 <= latitude < 64 and 3 <= longitude < 12:
            zone = 32  # Norway special zone
        elif 72 <= latitude < 84:
            if 0 <= longitude < 9:
                zone = 31
            elif 9 <= longitude < 21:
                zone = 33
            elif 21 <= longitude < 33:
                zone = 35
            elif 33 <= longitude < 42:
                zone = 37
            else:
                zone = int((longitude + 180) / 6) + 1
        else:
            # Standard UTM zone calculation
            zone = int((longitude + 180) / 6) + 1
        
        # Determine EPSG code based on hemisphere
        if latitude >= 0:
            # Northern hemisphere: EPSG:326XX
            epsg = 32600 + zone
        else:
            # Southern hemisphere: EPSG:327XX
            epsg = 32700 + zone
        
        # Validate the CRS
        utm_crs = QgsCoordinateReferenceSystem(f"EPSG:{epsg}")
        if utm_crs.isValid():
            return f"EPSG:{epsg}"
        else:
            logger.warning(f"Generated UTM CRS EPSG:{epsg} is not valid")
            return None
            
    except Exception as e:
        logger.debug(f"calculate_utm_zone error: {e}")
        return None


# =============================================================================
# CRS Transformer Class
# =============================================================================

class CRSTransformer:
    """
    Utility class for transforming geometries and coordinates between CRS.
    
    Provides a convenient wrapper around QgsCoordinateTransform with
    caching and error handling.
    
    Example:
        >>> transformer = CRSTransformer("EPSG:4326", "EPSG:3857")
        >>> point = QgsPointXY(2.3522, 48.8566)  # Paris
        >>> transformed = transformer.transform_point(point)
        >>> print(transformed)
        QgsPointXY(261990.5, 6250650.9)
    """
    
    def __init__(
        self,
        source_crs: Union[str, QgsCoordinateReferenceSystem],
        target_crs: Union[str, QgsCoordinateReferenceSystem],
        project: Optional[QgsProject] = None
    ):
        """
        Initialize transformer.
        
        Args:
            source_crs: Source CRS (authid string or QgsCoordinateReferenceSystem)
            target_crs: Target CRS (authid string or QgsCoordinateReferenceSystem)
            project: QgsProject for transform context (optional)
        """
        # Convert string to CRS if needed
        if isinstance(source_crs, str):
            self.source_crs = QgsCoordinateReferenceSystem(source_crs)
        else:
            self.source_crs = source_crs
            
        if isinstance(target_crs, str):
            self.target_crs = QgsCoordinateReferenceSystem(target_crs)
        else:
            self.target_crs = target_crs
        
        self.project = project or QgsProject.instance()
        
        # Create transforms
        self._forward_transform = None
        self._reverse_transform = None
        
        if self.source_crs.isValid() and self.target_crs.isValid():
            self._forward_transform = QgsCoordinateTransform(
                self.source_crs, self.target_crs, self.project
            )
            self._reverse_transform = QgsCoordinateTransform(
                self.target_crs, self.source_crs, self.project
            )
    
    @property
    def is_valid(self) -> bool:
        """Check if transformer is valid."""
        return self._forward_transform is not None and self._forward_transform.isValid()
    
    @property
    def is_identity(self) -> bool:
        """Check if transformation is identity (same CRS)."""
        return self.source_crs.authid() == self.target_crs.authid()
    
    def transform_geometry(
        self, 
        geom: QgsGeometry, 
        reverse: bool = False,
        copy: bool = True
    ) -> Optional[QgsGeometry]:
        """
        Transform a geometry between CRS.
        
        Args:
            geom: QgsGeometry to transform
            reverse: If True, transform from target to source
            copy: If True, create a copy (default, safer)
            
        Returns:
            QgsGeometry or None: Transformed geometry
        """
        if geom is None or geom.isNull() or geom.isEmpty():
            return None
        
        if self.is_identity:
            return QgsGeometry(geom) if copy else geom
        
        if not self.is_valid:
            logger.warning("CRSTransformer: Transform is not valid")
            return None
        
        try:
            work_geom = QgsGeometry(geom) if copy else geom
            transform = self._reverse_transform if reverse else self._forward_transform
            
            result = work_geom.transform(transform)
            if result == 0:  # Success
                return work_geom
            else:
                logger.warning(f"CRSTransformer: Geometry transform failed with code {result}")
                return None
                
        except Exception as e:
            logger.error(f"CRSTransformer: transform_geometry error: {e}")
            return None
    
    def transform_point(
        self, 
        point: QgsPointXY, 
        reverse: bool = False
    ) -> Optional[QgsPointXY]:
        """
        Transform a point between CRS.
        
        Args:
            point: QgsPointXY to transform
            reverse: If True, transform from target to source
            
        Returns:
            QgsPointXY or None: Transformed point
        """
        if point is None:
            return None
        
        if self.is_identity:
            return QgsPointXY(point)
        
        if not self.is_valid:
            return None
        
        try:
            transform = self._reverse_transform if reverse else self._forward_transform
            return transform.transform(point)
        except Exception as e:
            logger.error(f"CRSTransformer: transform_point error: {e}")
            return None
    
    def transform_extent(
        self, 
        extent: QgsRectangle, 
        reverse: bool = False
    ) -> Optional[QgsRectangle]:
        """
        Transform a bounding box between CRS.
        
        Args:
            extent: QgsRectangle to transform
            reverse: If True, transform from target to source
            
        Returns:
            QgsRectangle or None: Transformed extent
        """
        if extent is None or extent.isEmpty():
            return None
        
        if self.is_identity:
            return QgsRectangle(extent)
        
        if not self.is_valid:
            return None
        
        try:
            transform = self._reverse_transform if reverse else self._forward_transform
            return transform.transformBoundingBox(extent)
        except Exception as e:
            logger.error(f"CRSTransformer: transform_extent error: {e}")
            return None


# =============================================================================
# Metric Buffer Functions
# =============================================================================

def create_metric_buffer(
    geom: QgsGeometry,
    distance_meters: float,
    source_crs: QgsCoordinateReferenceSystem,
    segments: int = 8,
    project: Optional[QgsProject] = None
) -> Optional[QgsGeometry]:
    """
    Create a buffer with distance in meters, regardless of source CRS.
    
    Automatically converts to a metric CRS if source is geographic,
    applies the buffer, and converts back to the original CRS.
    
    Args:
        geom: QgsGeometry to buffer
        distance_meters: Buffer distance in meters (can be negative for erosion)
        source_crs: CRS of the input geometry
        segments: Number of segments for curved buffers (default 8)
        project: QgsProject for transform context (optional)
        
    Returns:
        QgsGeometry or None: Buffered geometry in source CRS
        
    Example:
        >>> # Buffer a point in WGS84 by 100 meters
        >>> geom = QgsGeometry.fromPointXY(QgsPointXY(2.3522, 48.8566))
        >>> crs = QgsCoordinateReferenceSystem("EPSG:4326")
        >>> buffered = create_metric_buffer(geom, 100, crs)
    """
    if geom is None or geom.isNull() or geom.isEmpty():
        logger.debug("create_metric_buffer: Invalid input geometry")
        return None
    
    if not source_crs or not source_crs.isValid():
        logger.warning("create_metric_buffer: Invalid source CRS")
        return None
    
    project = project or QgsProject.instance()
    
    # Check if we need to convert CRS
    needs_conversion = is_geographic_crs(source_crs)
    
    if needs_conversion:
        # Get optimal metric CRS
        metric_crs_authid = get_optimal_metric_crs(
            project=project,
            source_crs=source_crs,
            extent=geom.boundingBox(),
            prefer_utm=True
        )
        metric_crs = QgsCoordinateReferenceSystem(metric_crs_authid)
        
        logger.debug(
            f"create_metric_buffer: Converting from {source_crs.authid()} "
            f"to {metric_crs_authid} for metric buffer"
        )
        
        # Create transformer
        transformer = CRSTransformer(source_crs, metric_crs, project)
        
        # Transform geometry to metric CRS
        work_geom = transformer.transform_geometry(geom, copy=True)
        if work_geom is None:
            logger.error("create_metric_buffer: Failed to transform geometry to metric CRS")
            return None
    else:
        work_geom = QgsGeometry(geom)
        transformer = None
    
    # Apply buffer in metric CRS
    try:
        buffered = work_geom.buffer(distance_meters, segments)
        
        if buffered is None or buffered.isNull() or buffered.isEmpty():
            if distance_meters < 0:
                logger.debug(
                    f"create_metric_buffer: Negative buffer ({distance_meters}m) "
                    "produced empty geometry (complete erosion)"
                )
            else:
                logger.warning("create_metric_buffer: Buffer produced empty geometry")
            return None
            
    except Exception as e:
        logger.error(f"create_metric_buffer: Buffer operation failed: {e}")
        return None
    
    # Transform back to source CRS if needed
    if needs_conversion and transformer:
        result = transformer.transform_geometry(buffered, reverse=True, copy=False)
        if result is None:
            logger.error("create_metric_buffer: Failed to transform result back to source CRS")
            return None
        return result
    else:
        return buffered


def buffer_layer_metric(
    layer: QgsVectorLayer,
    distance_meters: float,
    segments: int = 8,
    dissolve: bool = True,
    project: Optional[QgsProject] = None
) -> Optional[QgsVectorLayer]:
    """
    Buffer an entire layer with distance in meters.
    
    Creates a memory layer with buffered geometries, automatically
    handling CRS conversion for geographic coordinate systems.
    
    Args:
        layer: Input QgsVectorLayer
        distance_meters: Buffer distance in meters
        segments: Number of segments for curves
        dissolve: If True, dissolve all buffers into one geometry
        project: QgsProject for context
        
    Returns:
        QgsVectorLayer or None: Memory layer with buffered geometries
    """
    if layer is None or not layer.isValid():
        logger.warning("buffer_layer_metric: Invalid input layer")
        return None
    
    if layer.featureCount() == 0:
        logger.warning("buffer_layer_metric: Layer has no features")
        return None
    
    project = project or QgsProject.instance()
    source_crs = layer.sourceCrs()
    
    # Create output memory layer
    output_layer = QgsMemoryProviderUtils.createMemoryLayer(
        f"{layer.name()}_buffer_{distance_meters}m",
        layer.fields() if not dissolve else None,
        QgsWkbTypes.MultiPolygon,
        source_crs
    )
    
    if not output_layer or not output_layer.isValid():
        logger.error("buffer_layer_metric: Failed to create output layer")
        return None
    
    provider = output_layer.dataProvider()
    buffered_features = []
    all_geometries = []
    
    for feature in layer.getFeatures():
        geom = feature.geometry()
        if geom is None or geom.isNull() or geom.isEmpty():
            continue
        
        # Buffer with metric conversion
        buffered_geom = create_metric_buffer(
            geom, distance_meters, source_crs, segments, project
        )
        
        if buffered_geom and not buffered_geom.isEmpty():
            if dissolve:
                all_geometries.append(buffered_geom)
            else:
                new_feature = QgsFeature(layer.fields())
                new_feature.setGeometry(buffered_geom)
                new_feature.setAttributes(feature.attributes())
                buffered_features.append(new_feature)
    
    # Handle dissolve
    if dissolve and all_geometries:
        from .geometry_safety import safe_unary_union
        dissolved = safe_unary_union(all_geometries)
        if dissolved:
            new_feature = QgsFeature()
            new_feature.setGeometry(dissolved)
            buffered_features = [new_feature]
    
    if not buffered_features:
        logger.warning("buffer_layer_metric: No valid buffered geometries produced")
        return None
    
    provider.addFeatures(buffered_features)
    output_layer.updateExtents()
    
    logger.info(
        f"buffer_layer_metric: Created layer with {len(buffered_features)} features, "
        f"buffer={distance_meters}m"
    )
    
    return output_layer


# =============================================================================
# Distance Calculation Functions
# =============================================================================

def calculate_distance_meters(
    point1: QgsPointXY,
    point2: QgsPointXY,
    crs: QgsCoordinateReferenceSystem,
    ellipsoid: str = "WGS84"
) -> Optional[float]:
    """
    Calculate distance between two points in meters.
    
    Uses ellipsoidal calculation for geographic CRS, or direct
    calculation for projected CRS.
    
    Args:
        point1: First point
        point2: Second point
        crs: CRS of the points
        ellipsoid: Ellipsoid for geodetic calculations (default "WGS84")
        
    Returns:
        float or None: Distance in meters
    """
    if point1 is None or point2 is None:
        return None
    
    if not crs or not crs.isValid():
        logger.warning("calculate_distance_meters: Invalid CRS")
        return None
    
    try:
        distance_area = QgsDistanceArea()
        distance_area.setSourceCrs(crs, QgsProject.instance().transformContext())
        distance_area.setEllipsoid(ellipsoid)
        
        # measureLine returns distance in meters when ellipsoid is set
        distance = distance_area.measureLine(point1, point2)
        
        return distance
        
    except Exception as e:
        logger.error(f"calculate_distance_meters error: {e}")
        return None


def convert_meters_to_crs_units(
    meters: float,
    crs: QgsCoordinateReferenceSystem,
    reference_point: Optional[QgsPointXY] = None
) -> float:
    """
    Convert a distance in meters to CRS units.
    
    For geographic CRS, this is an approximation based on latitude.
    For projected CRS with meter units, returns the input value.
    
    Args:
        meters: Distance in meters
        crs: Target CRS
        reference_point: Reference point for latitude-dependent conversion
        
    Returns:
        float: Distance in CRS units
    """
    if not crs or not crs.isValid():
        return meters
    
    try:
        if is_geographic_crs(crs):
            # For geographic CRS, convert meters to degrees
            # This is an approximation - 1 degree ≈ 111km at equator
            # but varies with latitude
            
            if reference_point:
                # Use latitude for more accurate conversion
                lat = abs(reference_point.y())
                # Meters per degree at given latitude
                meters_per_degree_lon = 111320 * math.cos(math.radians(lat))
                meters_per_degree_lat = 111320
                # Use average
                meters_per_degree = (meters_per_degree_lon + meters_per_degree_lat) / 2
            else:
                # Use approximate value (at ~45° latitude)
                meters_per_degree = 78000
            
            return meters / meters_per_degree
            
        elif is_metric_crs(crs):
            return meters
            
        else:
            # Unknown units - try to use QGIS conversion
            map_units = crs.mapUnits()
            # Convert from meters to map units
            from_meters = QgsUnitTypes.fromUnitToUnitFactor(
                QgsUnitTypes.DistanceUnit.DistanceMeters,
                map_units
            )
            return meters * from_meters
            
    except Exception as e:
        logger.warning(f"convert_meters_to_crs_units error: {e}, returning original value")
        return meters


def convert_crs_units_to_meters(
    value: float,
    crs: QgsCoordinateReferenceSystem,
    reference_point: Optional[QgsPointXY] = None
) -> float:
    """
    Convert a distance in CRS units to meters.
    
    Args:
        value: Distance in CRS units
        crs: Source CRS
        reference_point: Reference point for latitude-dependent conversion
        
    Returns:
        float: Distance in meters
    """
    if not crs or not crs.isValid():
        return value
    
    try:
        if is_geographic_crs(crs):
            # Convert degrees to meters
            if reference_point:
                lat = abs(reference_point.y())
                meters_per_degree_lon = 111320 * math.cos(math.radians(lat))
                meters_per_degree_lat = 111320
                meters_per_degree = (meters_per_degree_lon + meters_per_degree_lat) / 2
            else:
                meters_per_degree = 78000
            
            return value * meters_per_degree
            
        elif is_metric_crs(crs):
            return value
            
        else:
            map_units = crs.mapUnits()
            to_meters = QgsUnitTypes.fromUnitToUnitFactor(
                map_units,
                QgsUnitTypes.DistanceUnit.DistanceMeters
            )
            return value * to_meters
            
    except Exception as e:
        logger.warning(f"convert_crs_units_to_meters error: {e}, returning original value")
        return value


# =============================================================================
# Layer CRS Utilities
# =============================================================================

def ensure_metric_crs(
    layer: QgsVectorLayer,
    project: Optional[QgsProject] = None
) -> Tuple[QgsVectorLayer, bool]:
    """
    Ensure a layer is in a metric CRS, reprojecting if necessary.
    
    Args:
        layer: Input layer
        project: QgsProject for context
        
    Returns:
        tuple: (layer, was_reprojected)
            - layer: Original or reprojected layer
            - was_reprojected: True if layer was reprojected
    """
    if layer is None or not layer.isValid():
        return layer, False
    
    source_crs = layer.sourceCrs()
    
    if is_metric_crs(source_crs):
        logger.debug(f"ensure_metric_crs: Layer already in metric CRS {source_crs.authid()}")
        return layer, False
    
    # Need to reproject
    project = project or QgsProject.instance()
    target_crs_authid = get_optimal_metric_crs(
        project=project,
        source_crs=source_crs,
        extent=layer.extent()
    )
    
    logger.info(
        f"ensure_metric_crs: Reprojecting layer from {source_crs.authid()} "
        f"to {target_crs_authid}"
    )
    
    try:
        import processing
        
        result = processing.run('qgis:reprojectlayer', {
            'INPUT': layer,
            'TARGET_CRS': target_crs_authid,
            'OUTPUT': 'memory:'
        })
        
        reprojected = result['OUTPUT']
        if reprojected and reprojected.isValid():
            return reprojected, True
        else:
            logger.warning("ensure_metric_crs: Reprojection failed, returning original")
            return layer, False
            
    except Exception as e:
        logger.error(f"ensure_metric_crs: Reprojection error: {e}")
        return layer, False


def get_layer_crs_info(layer: QgsVectorLayer) -> dict:
    """
    Get detailed CRS information for a layer.
    
    Args:
        layer: QgsVectorLayer
        
    Returns:
        dict: CRS information including:
            - authid: EPSG code
            - description: Human-readable name
            - is_geographic: True if geographic
            - is_metric: True if uses meters
            - units: Unit name
            - proj4: PROJ4 string
    """
    result = {
        "authid": None,
        "description": None,
        "is_geographic": False,
        "is_metric": False,
        "units": "unknown",
        "proj4": None
    }
    
    if layer is None or not layer.isValid():
        return result
    
    crs = layer.sourceCrs()
    if not crs or not crs.isValid():
        return result
    
    try:
        result["authid"] = crs.authid()
        result["description"] = crs.description()
        result["is_geographic"] = is_geographic_crs(crs)
        result["is_metric"] = is_metric_crs(crs)
        result["units"] = get_crs_units(crs)
        result["proj4"] = crs.toProj4()
    except Exception as e:
        logger.debug(f"get_layer_crs_info error: {e}")
    
    return result

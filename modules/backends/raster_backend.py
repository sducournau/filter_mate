# -*- coding: utf-8 -*-
"""
FilterMate - Raster Backend

This module provides raster data access and sampling capabilities
using GDAL for reading raster data and extracting values at vector positions.

Classes:
    RasterBackend: Backend for raster operations via GDAL

Example usage:
    >>> backend = RasterBackend("/path/to/dem.tif")
    >>> elevation = backend.sample_point(point_geometry)
    >>> stats = backend.zonal_stats(polygon_geometry)
"""

import logging
from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path

# GDAL imports (available in QGIS environment)
try:
    from osgeo import gdal, osr
    import numpy as np
    GDAL_AVAILABLE = True
except ImportError:
    GDAL_AVAILABLE = False
    gdal = None
    osr = None
    np = None

# QGIS imports
from qgis.core import (
    QgsGeometry,
    QgsPointXY,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsRectangle,
)


logger = logging.getLogger(__name__)


class RasterBackendError(Exception):
    """Exception raised for raster backend errors."""
    pass


class RasterBackend:
    """
    Backend for raster operations via GDAL.
    
    Provides sampling of raster values at point locations, zonal statistics
    for polygons, and metadata extraction from raster files.
    
    Attributes:
        raster_path: Path to the raster file
        dataset: GDAL dataset object
        crs: Coordinate reference system
        geotransform: GDAL geotransform tuple
        n_bands: Number of raster bands
        width: Raster width in pixels
        height: Raster height in pixels
        
    Example:
        >>> backend = RasterBackend("/path/to/dem.tif")
        >>> value = backend.sample_point(QgsPointXY(500000, 6500000))
        >>> print(f"Elevation: {value}m")
    """
    
    # Sampling methods
    SAMPLE_NEAREST = 'nearest'
    SAMPLE_BILINEAR = 'bilinear'
    SAMPLE_CUBIC = 'cubic'
    
    def __init__(self, raster_path: str):
        """
        Initialize the raster backend.
        
        Args:
            raster_path: Path to the raster file (GeoTIFF, JPEG2000, VRT, etc.)
            
        Raises:
            RasterBackendError: If GDAL is not available or raster cannot be opened
        """
        if not GDAL_AVAILABLE:
            raise RasterBackendError(
                "GDAL is not available. Please ensure osgeo.gdal is installed."
            )
        
        self.raster_path = str(raster_path)
        self.dataset: Optional[gdal.Dataset] = None
        self.crs: Optional[QgsCoordinateReferenceSystem] = None
        self.geotransform: Optional[Tuple] = None
        self.n_bands: int = 0
        self.width: int = 0
        self.height: int = 0
        self.nodata_values: Dict[int, Optional[float]] = {}
        
        self._open_dataset()
    
    def _open_dataset(self) -> None:
        """
        Open the GDAL dataset and extract metadata.
        
        Raises:
            RasterBackendError: If raster file cannot be opened
        """
        if not Path(self.raster_path).exists():
            raise RasterBackendError(f"Raster file not found: {self.raster_path}")
        
        self.dataset = gdal.Open(self.raster_path, gdal.GA_ReadOnly)
        if self.dataset is None:
            raise RasterBackendError(f"Cannot open raster: {self.raster_path}")
        
        # Extract metadata
        self.geotransform = self.dataset.GetGeoTransform()
        self.n_bands = self.dataset.RasterCount
        self.width = self.dataset.RasterXSize
        self.height = self.dataset.RasterYSize
        
        # Get CRS
        wkt = self.dataset.GetProjection()
        if wkt:
            self.crs = QgsCoordinateReferenceSystem(wkt)
        
        # Get nodata values for each band
        for band_idx in range(1, self.n_bands + 1):
            band = self.dataset.GetRasterBand(band_idx)
            self.nodata_values[band_idx] = band.GetNoDataValue()
        
        logger.info(
            f"Opened raster: {self.raster_path} "
            f"({self.width}x{self.height}, {self.n_bands} bands)"
        )
    
    def close(self) -> None:
        """Close the GDAL dataset and release resources."""
        if self.dataset is not None:
            self.dataset = None
            logger.debug(f"Closed raster: {self.raster_path}")
    
    def __del__(self):
        """Destructor to ensure dataset is closed."""
        self.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
    
    def get_metadata(self) -> Dict:
        """
        Get raster metadata.
        
        Returns:
            Dictionary containing:
                - path: Raster file path
                - crs: CRS auth ID (e.g., "EPSG:4326")
                - width: Width in pixels
                - height: Height in pixels
                - n_bands: Number of bands
                - resolution: (x_res, y_res) tuple
                - extent: (xmin, ymin, xmax, ymax) tuple
                - nodata: Dict of nodata values by band
        """
        if self.dataset is None:
            raise RasterBackendError("Dataset not open")
        
        gt = self.geotransform
        x_res = abs(gt[1])
        y_res = abs(gt[5])
        
        xmin = gt[0]
        ymax = gt[3]
        xmax = xmin + self.width * gt[1]
        ymin = ymax + self.height * gt[5]
        
        return {
            'path': self.raster_path,
            'crs': self.crs.authid() if self.crs else None,
            'width': self.width,
            'height': self.height,
            'n_bands': self.n_bands,
            'resolution': (x_res, y_res),
            'extent': (xmin, ymin, xmax, ymax),
            'nodata': self.nodata_values.copy(),
        }
    
    def get_extent(self) -> QgsRectangle:
        """
        Get the raster extent as a QgsRectangle.
        
        Returns:
            QgsRectangle representing the raster extent
        """
        meta = self.get_metadata()
        xmin, ymin, xmax, ymax = meta['extent']
        return QgsRectangle(xmin, ymin, xmax, ymax)
    
    def _world_to_pixel(self, x: float, y: float) -> Tuple[int, int]:
        """
        Convert world coordinates to pixel coordinates.
        
        Args:
            x: X coordinate in world units
            y: Y coordinate in world units
            
        Returns:
            Tuple of (column, row) pixel coordinates
        """
        gt = self.geotransform
        col = int((x - gt[0]) / gt[1])
        row = int((y - gt[3]) / gt[5])
        return col, row
    
    def _pixel_to_world(self, col: int, row: int) -> Tuple[float, float]:
        """
        Convert pixel coordinates to world coordinates (pixel center).
        
        Args:
            col: Column index
            row: Row index
            
        Returns:
            Tuple of (x, y) world coordinates at pixel center
        """
        gt = self.geotransform
        x = gt[0] + (col + 0.5) * gt[1]
        y = gt[3] + (row + 0.5) * gt[5]
        return x, y
    
    def _transform_point(
        self, 
        point: QgsPointXY, 
        source_crs: QgsCoordinateReferenceSystem
    ) -> QgsPointXY:
        """
        Transform a point to the raster's CRS if needed.
        
        Args:
            point: Point to transform
            source_crs: Source CRS of the point
            
        Returns:
            Transformed point in raster CRS
        """
        if self.crs is None or source_crs is None:
            return point
        
        if self.crs == source_crs:
            return point
        
        transform = QgsCoordinateTransform(
            source_crs, 
            self.crs, 
            QgsProject.instance()
        )
        return transform.transform(point)
    
    def sample_point(
        self, 
        geom: Union[QgsGeometry, QgsPointXY], 
        band: int = 1,
        method: str = SAMPLE_NEAREST,
        source_crs: Optional[QgsCoordinateReferenceSystem] = None
    ) -> Optional[float]:
        """
        Sample raster value at a point location.
        
        Args:
            geom: Point geometry or QgsPointXY
            band: Band number (1-based)
            method: Sampling method ('nearest', 'bilinear', 'cubic')
            source_crs: CRS of the input geometry (for reprojection)
            
        Returns:
            Raster value at the point, or None if outside raster or nodata
            
        Raises:
            RasterBackendError: If band is invalid
        """
        if self.dataset is None:
            raise RasterBackendError("Dataset not open")
        
        if band < 1 or band > self.n_bands:
            raise RasterBackendError(
                f"Invalid band {band}, raster has {self.n_bands} bands"
            )
        
        # Get point coordinates
        if isinstance(geom, QgsGeometry):
            point = geom.asPoint()
        else:
            point = geom
        
        # Transform to raster CRS if needed
        if source_crs is not None:
            point = self._transform_point(point, source_crs)
        
        x, y = point.x(), point.y()
        
        # Convert to pixel coordinates
        col, row = self._world_to_pixel(x, y)
        
        # Check bounds
        if col < 0 or col >= self.width or row < 0 or row >= self.height:
            return None
        
        # Read value based on method
        if method == self.SAMPLE_NEAREST:
            return self._sample_nearest(col, row, band)
        elif method == self.SAMPLE_BILINEAR:
            return self._sample_bilinear(x, y, band)
        elif method == self.SAMPLE_CUBIC:
            return self._sample_cubic(x, y, band)
        else:
            raise RasterBackendError(f"Unknown sampling method: {method}")
    
    def _sample_nearest(self, col: int, row: int, band: int) -> Optional[float]:
        """Sample using nearest neighbor."""
        raster_band = self.dataset.GetRasterBand(band)
        data = raster_band.ReadAsArray(col, row, 1, 1)
        
        if data is None:
            return None
        
        value = float(data[0, 0])
        nodata = self.nodata_values.get(band)
        
        if nodata is not None and value == nodata:
            return None
        
        return value
    
    def _sample_bilinear(self, x: float, y: float, band: int) -> Optional[float]:
        """Sample using bilinear interpolation."""
        gt = self.geotransform
        
        # Get fractional pixel coordinates
        col_f = (x - gt[0]) / gt[1] - 0.5
        row_f = (y - gt[3]) / gt[5] - 0.5
        
        col0 = int(np.floor(col_f))
        row0 = int(np.floor(row_f))
        
        # Check bounds for 2x2 window
        if col0 < 0 or col0 >= self.width - 1:
            return self._sample_nearest(max(0, min(col0, self.width - 1)), 
                                        max(0, min(row0, self.height - 1)), band)
        if row0 < 0 or row0 >= self.height - 1:
            return self._sample_nearest(max(0, min(col0, self.width - 1)), 
                                        max(0, min(row0, self.height - 1)), band)
        
        # Read 2x2 window
        raster_band = self.dataset.GetRasterBand(band)
        data = raster_band.ReadAsArray(col0, row0, 2, 2)
        
        if data is None:
            return None
        
        nodata = self.nodata_values.get(band)
        
        # Check for nodata in window
        if nodata is not None:
            if np.any(data == nodata):
                return self._sample_nearest(int(col_f + 0.5), int(row_f + 0.5), band)
        
        # Bilinear interpolation
        dx = col_f - col0
        dy = row_f - row0
        
        value = (
            data[0, 0] * (1 - dx) * (1 - dy) +
            data[0, 1] * dx * (1 - dy) +
            data[1, 0] * (1 - dx) * dy +
            data[1, 1] * dx * dy
        )
        
        return float(value)
    
    def _sample_cubic(self, x: float, y: float, band: int) -> Optional[float]:
        """
        Sample using cubic interpolation.
        
        Falls back to bilinear near edges.
        """
        gt = self.geotransform
        
        # Get fractional pixel coordinates
        col_f = (x - gt[0]) / gt[1] - 0.5
        row_f = (y - gt[3]) / gt[5] - 0.5
        
        col0 = int(np.floor(col_f)) - 1
        row0 = int(np.floor(row_f)) - 1
        
        # Check bounds for 4x4 window
        if col0 < 0 or col0 >= self.width - 3 or row0 < 0 or row0 >= self.height - 3:
            return self._sample_bilinear(x, y, band)
        
        # Read 4x4 window
        raster_band = self.dataset.GetRasterBand(band)
        data = raster_band.ReadAsArray(col0, row0, 4, 4)
        
        if data is None:
            return None
        
        nodata = self.nodata_values.get(band)
        
        # Check for nodata in window
        if nodata is not None:
            if np.any(data == nodata):
                return self._sample_bilinear(x, y, band)
        
        # Cubic interpolation weights
        def cubic_weight(t):
            t = abs(t)
            if t <= 1:
                return 1.5 * t**3 - 2.5 * t**2 + 1
            elif t <= 2:
                return -0.5 * t**3 + 2.5 * t**2 - 4 * t + 2
            return 0
        
        dx = col_f - (col0 + 1)
        dy = row_f - (row0 + 1)
        
        value = 0.0
        for j in range(4):
            for i in range(4):
                weight = cubic_weight(i - 1 - dx) * cubic_weight(j - 1 - dy)
                value += data[j, i] * weight
        
        return float(value)
    
    def sample_points(
        self, 
        layer: QgsVectorLayer, 
        band: int = 1,
        method: str = SAMPLE_NEAREST,
        feature_ids: Optional[List[int]] = None
    ) -> Dict[int, Optional[float]]:
        """
        Sample raster values at multiple point locations (batch optimized).
        
        Args:
            layer: Vector layer with point geometries
            band: Band number (1-based)
            method: Sampling method
            feature_ids: Optional list of feature IDs to sample (all if None)
            
        Returns:
            Dictionary mapping feature ID to raster value
        """
        if self.dataset is None:
            raise RasterBackendError("Dataset not open")
        
        results: Dict[int, Optional[float]] = {}
        layer_crs = layer.crs()
        
        # Get features to process
        if feature_ids is not None:
            features = [layer.getFeature(fid) for fid in feature_ids]
        else:
            features = layer.getFeatures()
        
        for feature in features:
            geom = feature.geometry()
            if geom.isNull() or geom.isEmpty():
                results[feature.id()] = None
                continue
            
            # Get centroid for non-point geometries
            if geom.type() != 0:  # Not a point
                geom = geom.centroid()
            
            value = self.sample_point(geom, band, method, layer_crs)
            results[feature.id()] = value
        
        logger.info(f"Sampled {len(results)} features from band {band}")
        return results
    
    def zonal_stats(
        self, 
        polygon: QgsGeometry, 
        band: int = 1,
        source_crs: Optional[QgsCoordinateReferenceSystem] = None
    ) -> Dict[str, Optional[float]]:
        """
        Calculate zonal statistics for a polygon.
        
        Args:
            polygon: Polygon geometry
            band: Band number (1-based)
            source_crs: CRS of the input geometry (for reprojection)
            
        Returns:
            Dictionary with statistics:
                - min: Minimum value
                - max: Maximum value
                - mean: Mean value
                - std: Standard deviation
                - sum: Sum of values
                - count: Number of valid pixels
        """
        if self.dataset is None:
            raise RasterBackendError("Dataset not open")
        
        if band < 1 or band > self.n_bands:
            raise RasterBackendError(
                f"Invalid band {band}, raster has {self.n_bands} bands"
            )
        
        # Transform polygon to raster CRS if needed
        if source_crs is not None and self.crs is not None and source_crs != self.crs:
            transform = QgsCoordinateTransform(
                source_crs, 
                self.crs, 
                QgsProject.instance()
            )
            polygon = QgsGeometry(polygon)
            polygon.transform(transform)
        
        # Get polygon bounding box
        bbox = polygon.boundingBox()
        
        # Convert to pixel coordinates
        col_min, row_max = self._world_to_pixel(bbox.xMinimum(), bbox.yMinimum())
        col_max, row_min = self._world_to_pixel(bbox.xMaximum(), bbox.yMaximum())
        
        # Clamp to raster bounds
        col_min = max(0, col_min)
        col_max = min(self.width - 1, col_max)
        row_min = max(0, row_min)
        row_max = min(self.height - 1, row_max)
        
        if col_min > col_max or row_min > row_max:
            return {
                'min': None, 'max': None, 'mean': None,
                'std': None, 'sum': None, 'count': 0
            }
        
        # Read raster window
        width = col_max - col_min + 1
        height = row_max - row_min + 1
        
        raster_band = self.dataset.GetRasterBand(band)
        data = raster_band.ReadAsArray(col_min, row_min, width, height)
        
        if data is None:
            return {
                'min': None, 'max': None, 'mean': None,
                'std': None, 'sum': None, 'count': 0
            }
        
        # Create mask for pixels inside polygon
        nodata = self.nodata_values.get(band)
        values = []
        
        for row_offset in range(height):
            for col_offset in range(width):
                # Get pixel center in world coordinates
                px, py = self._pixel_to_world(col_min + col_offset, row_min + row_offset)
                pixel_center = QgsPointXY(px, py)
                
                # Check if pixel center is inside polygon
                if polygon.contains(QgsGeometry.fromPointXY(pixel_center)):
                    value = float(data[row_offset, col_offset])
                    if nodata is None or value != nodata:
                        values.append(value)
        
        if not values:
            return {
                'min': None, 'max': None, 'mean': None,
                'std': None, 'sum': None, 'count': 0
            }
        
        values_array = np.array(values)
        
        return {
            'min': float(np.min(values_array)),
            'max': float(np.max(values_array)),
            'mean': float(np.mean(values_array)),
            'std': float(np.std(values_array)),
            'sum': float(np.sum(values_array)),
            'count': len(values),
        }
    
    def zonal_stats_batch(
        self, 
        layer: QgsVectorLayer, 
        band: int = 1,
        feature_ids: Optional[List[int]] = None
    ) -> Dict[int, Dict[str, Optional[float]]]:
        """
        Calculate zonal statistics for multiple polygons (batch).
        
        Args:
            layer: Vector layer with polygon geometries
            band: Band number (1-based)
            feature_ids: Optional list of feature IDs (all if None)
            
        Returns:
            Dictionary mapping feature ID to statistics dict
        """
        results: Dict[int, Dict[str, Optional[float]]] = {}
        layer_crs = layer.crs()
        
        if feature_ids is not None:
            features = [layer.getFeature(fid) for fid in feature_ids]
        else:
            features = layer.getFeatures()
        
        for feature in features:
            geom = feature.geometry()
            if geom.isNull() or geom.isEmpty():
                results[feature.id()] = {
                    'min': None, 'max': None, 'mean': None,
                    'std': None, 'sum': None, 'count': 0
                }
                continue
            
            stats = self.zonal_stats(geom, band, layer_crs)
            results[feature.id()] = stats
        
        logger.info(f"Computed zonal stats for {len(results)} features")
        return results
    
    @staticmethod
    def from_qgis_layer(raster_layer: QgsRasterLayer) -> 'RasterBackend':
        """
        Create a RasterBackend from a QGIS raster layer.
        
        Args:
            raster_layer: QGIS raster layer
            
        Returns:
            RasterBackend instance
        """
        source = raster_layer.source()
        return RasterBackend(source)
    
    def get_backend_name(self) -> str:
        """Get the backend name for logging."""
        return "RasterBackend"

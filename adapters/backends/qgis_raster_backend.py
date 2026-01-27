#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QGIS Raster Backend
===================

Concrete implementation of RasterPort using QGIS APIs.
Provides raster statistics, histogram, and transparency operations.

EPIC-2: Raster Integration
US-03: QGIS Raster Backend

Architecture:
    RasterPort (abstract interface)
    └── QGISRasterBackend (this implementation)

Usage:
    >>> from adapters.backends.qgis_raster_backend import QGISRasterBackend
    >>> backend = QGISRasterBackend()
    >>> stats = backend.get_statistics(layer.id())
    >>> print(f"Band 1 mean: {stats.band_statistics[0].mean}")
"""

import logging
from typing import Dict, List, Optional, Tuple

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsMapLayer,
    QgsPointXY,
    QgsProject,
    QgsRaster,
    QgsRasterBandStats,
    QgsRasterDataProvider,
    QgsRasterLayer,
    QgsRectangle,
)

from core.ports.raster_port import (
    BandStatistics,
    HistogramBinMethod,
    HistogramData,
    PixelIdentifyResult,
    RasterDataType,
    RasterPort,
    RasterRendererType,
    RasterStats,
    TransparencySettings,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Data Type Mapping
# =============================================================================

def _qgis_to_raster_data_type(qgis_type: Qgis.DataType) -> RasterDataType:
    """
    Convert QGIS data type to RasterDataType enum.
    
    Args:
        qgis_type: QGIS Qgis.DataType value
        
    Returns:
        Corresponding RasterDataType enum value
    """
    mapping = {
        Qgis.DataType.Byte: RasterDataType.BYTE,
        Qgis.DataType.Int16: RasterDataType.INT16,
        Qgis.DataType.UInt16: RasterDataType.UINT16,
        Qgis.DataType.Int32: RasterDataType.INT32,
        Qgis.DataType.UInt32: RasterDataType.UINT32,
        Qgis.DataType.Float32: RasterDataType.FLOAT32,
        Qgis.DataType.Float64: RasterDataType.FLOAT64,
        Qgis.DataType.CInt16: RasterDataType.CINT16,
        Qgis.DataType.CInt32: RasterDataType.CINT32,
        Qgis.DataType.CFloat32: RasterDataType.CFLOAT32,
        Qgis.DataType.CFloat64: RasterDataType.CFLOAT64,
    }
    return mapping.get(qgis_type, RasterDataType.UNKNOWN)


def _detect_renderer_type(layer: QgsRasterLayer) -> RasterRendererType:
    """
    Detect renderer type from QgsRasterLayer.
    
    Args:
        layer: QGIS raster layer
        
    Returns:
        RasterRendererType enum value
    """
    if not layer or not layer.renderer():
        return RasterRendererType.UNKNOWN
    
    renderer_type = layer.renderer().type()
    mapping = {
        'singlebandgray': RasterRendererType.SINGLEBAND_GRAY,
        'singlebandpseudocolor': RasterRendererType.SINGLEBAND_PSEUDOCOLOR,
        'multibandcolor': RasterRendererType.MULTIBAND_COLOR,
        'paletted': RasterRendererType.PALETTED,
        'hillshade': RasterRendererType.HILLSHADE,
        'contour': RasterRendererType.CONTOUR,
    }
    return mapping.get(renderer_type, RasterRendererType.UNKNOWN)


# =============================================================================
# QGIS Raster Backend Implementation
# =============================================================================

class QGISRasterBackend(RasterPort):
    """
    QGIS implementation of RasterPort interface.
    
    Uses QGIS raster APIs to provide:
    - Band statistics (min, max, mean, std_dev)
    - Histogram computation
    - Pixel identification
    - Transparency management
    
    Thread Safety:
        This backend accesses QGIS layers which must be used from
        the main thread. For background processing, use QgsTask.
    
    Example:
        >>> backend = QGISRasterBackend()
        >>> layer = QgsProject.instance().mapLayer("raster_id")
        >>> stats = backend.get_statistics(layer.id())
        >>> print(f"Bands: {stats.band_count}")
    """
    
    def __init__(self):
        """Initialize QGIS Raster Backend."""
        self._stats_cache: Dict[str, RasterStats] = {}
        logger.debug("[QGISRasterBackend] Initialized")
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _get_layer(self, layer_id: str) -> Optional[QgsRasterLayer]:
        """
        Get raster layer by ID from current project.
        
        Args:
            layer_id: QGIS layer ID
            
        Returns:
            QgsRasterLayer or None if not found/invalid
        """
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer and layer.type() == QgsMapLayer.RasterLayer:
            return layer
        return None
    
    def _get_provider(self, layer_id: str) -> Optional[QgsRasterDataProvider]:
        """
        Get raster data provider for layer.
        
        Args:
            layer_id: QGIS layer ID
            
        Returns:
            QgsRasterDataProvider or None
        """
        layer = self._get_layer(layer_id)
        if layer and layer.isValid():
            return layer.dataProvider()
        return None
    
    def _validate_band(self, layer_id: str, band_number: int) -> bool:
        """
        Validate band number is within range.
        
        Args:
            layer_id: QGIS layer ID
            band_number: 1-based band index
            
        Returns:
            True if band is valid
        """
        band_count = self.get_band_count(layer_id)
        return 1 <= band_number <= band_count
    
    # =========================================================================
    # Statistics Methods
    # =========================================================================
    
    def get_statistics(
        self,
        layer_id: str,
        bands: Optional[List[int]] = None,
        sample_size: int = 0,
        force_recalculate: bool = False
    ) -> RasterStats:
        """
        Get statistics for a raster layer.
        
        Args:
            layer_id: Unique layer identifier
            bands: List of band numbers to compute (None = all bands)
            sample_size: Number of pixels to sample (0 = all pixels)
            force_recalculate: Force recalculation even if cached
            
        Returns:
            RasterStats with complete layer statistics
            
        Raises:
            ValueError: If layer_id is invalid
        """
        # Check cache
        cache_key = f"{layer_id}_{bands}_{sample_size}"
        if not force_recalculate and cache_key in self._stats_cache:
            logger.debug(f"[QGISRasterBackend] Cache hit for {layer_id}")
            return self._stats_cache[cache_key]
        
        layer = self._get_layer(layer_id)
        if not layer:
            raise ValueError(f"Invalid raster layer: {layer_id}")
        
        provider = layer.dataProvider()
        if not provider:
            raise ValueError(f"No data provider for layer: {layer_id}")
        
        # Determine bands to process
        band_count = provider.bandCount()
        if bands is None:
            bands = list(range(1, band_count + 1))
        
        # Compute band statistics
        band_stats_list = []
        for band_num in bands:
            if 1 <= band_num <= band_count:
                band_stats = self.get_band_statistics(
                    layer_id, band_num, sample_size
                )
                band_stats_list.append(band_stats)
        
        # Get extent
        extent = layer.extent()
        extent_tuple = (
            extent.xMinimum(),
            extent.yMinimum(),
            extent.xMaximum(),
            extent.yMaximum()
        )
        
        # Build RasterStats
        stats = RasterStats(
            layer_id=layer_id,
            layer_name=layer.name(),
            width=provider.xSize(),
            height=provider.ySize(),
            band_count=band_count,
            crs_auth_id=layer.crs().authid() if layer.crs().isValid() else "",
            pixel_size_x=layer.rasterUnitsPerPixelX(),
            pixel_size_y=layer.rasterUnitsPerPixelY(),
            extent=extent_tuple,
            band_statistics=tuple(band_stats_list),
            renderer_type=_detect_renderer_type(layer),
            file_path=layer.source() if layer.source() else None
        )
        
        # Cache result
        self._stats_cache[cache_key] = stats
        logger.debug(
            f"[QGISRasterBackend] Statistics computed for {layer.name()}: "
            f"{band_count} bands, {stats.width}x{stats.height}"
        )
        
        return stats
    
    def get_band_statistics(
        self,
        layer_id: str,
        band_number: int,
        sample_size: int = 0
    ) -> BandStatistics:
        """
        Get statistics for a single band.
        
        Args:
            layer_id: Unique layer identifier
            band_number: 1-based band index
            sample_size: Number of pixels to sample (0 = all pixels)
            
        Returns:
            BandStatistics for the specified band
            
        Raises:
            ValueError: If layer_id or band_number is invalid
        """
        provider = self._get_provider(layer_id)
        if not provider:
            raise ValueError(f"Invalid raster layer: {layer_id}")
        
        if not self._validate_band(layer_id, band_number):
            raise ValueError(
                f"Invalid band {band_number} for layer {layer_id}"
            )
        
        # Get QGIS band statistics
        stats_flags = QgsRasterBandStats.All
        qgis_stats = provider.bandStatistics(
            band_number,
            stats_flags,
            QgsRectangle(),  # Full extent
            sample_size
        )
        
        # Get no-data value
        no_data = None
        if provider.sourceHasNoDataValue(band_number):
            no_data = provider.sourceNoDataValue(band_number)
        
        # Get data type
        qgis_data_type = provider.dataType(band_number)
        data_type = _qgis_to_raster_data_type(qgis_data_type)
        
        # Calculate pixel counts
        total_pixels = provider.xSize() * provider.ySize()
        # elementCount gives valid pixel count in stats
        valid_pixels = int(qgis_stats.elementCount) if qgis_stats.elementCount else total_pixels
        
        return BandStatistics(
            band_number=band_number,
            min_value=qgis_stats.minimumValue,
            max_value=qgis_stats.maximumValue,
            mean=qgis_stats.mean,
            std_dev=qgis_stats.stdDev,
            no_data_value=no_data,
            valid_pixel_count=valid_pixels,
            total_pixel_count=total_pixels,
            sum=qgis_stats.sum if hasattr(qgis_stats, 'sum') else qgis_stats.mean * valid_pixels,
            data_type=data_type
        )
    
    # =========================================================================
    # Histogram Methods
    # =========================================================================
    
    def get_histogram(
        self,
        layer_id: str,
        band_number: int = 1,
        bin_count: int = 256,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        include_no_data: bool = False,
        method: HistogramBinMethod = HistogramBinMethod.EQUAL_INTERVAL
    ) -> HistogramData:
        """
        Compute histogram for a raster band.
        
        Args:
            layer_id: Unique layer identifier
            band_number: 1-based band index
            bin_count: Number of histogram bins
            min_value: Minimum value for histogram (None = auto)
            max_value: Maximum value for histogram (None = auto)
            include_no_data: Include no-data values in histogram
            method: Binning method to use
            
        Returns:
            HistogramData with computed histogram
        """
        provider = self._get_provider(layer_id)
        if not provider:
            raise ValueError(f"Invalid raster layer: {layer_id}")
        
        if not self._validate_band(layer_id, band_number):
            raise ValueError(
                f"Invalid band {band_number} for layer {layer_id}"
            )
        
        # Get band statistics for auto-range
        if min_value is None or max_value is None:
            band_stats = self.get_band_statistics(layer_id, band_number)
            if min_value is None:
                min_value = band_stats.min_value
            if max_value is None:
                max_value = band_stats.max_value
        
        # Compute histogram using QGIS
        histogram = provider.histogram(
            band_number,
            bin_count,
            min_value,
            max_value,
            QgsRectangle(),  # Full extent
            0,  # Sample size (0 = all)
            include_no_data
        )
        
        # Extract histogram data
        counts = tuple(histogram.histogramVector)
        
        # Calculate bin edges
        bin_width = (max_value - min_value) / bin_count
        bin_edges = tuple(
            min_value + i * bin_width 
            for i in range(bin_count + 1)
        )
        
        return HistogramData(
            band_number=band_number,
            bin_count=bin_count,
            bin_edges=bin_edges,
            counts=counts,
            min_value=min_value,
            max_value=max_value,
            include_no_data=include_no_data,
            method=method
        )
    
    # =========================================================================
    # Pixel Identification Methods
    # =========================================================================
    
    def identify_pixel(
        self,
        layer_id: str,
        x: float,
        y: float,
        crs_auth_id: Optional[str] = None
    ) -> PixelIdentifyResult:
        """
        Identify pixel values at a map location.
        
        Args:
            layer_id: Unique layer identifier
            x: X coordinate in map units
            y: Y coordinate in map units
            crs_auth_id: CRS of input coordinates (None = layer CRS)
            
        Returns:
            PixelIdentifyResult with values at location
        """
        layer = self._get_layer(layer_id)
        if not layer:
            return PixelIdentifyResult(
                x=x, y=y, row=-1, col=-1,
                is_valid=False
            )
        
        provider = layer.dataProvider()
        point = QgsPointXY(x, y)
        
        # Transform coordinates if needed
        if crs_auth_id and crs_auth_id != layer.crs().authid():
            source_crs = QgsCoordinateReferenceSystem(crs_auth_id)
            if source_crs.isValid():
                transform = QgsCoordinateTransform(
                    source_crs,
                    layer.crs(),
                    QgsProject.instance()
                )
                point = transform.transform(point)
        
        # Check if point is within extent
        extent = layer.extent()
        if not extent.contains(point):
            return PixelIdentifyResult(
                x=x, y=y, row=-1, col=-1,
                is_valid=False
            )
        
        # Calculate row/col
        pixel_x = layer.rasterUnitsPerPixelX()
        pixel_y = layer.rasterUnitsPerPixelY()
        col = int((point.x() - extent.xMinimum()) / pixel_x)
        row = int((extent.yMaximum() - point.y()) / pixel_y)
        
        # Clamp to valid range
        col = max(0, min(col, provider.xSize() - 1))
        row = max(0, min(row, provider.ySize() - 1))
        
        # Get pixel values for all bands
        band_values = {}
        is_no_data = False
        
        for band in range(1, provider.bandCount() + 1):
            value = self.get_pixel_value(layer_id, row, col, band)
            band_values[band] = value
            
            # Check if this is no-data
            if provider.sourceHasNoDataValue(band):
                no_data = provider.sourceNoDataValue(band)
                if value is not None and value == no_data:
                    is_no_data = True
        
        return PixelIdentifyResult(
            x=x,
            y=y,
            row=row,
            col=col,
            band_values=band_values,
            is_valid=True,
            is_no_data=is_no_data
        )
    
    def get_pixel_value(
        self,
        layer_id: str,
        row: int,
        col: int,
        band_number: int = 1
    ) -> Optional[float]:
        """
        Get pixel value at specific row/column.
        
        Args:
            layer_id: Unique layer identifier
            row: Pixel row (0-based)
            col: Pixel column (0-based)
            band_number: 1-based band index
            
        Returns:
            Pixel value or None if no-data/out of bounds
        """
        provider = self._get_provider(layer_id)
        if not provider:
            return None
        
        # Check bounds
        if row < 0 or row >= provider.ySize():
            return None
        if col < 0 or col >= provider.xSize():
            return None
        if not self._validate_band(layer_id, band_number):
            return None
        
        # Use identify to get value
        layer = self._get_layer(layer_id)
        extent = layer.extent()
        
        # Convert row/col to coordinates
        pixel_x = layer.rasterUnitsPerPixelX()
        pixel_y = layer.rasterUnitsPerPixelY()
        x = extent.xMinimum() + (col + 0.5) * pixel_x
        y = extent.yMaximum() - (row + 0.5) * pixel_y
        
        point = QgsPointXY(x, y)
        
        # Identify at point
        result = provider.identify(
            point,
            QgsRaster.IdentifyFormatValue
        )
        
        if result.isValid():
            results = result.results()
            if band_number in results:
                value = results[band_number]
                # Check for no-data
                if provider.sourceHasNoDataValue(band_number):
                    no_data = provider.sourceNoDataValue(band_number)
                    if value == no_data:
                        return None
                return float(value) if value is not None else None
        
        return None
    
    # =========================================================================
    # Transparency Methods
    # =========================================================================
    
    def get_transparency_settings(
        self,
        layer_id: str
    ) -> TransparencySettings:
        """
        Get current transparency settings for a layer.
        
        Args:
            layer_id: Unique layer identifier
            
        Returns:
            Current TransparencySettings
        """
        layer = self._get_layer(layer_id)
        if not layer:
            return TransparencySettings()
        
        # Get global opacity
        opacity = layer.opacity()
        
        # Get no-data transparency (from renderer)
        renderer = layer.renderer()
        no_data_transparent = True
        if renderer:
            # Most renderers treat no-data as transparent by default
            no_data_transparent = True
        
        return TransparencySettings(
            global_opacity=opacity,
            no_data_transparent=no_data_transparent
        )
    
    def apply_transparency(
        self,
        layer_id: str,
        settings: TransparencySettings
    ) -> bool:
        """
        Apply transparency settings to a layer.
        
        Args:
            layer_id: Unique layer identifier
            settings: Transparency settings to apply
            
        Returns:
            True if successfully applied
        """
        layer = self._get_layer(layer_id)
        if not layer:
            return False
        
        try:
            # Apply global opacity
            layer.setOpacity(settings.global_opacity)
            
            # Trigger repaint
            layer.triggerRepaint()
            
            logger.debug(
                f"[QGISRasterBackend] Applied transparency to {layer.name()}: "
                f"opacity={settings.global_opacity}"
            )
            return True
            
        except Exception as e:
            logger.error(
                f"[QGISRasterBackend] Failed to apply transparency: {e}"
            )
            return False
    
    def set_opacity(
        self,
        layer_id: str,
        opacity: float
    ) -> bool:
        """
        Set global layer opacity.
        
        Args:
            layer_id: Unique layer identifier
            opacity: Opacity value (0.0-1.0)
            
        Returns:
            True if successfully applied
        """
        # Clamp opacity
        opacity = max(0.0, min(1.0, opacity))
        
        settings = TransparencySettings(global_opacity=opacity)
        return self.apply_transparency(layer_id, settings)
    
    # =========================================================================
    # Metadata Methods
    # =========================================================================
    
    def get_extent(
        self,
        layer_id: str
    ) -> Tuple[float, float, float, float]:
        """
        Get layer extent.
        
        Args:
            layer_id: Unique layer identifier
            
        Returns:
            Extent as (xmin, ymin, xmax, ymax)
        """
        layer = self._get_layer(layer_id)
        if not layer:
            return (0.0, 0.0, 0.0, 0.0)
        
        extent = layer.extent()
        return (
            extent.xMinimum(),
            extent.yMinimum(),
            extent.xMaximum(),
            extent.yMaximum()
        )
    
    def get_crs(
        self,
        layer_id: str
    ) -> str:
        """
        Get layer CRS authority ID.
        
        Args:
            layer_id: Unique layer identifier
            
        Returns:
            CRS authority ID (e.g., "EPSG:4326")
        """
        layer = self._get_layer(layer_id)
        if not layer or not layer.crs().isValid():
            return ""
        return layer.crs().authid()
    
    def get_band_count(
        self,
        layer_id: str
    ) -> int:
        """
        Get number of bands in raster.
        
        Args:
            layer_id: Unique layer identifier
            
        Returns:
            Number of bands
        """
        provider = self._get_provider(layer_id)
        if not provider:
            return 0
        return provider.bandCount()
    
    def get_data_type(
        self,
        layer_id: str,
        band_number: int = 1
    ) -> RasterDataType:
        """
        Get data type for a band.
        
        Args:
            layer_id: Unique layer identifier
            band_number: 1-based band index
            
        Returns:
            RasterDataType for the band
        """
        provider = self._get_provider(layer_id)
        if not provider:
            return RasterDataType.UNKNOWN
        
        if not self._validate_band(layer_id, band_number):
            return RasterDataType.UNKNOWN
        
        qgis_type = provider.dataType(band_number)
        return _qgis_to_raster_data_type(qgis_type)
    
    # =========================================================================
    # Validation Methods
    # =========================================================================
    
    def is_valid(
        self,
        layer_id: str
    ) -> bool:
        """
        Check if layer is valid and accessible.
        
        Args:
            layer_id: Unique layer identifier
            
        Returns:
            True if layer is valid
        """
        layer = self._get_layer(layer_id)
        return layer is not None and layer.isValid()
    
    def supports_statistics(
        self,
        layer_id: str
    ) -> bool:
        """
        Check if layer supports statistics computation.
        
        Args:
            layer_id: Unique layer identifier
            
        Returns:
            True if statistics are supported
        """
        provider = self._get_provider(layer_id)
        if not provider:
            return False
        
        # Check if provider has statistics capability
        capabilities = provider.capabilities()
        # Most raster providers support statistics
        return provider.isValid()
    
    # =========================================================================
    # Cache Management
    # =========================================================================
    
    def clear_cache(self, layer_id: Optional[str] = None) -> None:
        """
        Clear statistics cache.
        
        Args:
            layer_id: Specific layer to clear (None = all)
        """
        if layer_id:
            # Clear specific layer
            keys_to_remove = [
                k for k in self._stats_cache 
                if k.startswith(layer_id)
            ]
            for key in keys_to_remove:
                del self._stats_cache[key]
            logger.debug(
                f"[QGISRasterBackend] Cleared cache for {layer_id}"
            )
        else:
            # Clear all
            self._stats_cache.clear()
            logger.debug("[QGISRasterBackend] Cleared all cache")


# =============================================================================
# Module-level instance (singleton pattern)
# =============================================================================

_default_backend: Optional[QGISRasterBackend] = None


def get_qgis_raster_backend() -> QGISRasterBackend:
    """
    Get the default QGIS raster backend instance.
    
    Returns:
        QGISRasterBackend singleton instance
    """
    global _default_backend
    if _default_backend is None:
        _default_backend = QGISRasterBackend()
    return _default_backend

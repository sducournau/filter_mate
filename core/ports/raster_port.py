"""
Raster Port Interface.

Abstract interface for raster layer operations.
Implements the Port in Hexagonal Architecture pattern.

This is a PURE PYTHON module with NO QGIS dependencies,
enabling true unit testing and clear separation of concerns.

EPIC-2: Raster Integration
US-02: Raster Port Interface
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple


# =============================================================================
# Enumerations
# =============================================================================

class RasterDataType(Enum):
    """
    Raster data types supported by the system.
    
    Maps to common GDAL/QGIS data types without direct dependency.
    """
    UNKNOWN = auto()
    BYTE = auto()           # 8-bit unsigned integer (0-255)
    INT16 = auto()          # 16-bit signed integer
    UINT16 = auto()         # 16-bit unsigned integer
    INT32 = auto()          # 32-bit signed integer
    UINT32 = auto()         # 32-bit unsigned integer
    FLOAT32 = auto()        # 32-bit floating point
    FLOAT64 = auto()        # 64-bit floating point
    CINT16 = auto()         # Complex Int16
    CINT32 = auto()         # Complex Int32
    CFLOAT32 = auto()       # Complex Float32
    CFLOAT64 = auto()       # Complex Float64


class RasterRendererType(Enum):
    """
    Types of raster renderers.
    
    Determines how raster values are displayed.
    """
    UNKNOWN = auto()
    SINGLEBAND_GRAY = auto()      # Single band grayscale
    SINGLEBAND_PSEUDOCOLOR = auto()  # Single band with color ramp
    MULTIBAND_COLOR = auto()      # RGB/RGBA composition
    PALETTED = auto()             # Paletted/unique values
    HILLSHADE = auto()            # Hillshade rendering
    CONTOUR = auto()              # Contour lines


class HistogramBinMethod(Enum):
    """
    Methods for calculating histogram bins.
    """
    EQUAL_INTERVAL = auto()   # Equal-width bins
    QUANTILE = auto()         # Equal-count bins
    NATURAL_BREAKS = auto()   # Jenks natural breaks
    CUSTOM = auto()           # User-defined bins


# =============================================================================
# Data Classes
# =============================================================================

@dataclass(frozen=True)
class BandStatistics:
    """
    Statistics for a single raster band.
    
    Attributes:
        band_number: 1-based band index
        min_value: Minimum pixel value
        max_value: Maximum pixel value
        mean: Mean pixel value
        std_dev: Standard deviation
        no_data_value: No-data/null value (if defined)
        valid_pixel_count: Number of valid (non-null) pixels
        total_pixel_count: Total number of pixels
        sum: Sum of all valid pixel values
        data_type: Data type of the band
    """
    band_number: int
    min_value: float
    max_value: float
    mean: float
    std_dev: float
    no_data_value: Optional[float] = None
    valid_pixel_count: int = 0
    total_pixel_count: int = 0
    sum: float = 0.0
    data_type: RasterDataType = RasterDataType.UNKNOWN

    @property
    def has_no_data(self) -> bool:
        """Check if band has no-data value defined."""
        return self.no_data_value is not None

    @property
    def null_percentage(self) -> float:
        """Calculate percentage of null/no-data pixels."""
        if self.total_pixel_count == 0:
            return 0.0
        null_count = self.total_pixel_count - self.valid_pixel_count
        return (null_count / self.total_pixel_count) * 100.0

    @property
    def value_range(self) -> float:
        """Calculate the range of valid values."""
        return self.max_value - self.min_value


@dataclass(frozen=True)
class RasterStats:
    """
    Complete statistics for a raster layer.
    
    Aggregates statistics for all bands in the raster.
    
    Attributes:
        layer_id: QGIS layer ID or unique identifier
        layer_name: Human-readable layer name
        width: Raster width in pixels
        height: Raster height in pixels
        band_count: Number of bands
        crs_auth_id: CRS authority ID (e.g., "EPSG:4326")
        pixel_size_x: Pixel size in X direction (map units)
        pixel_size_y: Pixel size in Y direction (map units)
        extent: Bounding box as (xmin, ymin, xmax, ymax)
        band_statistics: Statistics for each band
        renderer_type: Current renderer type
        file_path: Path to raster file (if file-based)
    """
    layer_id: str
    layer_name: str
    width: int
    height: int
    band_count: int
    crs_auth_id: str
    pixel_size_x: float
    pixel_size_y: float
    extent: Tuple[float, float, float, float]
    band_statistics: Tuple[BandStatistics, ...] = field(default_factory=tuple)
    renderer_type: RasterRendererType = RasterRendererType.UNKNOWN
    file_path: Optional[str] = None

    @property
    def total_pixels(self) -> int:
        """Total number of pixels in the raster."""
        return self.width * self.height

    @property
    def is_singleband(self) -> bool:
        """Check if raster has only one band."""
        return self.band_count == 1

    @property
    def is_multiband(self) -> bool:
        """Check if raster has multiple bands."""
        return self.band_count > 1

    @property
    def extent_width(self) -> float:
        """Width of extent in map units."""
        return self.extent[2] - self.extent[0]

    @property
    def extent_height(self) -> float:
        """Height of extent in map units."""
        return self.extent[3] - self.extent[1]

    def get_band_stats(self, band_number: int) -> Optional[BandStatistics]:
        """
        Get statistics for a specific band.
        
        Args:
            band_number: 1-based band index
            
        Returns:
            BandStatistics if found, None otherwise
        """
        for stats in self.band_statistics:
            if stats.band_number == band_number:
                return stats
        return None


@dataclass
class HistogramData:
    """
    Histogram data for a raster band.
    
    Attributes:
        band_number: 1-based band index
        bin_count: Number of histogram bins
        bin_edges: Bin edge values (length = bin_count + 1)
        counts: Count of pixels in each bin (length = bin_count)
        min_value: Minimum value in histogram range
        max_value: Maximum value in histogram range
        include_no_data: Whether no-data values were included
        method: Binning method used
    """
    band_number: int
    bin_count: int
    bin_edges: Tuple[float, ...]
    counts: Tuple[int, ...]
    min_value: float
    max_value: float
    include_no_data: bool = False
    method: HistogramBinMethod = HistogramBinMethod.EQUAL_INTERVAL

    @property
    def total_count(self) -> int:
        """Total count of pixels in histogram."""
        return sum(self.counts)

    @property
    def bin_width(self) -> float:
        """Average bin width."""
        if self.bin_count == 0:
            return 0.0
        return (self.max_value - self.min_value) / self.bin_count

    def get_percentile_value(self, percentile: float) -> float:
        """
        Estimate value at given percentile from histogram.
        
        Args:
            percentile: Percentile value (0-100)
            
        Returns:
            Estimated value at percentile
        """
        if not self.counts or not self.bin_edges:
            return 0.0
            
        target_count = self.total_count * (percentile / 100.0)
        cumulative = 0
        
        for i, count in enumerate(self.counts):
            cumulative += count
            if cumulative >= target_count:
                # Linear interpolation within bin
                if count > 0:
                    fraction = (target_count - (cumulative - count)) / count
                else:
                    fraction = 0.5
                return self.bin_edges[i] + fraction * (self.bin_edges[i + 1] - self.bin_edges[i])
        
        return self.max_value


@dataclass
class PixelIdentifyResult:
    """
    Result of identifying pixel values at a location.
    
    Attributes:
        x: X coordinate (map units)
        y: Y coordinate (map units)
        row: Pixel row (0-based)
        col: Pixel column (0-based)
        band_values: Dictionary of band_number -> pixel value
        is_valid: Whether the location is within the raster extent
        is_no_data: Whether the pixel is a no-data value
    """
    x: float
    y: float
    row: int
    col: int
    band_values: Dict[int, Optional[float]] = field(default_factory=dict)
    is_valid: bool = True
    is_no_data: bool = False

    def get_value(self, band_number: int = 1) -> Optional[float]:
        """
        Get pixel value for a specific band.
        
        Args:
            band_number: 1-based band index
            
        Returns:
            Pixel value or None if not available
        """
        return self.band_values.get(band_number)


@dataclass
class TransparencySettings:
    """
    Transparency settings for raster rendering.
    
    Attributes:
        global_opacity: Overall layer opacity (0.0-1.0)
        no_data_transparent: Whether no-data values are transparent
        transparent_pixel_list: List of (r, g, b, tolerance) for RGB transparency
        single_band_transparent_values: List of (value, tolerance) for single band
    """
    global_opacity: float = 1.0
    no_data_transparent: bool = True
    transparent_pixel_list: List[Tuple[int, int, int, int]] = field(default_factory=list)
    single_band_transparent_values: List[Tuple[float, float]] = field(default_factory=list)

    def __post_init__(self):
        """Validate opacity range."""
        if not 0.0 <= self.global_opacity <= 1.0:
            object.__setattr__(self, 'global_opacity', max(0.0, min(1.0, self.global_opacity)))


# =============================================================================
# Port Interface
# =============================================================================

class RasterPort(ABC):
    """
    Abstract interface for raster layer operations.
    
    All concrete raster backends (QGIS, GDAL-direct, etc.)
    must implement this interface. This follows the Hexagonal
    Architecture pattern where the core domain depends on ports
    (interfaces), not concrete implementations.
    
    The interface provides:
    - Statistics retrieval (min, max, mean, std_dev per band)
    - Histogram computation
    - Pixel identification (value at point)
    - Transparency management
    - Basic metadata access
    
    Example:
        >>> class QGISRasterBackend(RasterPort):
        ...     def get_statistics(self, layer_id: str) -> RasterStats:
        ...         # QGIS-specific implementation
        ...         pass
        
        >>> backend = QGISRasterBackend()
        >>> stats = backend.get_statistics("raster_layer_001")
        >>> print(f"Min: {stats.band_statistics[0].min_value}")
    """

    # =========================================================================
    # Statistics Methods
    # =========================================================================

    @abstractmethod
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
            RuntimeError: If statistics computation fails
        """
        pass

    @abstractmethod
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
        pass

    # =========================================================================
    # Histogram Methods
    # =========================================================================

    @abstractmethod
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
            
        Raises:
            ValueError: If parameters are invalid
        """
        pass

    # =========================================================================
    # Pixel Identification Methods
    # =========================================================================

    @abstractmethod
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
            
        Raises:
            ValueError: If layer_id is invalid
        """
        pass

    @abstractmethod
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
        pass

    # =========================================================================
    # Transparency Methods
    # =========================================================================

    @abstractmethod
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
        pass

    @abstractmethod
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
            
        Raises:
            ValueError: If settings are invalid
        """
        pass

    @abstractmethod
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
        pass

    # =========================================================================
    # Metadata Methods
    # =========================================================================

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    # =========================================================================
    # Validation Methods
    # =========================================================================

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

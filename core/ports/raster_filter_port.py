# -*- coding: utf-8 -*-
"""
Raster Filter Port Interface.

EPIC-3: Raster-Vector Integration
US-R2V-01: Raster as Filter Source

This interface defines the API for raster-based filtering operations:
- Sample raster values at vector feature locations
- Filter vector features by underlying raster values
- Generate value-based masks for raster visualization
- Compute zonal statistics for vector/raster intersection

This is a PURE PYTHON module with NO QGIS dependencies,
enabling true unit testing and clear separation of concerns.

Author: FilterMate Team
Date: January 2026
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any


# =============================================================================
# Enumerations
# =============================================================================

class RasterValuePredicate(Enum):
    """
    Predicates for filtering by raster values.
    
    EPIC-3: Defines how raster values are compared to filter criteria.
    """
    WITHIN_RANGE = auto()      # min <= value <= max
    OUTSIDE_RANGE = auto()     # value < min OR value > max
    ABOVE_VALUE = auto()       # value > threshold
    BELOW_VALUE = auto()       # value < threshold
    EQUALS_VALUE = auto()      # value == specific value
    IS_NODATA = auto()         # value is NoData
    IS_NOT_NODATA = auto()     # value is not NoData


class SamplingMethod(Enum):
    """
    Methods for sampling raster values at vector features.
    
    EPIC-3: Defines how vector features interact with raster pixels.
    """
    CENTROID = auto()          # Sample at feature centroid
    ALL_VERTICES = auto()      # Sample at all vertices (polygon/line)
    INTERSECTING_CELLS = auto() # All cells intersecting the geometry
    WEIGHTED_AVERAGE = auto()  # Area-weighted average of cells
    MAJORITY = auto()          # Most common value (categorical)


class RasterOperation(Enum):
    """
    Operations for raster-vector interactions.
    
    EPIC-3: Defines operations when a vector acts on rasters.
    """
    CLIP = auto()              # Clip raster to vector extent
    MASK_OUTSIDE = auto()      # Mask pixels outside vector
    MASK_INSIDE = auto()       # Mask pixels inside vector
    ZONAL_STATS = auto()       # Calculate zonal statistics


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class RasterSampleResult:
    """
    Result of sampling raster values at a single location.
    
    Attributes:
        feature_id: ID of the vector feature
        point_x: X coordinate of sample point
        point_y: Y coordinate of sample point
        band_values: Dict mapping band number to sampled value
        is_nodata: True if all bands returned NoData
        error: Error message if sampling failed
    """
    feature_id: int
    point_x: float
    point_y: float
    band_values: Dict[int, Optional[float]] = field(default_factory=dict)
    is_nodata: bool = False
    error: Optional[str] = None


@dataclass
class RasterFilterResult:
    """
    Result of filtering vector features by raster values.
    
    EPIC-3: Captures the outcome of a raster-based filter operation.
    
    Attributes:
        matching_feature_ids: IDs of features that match the filter
        total_features: Total number of features evaluated
        matching_count: Number of features matching the filter
        filter_expression: Generated filter expression (if applicable)
        predicate: The predicate used for filtering
        value_range: (min, max) range used for filtering
        band: Band number used for filtering
        sampling_method: Method used to sample values
        statistics: Summary statistics of the operation
        error: Error message if operation failed
    """
    matching_feature_ids: List[int] = field(default_factory=list)
    total_features: int = 0
    matching_count: int = 0
    filter_expression: str = ""
    predicate: RasterValuePredicate = RasterValuePredicate.WITHIN_RANGE
    value_range: Tuple[float, float] = (0.0, 0.0)
    band: int = 1
    sampling_method: SamplingMethod = SamplingMethod.CENTROID
    statistics: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    
    @property
    def match_percentage(self) -> float:
        """Calculate percentage of matching features."""
        if self.total_features == 0:
            return 0.0
        return (self.matching_count / self.total_features) * 100.0
    
    @property
    def is_success(self) -> bool:
        """Check if operation succeeded."""
        return self.error is None


@dataclass
class ZonalStatisticsResult:
    """
    Result of zonal statistics computation.
    
    EPIC-3: Statistics for raster values within vector zones.
    
    Attributes:
        feature_id: ID of the vector zone
        zone_name: Name or label of the zone
        pixel_count: Number of pixels in zone
        valid_pixel_count: Number of non-NoData pixels
        min_value: Minimum raster value in zone
        max_value: Maximum raster value in zone
        mean_value: Mean raster value in zone
        std_dev: Standard deviation
        sum_value: Sum of values
        majority_value: Most common value (for categorical)
        minority_value: Least common value
        coverage_percent: Percentage of zone covered by valid pixels
    """
    feature_id: int
    zone_name: str = ""
    pixel_count: int = 0
    valid_pixel_count: int = 0
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean_value: Optional[float] = None
    std_dev: Optional[float] = None
    sum_value: Optional[float] = None
    majority_value: Optional[float] = None
    minority_value: Optional[float] = None
    coverage_percent: float = 0.0


@dataclass
class RasterMaskResult:
    """
    Result of creating a raster mask.
    
    EPIC-3: Describes a generated value-based mask.
    
    Attributes:
        layer_id: ID of the created mask layer
        layer_name: Name of the mask layer
        source_layer_id: ID of the source raster
        band: Band used for masking
        value_range: (min, max) range for mask
        masked_pixel_count: Number of pixels masked
        total_pixel_count: Total pixels in raster
        is_memory_layer: True if mask is in-memory only
        file_path: Path to saved mask file (if saved)
    """
    layer_id: str = ""
    layer_name: str = ""
    source_layer_id: str = ""
    band: int = 1
    value_range: Tuple[float, float] = (0.0, 0.0)
    masked_pixel_count: int = 0
    total_pixel_count: int = 0
    is_memory_layer: bool = True
    file_path: Optional[str] = None
    
    @property
    def mask_percentage(self) -> float:
        """Calculate percentage of pixels masked."""
        if self.total_pixel_count == 0:
            return 0.0
        return (self.masked_pixel_count / self.total_pixel_count) * 100.0


# =============================================================================
# Port Interface
# =============================================================================

class RasterFilterPort(ABC):
    """
    Abstract interface for raster-based filtering operations.
    
    EPIC-3: Raster-Vector Integration
    
    This port defines operations for:
    1. Sampling raster values at vector feature locations
    2. Filtering vector features by raster value criteria
    3. Generating value-based masks for raster visualization
    4. Computing zonal statistics for vector/raster intersection
    
    Implementations:
    - QGISRasterFilterBackend (QGIS native operations)
    - GDALRasterFilterBackend (GDAL operations) [future]
    """
    
    @abstractmethod
    def sample_at_points(
        self,
        raster_layer_id: str,
        points: List[Tuple[float, float, int]],  # (x, y, feature_id)
        band: int = 1
    ) -> List[RasterSampleResult]:
        """
        Sample raster values at specified points.
        
        Args:
            raster_layer_id: ID of the raster layer to sample
            points: List of (x, y, feature_id) tuples
            band: Band number to sample (1-indexed)
        
        Returns:
            List of RasterSampleResult for each point
        """
        pass
    
    @abstractmethod
    def sample_at_features(
        self,
        raster_layer_id: str,
        vector_layer_id: str,
        band: int = 1,
        method: SamplingMethod = SamplingMethod.CENTROID,
        feature_ids: Optional[List[int]] = None
    ) -> List[RasterSampleResult]:
        """
        Sample raster values at vector feature locations.
        
        Args:
            raster_layer_id: ID of the raster layer
            vector_layer_id: ID of the vector layer
            band: Band number to sample (1-indexed)
            method: Sampling method to use
            feature_ids: Optional list of specific feature IDs (None = all)
        
        Returns:
            List of RasterSampleResult for each feature
        """
        pass
    
    @abstractmethod
    def filter_features_by_value(
        self,
        raster_layer_id: str,
        vector_layer_id: str,
        band: int,
        predicate: RasterValuePredicate,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        method: SamplingMethod = SamplingMethod.CENTROID,
        feature_ids: Optional[List[int]] = None
    ) -> RasterFilterResult:
        """
        Filter vector features by underlying raster values.
        
        Args:
            raster_layer_id: ID of the raster layer
            vector_layer_id: ID of the vector layer
            band: Band number to evaluate
            predicate: Value comparison predicate
            min_value: Minimum value for range predicates
            max_value: Maximum value for range predicates
            method: Sampling method to use
            feature_ids: Optional list of specific feature IDs
        
        Returns:
            RasterFilterResult with matching feature IDs
        """
        pass
    
    @abstractmethod
    def generate_value_mask(
        self,
        raster_layer_id: str,
        band: int,
        min_value: float,
        max_value: float,
        output_name: Optional[str] = None,
        invert: bool = False
    ) -> RasterMaskResult:
        """
        Generate a binary mask based on value range.
        
        Args:
            raster_layer_id: ID of the source raster
            band: Band number for masking
            min_value: Minimum value to include
            max_value: Maximum value to include
            output_name: Optional name for output layer
            invert: If True, mask values WITHIN range instead of outside
        
        Returns:
            RasterMaskResult describing the created mask
        """
        pass
    
    @abstractmethod
    def compute_zonal_statistics(
        self,
        raster_layer_id: str,
        vector_layer_id: str,
        band: int = 1,
        statistics: Optional[List[str]] = None,
        feature_ids: Optional[List[int]] = None,
        prefix: str = ""
    ) -> List[ZonalStatisticsResult]:
        """
        Compute zonal statistics for raster values within vector zones.
        
        Args:
            raster_layer_id: ID of the raster layer
            vector_layer_id: ID of the vector (zone) layer
            band: Band number to analyze
            statistics: List of statistics to compute 
                       ['min', 'max', 'mean', 'std', 'sum', 'count', 'majority']
            feature_ids: Optional list of specific zone feature IDs
            prefix: Prefix for output field names
        
        Returns:
            List of ZonalStatisticsResult for each zone
        """
        pass
    
    @abstractmethod
    def clip_raster_by_vector(
        self,
        raster_layer_id: str,
        vector_layer_id: str,
        feature_ids: Optional[List[int]] = None,
        output_name: Optional[str] = None
    ) -> RasterMaskResult:
        """
        Clip raster to vector geometry extent.
        
        Args:
            raster_layer_id: ID of the raster to clip
            vector_layer_id: ID of the clipping vector
            feature_ids: Optional specific features to use as clip extent
            output_name: Optional name for output layer
        
        Returns:
            RasterMaskResult describing the clipped raster
        """
        pass
    
    @abstractmethod
    def mask_raster_by_vector(
        self,
        raster_layer_id: str,
        vector_layer_id: str,
        operation: RasterOperation,
        feature_ids: Optional[List[int]] = None,
        output_name: Optional[str] = None
    ) -> RasterMaskResult:
        """
        Mask raster pixels by vector geometry.
        
        Args:
            raster_layer_id: ID of the raster to mask
            vector_layer_id: ID of the masking vector
            operation: MASK_OUTSIDE or MASK_INSIDE
            feature_ids: Optional specific features to use as mask
            output_name: Optional name for output layer
        
        Returns:
            RasterMaskResult describing the masked raster
        """
        pass

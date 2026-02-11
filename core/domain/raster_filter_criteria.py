"""
Raster Filter Criteria - Domain Objects for Raster Sampling and Filtering.

Pure Python value objects for raster value sampling operations.
These define the contract between UI, services, and infrastructure layers.

This is a PURE PYTHON module with NO QGIS dependencies,
enabling true unit testing and clear separation of concerns.

Phase 1: Value Sampling criteria and results.
Future phases: Zonal Stats criteria, Histogram ranges, Band compositions.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple


class SamplingMethod(Enum):
    """Method for extracting raster values at vector feature locations.

    CENTROID: Fastest but inaccurate for concave polygons (point may fall outside).
    POINT_ON_SURFACE: Guaranteed inside polygon. Preferred default.
    MEAN_UNDER_POLYGON: Average of all raster cells under the polygon. Slowest but most accurate.
    """
    CENTROID = "centroid"
    POINT_ON_SURFACE = "point_on_surface"
    MEAN_UNDER_POLYGON = "mean_under_polygon"


class ComparisonOperator(Enum):
    """Comparison operators for filtering sampled raster values.

    Standard numeric comparisons plus BETWEEN for range filtering.
    """
    EQUAL = "="
    NOT_EQUAL = "!="
    GREATER_THAN = ">"
    GREATER_EQUAL = ">="
    LESS_THAN = "<"
    LESS_EQUAL = "<="
    BETWEEN = "BETWEEN"

    @property
    def symbol(self) -> str:
        """Return the operator symbol for display."""
        return self.value

    def evaluate(self, value: float, threshold: float, threshold_max: Optional[float] = None) -> bool:
        """Evaluate the comparison against a value.

        Args:
            value: The sampled raster value to test.
            threshold: The primary threshold value.
            threshold_max: Upper bound for BETWEEN operator.

        Returns:
            True if the comparison holds, False otherwise.

        Raises:
            ValueError: If BETWEEN is used without threshold_max.
        """
        if self == ComparisonOperator.EQUAL:
            return value == threshold
        elif self == ComparisonOperator.NOT_EQUAL:
            return value != threshold
        elif self == ComparisonOperator.GREATER_THAN:
            return value > threshold
        elif self == ComparisonOperator.GREATER_EQUAL:
            return value >= threshold
        elif self == ComparisonOperator.LESS_THAN:
            return value < threshold
        elif self == ComparisonOperator.LESS_EQUAL:
            return value <= threshold
        elif self == ComparisonOperator.BETWEEN:
            if threshold_max is None:
                raise ValueError("BETWEEN operator requires threshold_max")
            return threshold <= value <= threshold_max
        return False


@dataclass(frozen=True)
class RasterSamplingCriteria:
    """Immutable criteria for a raster value sampling operation.

    Defines what to sample, how, and how to filter the results.
    Frozen dataclass ensures thread safety when passed to tasks.

    Attributes:
        raster_uri: URI/path of the raster layer to sample from.
        vector_uri: URI/path of the vector layer providing feature geometries.
        band: 1-based band number to sample.
        method: Sampling method (how to extract point from geometry).
        operator: Comparison operator for filtering.
        threshold: Primary threshold value.
        threshold_max: Upper bound for BETWEEN operator (None otherwise).
    """
    raster_uri: str
    vector_uri: str
    band: int = 1
    method: SamplingMethod = SamplingMethod.POINT_ON_SURFACE
    operator: ComparisonOperator = ComparisonOperator.GREATER_EQUAL
    threshold: float = 0.0
    threshold_max: Optional[float] = None

    def __post_init__(self):
        """Validate criteria after initialization."""
        if self.band < 1:
            raise ValueError(f"Band number must be >= 1, got {self.band}")
        if self.operator == ComparisonOperator.BETWEEN and self.threshold_max is None:
            raise ValueError("BETWEEN operator requires threshold_max")
        if (self.threshold_max is not None
                and self.operator == ComparisonOperator.BETWEEN
                and self.threshold_max < self.threshold):
            raise ValueError(
                f"threshold_max ({self.threshold_max}) must be >= threshold ({self.threshold})"
            )


@dataclass
class RasterSamplingResult:
    """Result of a raster value sampling operation.

    Contains the per-feature sampled values and aggregated statistics.
    Not frozen because it is built incrementally during task execution.

    Attributes:
        feature_values: Mapping of feature ID to sampled raster value.
            None value means the sample point fell on NoData or outside raster extent.
        matching_ids: Set of feature IDs that pass the filter criteria.
        total_features: Total number of features processed.
        sampled_count: Number of features with valid (non-None) raster values.
        nodata_count: Number of features that fell on NoData.
        error_message: Error description if operation failed, None on success.
        stats: Summary statistics of sampled values.
    """
    feature_values: Dict[int, Optional[float]] = field(default_factory=dict)
    matching_ids: list = field(default_factory=list)
    total_features: int = 0
    sampled_count: int = 0
    nodata_count: int = 0
    error_message: Optional[str] = None
    stats: Optional['SamplingStats'] = None

    @property
    def matching_count(self) -> int:
        """Number of features passing the filter criteria."""
        return len(self.matching_ids)

    @property
    def is_success(self) -> bool:
        """Whether the sampling operation completed without error."""
        return self.error_message is None

    def summary(self) -> str:
        """Human-readable summary of the sampling result.

        Returns:
            Formatted string like '342/1204 features retained'.
        """
        if not self.is_success:
            return f"Error: {self.error_message}"
        return (
            f"{self.matching_count}/{self.total_features} features retained "
            f"({self.sampled_count} sampled, {self.nodata_count} NoData)"
        )


@dataclass(frozen=True)
class SamplingStats:
    """Summary statistics for sampled raster values.

    Computed from the valid (non-None) values in RasterSamplingResult.

    Attributes:
        min_value: Minimum sampled value.
        max_value: Maximum sampled value.
        mean_value: Mean of sampled values.
        std_value: Standard deviation of sampled values.
        median_value: Median of sampled values.
    """
    min_value: float = 0.0
    max_value: float = 0.0
    mean_value: float = 0.0
    std_value: float = 0.0
    median_value: float = 0.0

    @classmethod
    def from_values(cls, values: list) -> Optional['SamplingStats']:
        """Compute stats from a list of float values.

        Args:
            values: List of sampled raster values (no None entries).

        Returns:
            SamplingStats instance, or None if values is empty.
        """
        if not values:
            return None
        n = len(values)
        sorted_vals = sorted(values)
        min_val = sorted_vals[0]
        max_val = sorted_vals[-1]
        mean_val = sum(sorted_vals) / n

        # Standard deviation (population)
        variance = sum((v - mean_val) ** 2 for v in sorted_vals) / n
        std_val = variance ** 0.5

        # Median
        if n % 2 == 0:
            median_val = (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
        else:
            median_val = sorted_vals[n // 2]

        return cls(
            min_value=min_val,
            max_value=max_val,
            mean_value=mean_val,
            std_value=std_val,
            median_value=median_val,
        )

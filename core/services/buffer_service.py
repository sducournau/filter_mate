# -*- coding: utf-8 -*-
"""
Buffer Service for FilterMate - Hexagonal Architecture.

Extracted from filter_task.py as part of MIG-200 refactoring.
Provides pure Python buffer calculation logic and geometry simplification.

This service handles:
- Buffer tolerance calculation
- Geometry simplification strategies
- Buffer parameter validation
- Buffer distance evaluation

The actual QGIS buffer operations are delegated to adapters/qgis/buffer_adapter.py
to maintain hexagonal architecture separation.

Author: FilterMate Team
Date: January 2026
"""

import logging
import math
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, Tuple, List, Dict, Any

logger = logging.getLogger('FilterMate.Services.Buffer')


class BufferEndCapStyle(IntEnum):
    """Buffer end cap styles."""
    ROUND = 0
    FLAT = 1
    SQUARE = 2


class BufferJoinStyle(IntEnum):
    """Buffer join styles."""
    ROUND = 0
    MITRE = 1
    BEVEL = 2


@dataclass
class BufferConfig:
    """
    Configuration for buffer operations.
    
    Attributes:
        distance: Buffer distance in layer units
        segments: Number of segments for quarter circle (quad_segs)
        end_cap_style: End cap style for buffer
        join_style: Join style for buffer
        mitre_limit: Mitre limit for MITRE join style
        dissolve: Whether to dissolve overlapping buffers
        is_expression: Whether distance is from expression (dynamic per feature)
    """
    distance: float
    segments: int = 5
    end_cap_style: BufferEndCapStyle = BufferEndCapStyle.ROUND
    join_style: BufferJoinStyle = BufferJoinStyle.ROUND
    mitre_limit: float = 2.0
    dissolve: bool = True
    is_expression: bool = False
    expression: Optional[str] = None
    
    @property
    def is_negative(self) -> bool:
        """Check if buffer is negative (erosion)."""
        return self.distance < 0
    
    @property
    def absolute_distance(self) -> float:
        """Get absolute buffer distance."""
        return abs(self.distance)


@dataclass
class SimplificationConfig:
    """
    Configuration for geometry simplification.
    
    Attributes:
        enabled: Whether simplification is enabled
        max_wkt_length: Maximum WKT string length in characters
        min_tolerance_meters: Minimum simplification tolerance in meters
        max_tolerance_meters: Maximum simplification tolerance in meters
        show_warnings: Whether to log simplification warnings
    """
    enabled: bool = True
    max_wkt_length: int = 100000  # 100KB default
    min_tolerance_meters: float = 0.1
    max_tolerance_meters: float = 10.0
    show_warnings: bool = True


@dataclass
class SimplificationResult:
    """
    Result of geometry simplification.
    
    Attributes:
        original_wkt_length: Original WKT length in characters
        simplified_wkt_length: Simplified WKT length in characters
        tolerance_used: Tolerance value used for simplification
        iterations: Number of simplification iterations
        success: Whether simplification achieved target size
        reduction_percentage: Percentage of size reduction
    """
    original_wkt_length: int
    simplified_wkt_length: int
    tolerance_used: float
    iterations: int
    success: bool
    
    @property
    def reduction_percentage(self) -> float:
        """Calculate reduction percentage."""
        if self.original_wkt_length == 0:
            return 0.0
        return ((self.original_wkt_length - self.simplified_wkt_length) 
                / self.original_wkt_length * 100)


class BufferService:
    """
    Service for buffer calculations and geometry simplification.
    
    This is a PURE PYTHON service with NO QGIS dependencies,
    enabling true unit testing and clear separation of concerns.
    
    The actual geometry operations (buffer, simplify) are delegated
    to QGIS adapters.
    
    Example:
        service = BufferService()
        
        # Calculate buffer tolerance
        config = BufferConfig(distance=100, segments=8)
        tolerance = service.calculate_buffer_aware_tolerance(
            config, extent_size=1000
        )
        
        # Estimate simplification parameters
        target_reduction = 0.5
        tolerance = service.estimate_simplification_tolerance(
            extent_size=1000,
            target_reduction=target_reduction
        )
    """
    
    # Default configuration
    DEFAULT_SEGMENTS = 5
    DEFAULT_MAX_WKT_LENGTH = 100000  # 100KB
    
    # WKT precision by CRS type
    WKT_PRECISION_GEOGRAPHIC = 8  # 8 decimals for degrees (~1mm precision)
    WKT_PRECISION_PROJECTED = 3   # 3 decimals for meters (mm precision)
    
    # Tolerance scaling factors for extreme reductions
    EXTREME_REDUCTION_THRESHOLD = 0.01  # 99% reduction needed
    VERY_HIGH_REDUCTION_THRESHOLD = 0.05  # 95% reduction needed
    HIGH_REDUCTION_THRESHOLD = 0.1  # 90% reduction needed
    MODERATE_REDUCTION_THRESHOLD = 0.5  # 50% reduction needed
    
    def __init__(self, config: Optional[SimplificationConfig] = None):
        """
        Initialize BufferService.
        
        Args:
            config: Optional simplification configuration
        """
        self._config = config or SimplificationConfig()
        self._metrics = {
            'buffers_calculated': 0,
            'simplifications_calculated': 0,
            'total_reduction_achieved': 0.0
        }
    
    @property
    def config(self) -> SimplificationConfig:
        """Get current simplification configuration."""
        return self._config
    
    @config.setter
    def config(self, value: SimplificationConfig) -> None:
        """Set simplification configuration."""
        self._config = value
    
    @property
    def metrics(self) -> Dict[str, Any]:
        """Get service metrics."""
        return self._metrics.copy()
    
    def calculate_buffer_aware_tolerance(
        self,
        buffer_config: BufferConfig,
        extent_size: float,
        is_geographic: bool = False
    ) -> float:
        """
        Calculate optimal simplification tolerance based on buffer parameters.
        
        The idea is that when a buffer is applied with specific segments/type,
        the resulting geometry has a known precision. We can safely simplify
        up to that precision level without losing meaningful detail.
        
        For a buffer with N segments per quarter-circle:
        - Arc length per segment ≈ (π/2) * radius / N
        - Maximum error from simplification ≈ radius * (1 - cos(π/(2*N)))
        
        Args:
            buffer_config: Buffer configuration with distance and segments
            extent_size: Maximum extent dimension in map units
            is_geographic: Whether CRS is geographic (degrees)
            
        Returns:
            Recommended simplification tolerance in map units
        """
        self._metrics['buffers_calculated'] += 1
        
        abs_buffer = buffer_config.absolute_distance
        buffer_segments = buffer_config.segments
        buffer_type = buffer_config.end_cap_style
        
        # Default tolerance if no buffer
        if abs_buffer == 0:
            base_tolerance = extent_size * 0.001
        else:
            # Calculate maximum angular error per segment
            # For N segments per quarter circle, each segment covers π/(2*N) radians
            angle_per_segment = math.pi / (2 * buffer_segments)
            
            # Maximum chord-to-arc error is: r * (1 - cos(θ/2))
            # where θ is the angle per segment
            max_arc_error = abs_buffer * (1 - math.cos(angle_per_segment / 2))
            
            # For flat/square endcaps, tolerance can be more aggressive
            # since the buffer edges are straight lines
            if buffer_type in [BufferEndCapStyle.FLAT, BufferEndCapStyle.SQUARE]:
                tolerance_factor = 2.0
            else:  # Round
                tolerance_factor = 1.0
            
            base_tolerance = max_arc_error * tolerance_factor
            
            logger.debug(f"Buffer-aware tolerance: buffer={abs_buffer}, "
                        f"segments={buffer_segments}, type={buffer_type.name}, "
                        f"angle={math.degrees(angle_per_segment):.2f}°, "
                        f"tolerance={base_tolerance:.6f}")
        
        # Convert to degrees if geographic CRS
        if is_geographic:
            # 1 degree ≈ 111km at equator
            base_tolerance = base_tolerance / 111000.0
        
        return base_tolerance
    
    def estimate_simplification_tolerance(
        self,
        extent_size: float,
        target_reduction: float,
        is_geographic: bool = False,
        buffer_config: Optional[BufferConfig] = None
    ) -> float:
        """
        Estimate simplification tolerance based on target reduction.
        
        Args:
            extent_size: Maximum extent dimension
            target_reduction: Target size ratio (0.5 = reduce to 50%)
            is_geographic: Whether CRS is geographic (degrees)
            buffer_config: Optional buffer config for buffer-aware tolerance
            
        Returns:
            Estimated simplification tolerance
        """
        self._metrics['simplifications_calculated'] += 1
        
        # Get tolerance limits
        min_tolerance = self._config.min_tolerance_meters
        max_tolerance = self._config.max_tolerance_meters
        
        # Adjust max tolerance for extreme reductions
        if target_reduction < self.EXTREME_REDUCTION_THRESHOLD:
            extreme_multiplier = min(1.0 / target_reduction, 100) if target_reduction > 0 else 100
            max_tolerance = max_tolerance * extreme_multiplier
            logger.debug(f"Extreme reduction needed ({target_reduction:.4f}), "
                        f"max_tolerance increased to {max_tolerance:.1f}m")
        
        # Use buffer-aware tolerance if available
        if buffer_config is not None and buffer_config.distance != 0:
            buffer_tolerance = self.calculate_buffer_aware_tolerance(
                buffer_config, extent_size, is_geographic
            )
            initial_tolerance = self._scale_tolerance_for_reduction(
                buffer_tolerance, target_reduction
            )
            logger.debug(f"Using buffer-aware tolerance: {buffer_tolerance:.6f} "
                        f"→ scaled to {initial_tolerance:.6f}")
        else:
            # Calculate base tolerance from extent
            if is_geographic:
                min_tolerance = min_tolerance / 111000.0
                max_tolerance = max_tolerance / 111000.0
                base_tolerance = extent_size * 0.0001
            else:
                base_tolerance = extent_size * 0.001
            
            initial_tolerance = self._scale_tolerance_for_reduction(
                base_tolerance, target_reduction
            )
        
        # Clamp to limits
        return max(min_tolerance, min(initial_tolerance, max_tolerance))
    
    def _scale_tolerance_for_reduction(
        self,
        base_tolerance: float,
        target_reduction: float
    ) -> float:
        """
        Scale tolerance based on target reduction ratio.
        
        Args:
            base_tolerance: Base tolerance value
            target_reduction: Target size ratio
            
        Returns:
            Scaled tolerance
        """
        if target_reduction < self.EXTREME_REDUCTION_THRESHOLD:
            return base_tolerance * 50
        elif target_reduction < self.VERY_HIGH_REDUCTION_THRESHOLD:
            return base_tolerance * 20
        elif target_reduction < self.HIGH_REDUCTION_THRESHOLD:
            return base_tolerance * 10
        elif target_reduction < self.MODERATE_REDUCTION_THRESHOLD:
            return base_tolerance * 5
        else:
            return base_tolerance * 2
    
    def get_wkt_precision(self, crs_authid: Optional[str] = None) -> int:
        """
        Get optimal WKT precision for a CRS.
        
        Geographic CRS (degrees) needs more precision than projected (meters).
        
        Args:
            crs_authid: CRS authority ID (e.g., 'EPSG:4326')
            
        Returns:
            Number of decimal places for WKT output
        """
        if not crs_authid:
            return self.WKT_PRECISION_PROJECTED
        
        # Detect geographic CRS
        is_geographic = False
        try:
            if ':' in crs_authid:
                srid = int(crs_authid.split(':')[1])
            else:
                srid = int(crs_authid)
            # Common geographic CRS ranges
            is_geographic = srid == 4326 or (4000 < srid < 5000)
        except (ValueError, IndexError):
            pass
        
        return self.WKT_PRECISION_GEOGRAPHIC if is_geographic else self.WKT_PRECISION_PROJECTED
    
    def validate_buffer_config(
        self,
        config: BufferConfig,
        is_geographic: bool = False
    ) -> Tuple[bool, List[str]]:
        """
        Validate buffer configuration and return warnings.
        
        Args:
            config: Buffer configuration to validate
            is_geographic: Whether layer CRS is geographic
            
        Returns:
            Tuple of (is_valid, list of warning messages)
        """
        warnings = []
        is_valid = True
        
        # Check for geographic CRS with large buffer
        if is_geographic and config.absolute_distance > 1:
            # Buffer > 1 degree is likely wrong
            km_at_equator = config.distance * 111
            warnings.append(
                f"Geographic CRS detected with buffer value {config.distance}°. "
                f"This equals ~{km_at_equator:.0f}km at the equator. "
                "Consider reprojecting to a metric CRS."
            )
            if config.absolute_distance > 10:
                is_valid = False  # This is almost certainly wrong
        
        # Check for very small buffer with many segments
        if config.absolute_distance < 1 and config.segments > 16:
            warnings.append(
                f"Small buffer ({config.distance}) with many segments ({config.segments}). "
                "Consider reducing segments for better performance."
            )
        
        # Check for negative buffer (erosion) warnings
        if config.is_negative:
            warnings.append(
                f"Negative buffer ({config.distance}) will erode geometries. "
                "Small polygons may be completely removed."
            )
        
        return is_valid, warnings
    
    def calculate_progressive_tolerance_sequence(
        self,
        initial_tolerance: float,
        max_iterations: int = 10,
        scale_factor: float = 1.5
    ) -> List[float]:
        """
        Generate a sequence of progressively increasing tolerances.
        
        Used for iterative simplification when target size isn't reached.
        
        Args:
            initial_tolerance: Starting tolerance
            max_iterations: Maximum number of tolerance values
            scale_factor: Factor to multiply tolerance each iteration
            
        Returns:
            List of tolerance values in increasing order
        """
        tolerances = []
        current = initial_tolerance
        
        for _ in range(max_iterations):
            tolerances.append(current)
            current *= scale_factor
        
        return tolerances


def create_buffer_service(
    config: Optional[Dict[str, Any]] = None
) -> BufferService:
    """
    Factory function for BufferService.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Configured BufferService instance
    """
    if config:
        simplification_config = SimplificationConfig(
            enabled=config.get('simplification_enabled', True),
            max_wkt_length=config.get('max_wkt_length', 100000),
            min_tolerance_meters=config.get('min_tolerance_meters', 0.1),
            max_tolerance_meters=config.get('max_tolerance_meters', 10.0),
            show_warnings=config.get('show_warnings', True)
        )
    else:
        simplification_config = None
    
    return BufferService(config=simplification_config)

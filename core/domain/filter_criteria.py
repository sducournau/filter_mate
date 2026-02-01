# -*- coding: utf-8 -*-
"""
Filter Criteria Value Objects.

Immutable representations of filter criteria for both vector and raster layers.
Part of the Unified Filter System (EPIC-UNIFIED-FILTER).

This is a PURE PYTHON module with NO QGIS dependencies,
enabling true unit testing and clear separation of concerns.

Author: FilterMate Team (BMAD - Amelia)
Date: February 2026
Version: 5.0.0-alpha
"""

from dataclasses import dataclass, field
from typing import Protocol, Optional, List, Union, runtime_checkable
from enum import Enum


class LayerType(Enum):
    """Type of layer supported by the unified filtering system.
    
    Attributes:
        VECTOR: Vector layer (points, lines, polygons)
        RASTER: Raster layer (grid data, images, DEMs)
        MESH: Mesh layer (future support)
        POINT_CLOUD: Point cloud layer (future support)
    """
    VECTOR = "vector"
    RASTER = "raster"
    MESH = "mesh"              # Future
    POINT_CLOUD = "point_cloud"  # Future
    
    @classmethod
    def from_string(cls, value: str) -> 'LayerType':
        """Create LayerType from string value.
        
        Args:
            value: String representation ('vector', 'raster', etc.)
            
        Returns:
            Corresponding LayerType enum
            
        Raises:
            ValueError: If value is not a valid layer type
        """
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(f"Unknown layer type: {value}. Valid types: {[t.value for t in cls]}")


@runtime_checkable
class FilterCriteria(Protocol):
    """Protocol defining the common interface for all filter criteria.
    
    This protocol enables duck-typing: any class implementing these
    attributes/methods can be used as filter criteria.
    
    The protocol ensures polymorphic handling of different criteria types
    by the UnifiedFilterService and AbstractFilterStrategy.
    """
    
    @property
    def layer_type(self) -> LayerType:
        """Type of layer these criteria apply to."""
        ...
    
    @property
    def layer_id(self) -> str:
        """QGIS layer ID of the target layer."""
        ...
    
    @property
    def is_valid(self) -> bool:
        """Check if the criteria are valid and complete."""
        ...
    
    def to_display_string(self) -> str:
        """Return a human-readable representation for UI display."""
        ...


@dataclass(frozen=True)
class VectorFilterCriteria:
    """Immutable filter criteria for vector layers.
    
    Compatible with the FilterCriteria protocol.
    Encapsulates all parameters needed for vector filtering.
    
    Attributes:
        layer_id: QGIS layer ID of the target vector layer
        expression: QGIS expression or SQL filter string
        source_layer_id: Optional source layer for spatial filtering
        spatial_predicate: Spatial predicate (intersects, within, etc.)
        buffer_value: Buffer distance for spatial operations (in layer units)
        use_selection: Whether to filter only selected features
        
    Example:
        >>> criteria = VectorFilterCriteria(
        ...     layer_id="layer_123",
        ...     expression="population > 10000",
        ...     spatial_predicate="intersects",
        ...     buffer_value=100.0
        ... )
        >>> criteria.is_valid
        True
        >>> criteria.to_display_string()
        'population > 10000 [intersects] (buffer: 100.0)'
    """
    
    layer_id: str
    expression: str = ""
    source_layer_id: Optional[str] = None
    spatial_predicate: Optional[str] = None
    buffer_value: float = 0.0
    use_selection: bool = False
    
    @property
    def layer_type(self) -> LayerType:
        """Always returns VECTOR for vector criteria."""
        return LayerType.VECTOR
    
    @property
    def is_valid(self) -> bool:
        """Check if criteria are valid.
        
        Valid criteria must have:
        - Non-empty layer_id
        - Non-empty expression OR spatial predicate with source layer
        """
        if not self.layer_id:
            return False
        
        # Valid if has expression
        if self.expression:
            return True
        
        # Valid if has spatial predicate with source
        if self.spatial_predicate and self.source_layer_id:
            return True
        
        return False
    
    @property
    def is_spatial(self) -> bool:
        """Check if this is a spatial filter."""
        return bool(self.spatial_predicate and self.source_layer_id)
    
    @property
    def has_buffer(self) -> bool:
        """Check if a buffer is applied."""
        return self.buffer_value > 0
    
    def to_display_string(self) -> str:
        """Generate human-readable representation.
        
        Returns:
            String like "expression [predicate] (buffer: X)"
        """
        parts = []
        
        if self.expression:
            parts.append(self.expression)
        
        if self.spatial_predicate:
            parts.append(f"[{self.spatial_predicate}]")
        
        if self.buffer_value > 0:
            parts.append(f"(buffer: {self.buffer_value})")
        
        if self.use_selection:
            parts.append("(selection only)")
        
        return " ".join(parts) if parts else "(no filter)"
    
    def with_expression(self, expression: str) -> 'VectorFilterCriteria':
        """Create a new instance with updated expression.
        
        Args:
            expression: New filter expression
            
        Returns:
            New VectorFilterCriteria with updated expression
        """
        return VectorFilterCriteria(
            layer_id=self.layer_id,
            expression=expression,
            source_layer_id=self.source_layer_id,
            spatial_predicate=self.spatial_predicate,
            buffer_value=self.buffer_value,
            use_selection=self.use_selection
        )
    
    def with_spatial(
        self, 
        source_layer_id: str, 
        predicate: str,
        buffer: float = 0.0
    ) -> 'VectorFilterCriteria':
        """Create a new instance with spatial filter.
        
        Args:
            source_layer_id: Source layer for spatial operation
            predicate: Spatial predicate (intersects, within, etc.)
            buffer: Optional buffer distance
            
        Returns:
            New VectorFilterCriteria with spatial parameters
        """
        return VectorFilterCriteria(
            layer_id=self.layer_id,
            expression=self.expression,
            source_layer_id=source_layer_id,
            spatial_predicate=predicate,
            buffer_value=buffer,
            use_selection=self.use_selection
        )


class RasterPredicate(Enum):
    """Predicates for raster value filtering."""
    WITHIN_RANGE = "within_range"       # min <= value <= max
    OUTSIDE_RANGE = "outside_range"     # value < min OR value > max
    ABOVE_VALUE = "above_value"         # value > min
    BELOW_VALUE = "below_value"         # value < max
    EQUALS_VALUE = "equals_value"       # value == target (with tolerance)
    IS_NODATA = "is_nodata"             # value is NoData
    IS_NOT_NODATA = "is_not_nodata"     # value is not NoData


@dataclass(frozen=True)
class RasterFilterCriteria:
    """Immutable filter criteria for raster layers.
    
    Compatible with the FilterCriteria protocol.
    Supports filtering by pixel value ranges and vector masks.
    
    Attributes:
        layer_id: QGIS layer ID of the target raster layer
        band_index: Band number to filter (1-based)
        min_value: Minimum value for range filter
        max_value: Maximum value for range filter
        predicate: Type of value comparison
        mask_layer_id: Optional vector layer for masking
        mask_feature_ids: Specific feature IDs to use as mask
        tolerance: Tolerance for EQUALS_VALUE predicate
        
    Example:
        >>> criteria = RasterFilterCriteria(
        ...     layer_id="dem_123",
        ...     band_index=1,
        ...     min_value=500.0,
        ...     max_value=1500.0
        ... )
        >>> criteria.is_valid
        True
        >>> criteria.to_display_string()
        'Band 1 [500.0 - 1500.0]'
    """
    
    layer_id: str
    band_index: int = 1
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    predicate: RasterPredicate = RasterPredicate.WITHIN_RANGE
    mask_layer_id: Optional[str] = None
    mask_feature_ids: Optional[tuple] = None  # tuple for immutability
    tolerance: float = 0.001
    
    @property
    def layer_type(self) -> LayerType:
        """Always returns RASTER for raster criteria."""
        return LayerType.RASTER
    
    @property
    def is_valid(self) -> bool:
        """Check if criteria are valid.
        
        Valid criteria must have:
        - Non-empty layer_id
        - Valid band index (>= 1)
        - At least one of: value range, mask, or nodata predicate
        - If range specified, min <= max
        """
        if not self.layer_id:
            return False
        
        if self.band_index < 1:
            return False
        
        # Check for inverted range
        if (self.min_value is not None and 
            self.max_value is not None and 
            self.min_value > self.max_value):
            return False
        
        # Valid if has value filter
        if self.min_value is not None or self.max_value is not None:
            return True
        
        # Valid if has mask
        if self.mask_layer_id:
            return True
        
        # Valid if nodata predicate
        if self.predicate in (RasterPredicate.IS_NODATA, RasterPredicate.IS_NOT_NODATA):
            return True
        
        return False
    
    @property
    def has_mask(self) -> bool:
        """Check if a vector mask is applied."""
        return bool(self.mask_layer_id)
    
    @property
    def has_value_range(self) -> bool:
        """Check if a value range is defined."""
        return self.min_value is not None or self.max_value is not None
    
    def to_display_string(self) -> str:
        """Generate human-readable representation.
        
        Returns:
            String like "Band 1 [500 - 1500] (masked)"
        """
        parts = [f"Band {self.band_index}"]
        
        if self.min_value is not None and self.max_value is not None:
            parts.append(f"[{self.min_value} - {self.max_value}]")
        elif self.min_value is not None:
            parts.append(f"> {self.min_value}")
        elif self.max_value is not None:
            parts.append(f"< {self.max_value}")
        
        if self.predicate == RasterPredicate.IS_NODATA:
            parts.append("[NoData only]")
        elif self.predicate == RasterPredicate.IS_NOT_NODATA:
            parts.append("[exclude NoData]")
        elif self.predicate == RasterPredicate.EQUALS_VALUE:
            parts.append(f"[= {self.min_value} ±{self.tolerance}]")
        
        if self.mask_layer_id:
            parts.append("(masked)")
        
        return " ".join(parts)
    
    def with_range(self, min_val: float, max_val: float) -> 'RasterFilterCriteria':
        """Create a new instance with updated value range.
        
        Args:
            min_val: Minimum value
            max_val: Maximum value
            
        Returns:
            New RasterFilterCriteria with updated range
        """
        return RasterFilterCriteria(
            layer_id=self.layer_id,
            band_index=self.band_index,
            min_value=min_val,
            max_value=max_val,
            predicate=RasterPredicate.WITHIN_RANGE,
            mask_layer_id=self.mask_layer_id,
            mask_feature_ids=self.mask_feature_ids,
            tolerance=self.tolerance
        )
    
    def with_mask(
        self, 
        mask_layer_id: str,
        feature_ids: Optional[List[int]] = None
    ) -> 'RasterFilterCriteria':
        """Create a new instance with vector mask.
        
        Args:
            mask_layer_id: Vector layer ID for masking
            feature_ids: Optional specific feature IDs
            
        Returns:
            New RasterFilterCriteria with mask
        """
        return RasterFilterCriteria(
            layer_id=self.layer_id,
            band_index=self.band_index,
            min_value=self.min_value,
            max_value=self.max_value,
            predicate=self.predicate,
            mask_layer_id=mask_layer_id,
            mask_feature_ids=tuple(feature_ids) if feature_ids else None,
            tolerance=self.tolerance
        )
    
    def with_band(self, band_index: int) -> 'RasterFilterCriteria':
        """Create a new instance with different band.
        
        Args:
            band_index: New band index (1-based)
            
        Returns:
            New RasterFilterCriteria for specified band
        """
        return RasterFilterCriteria(
            layer_id=self.layer_id,
            band_index=band_index,
            min_value=self.min_value,
            max_value=self.max_value,
            predicate=self.predicate,
            mask_layer_id=self.mask_layer_id,
            mask_feature_ids=self.mask_feature_ids,
            tolerance=self.tolerance
        )


# Type alias for unified handling
UnifiedFilterCriteria = Union[VectorFilterCriteria, RasterFilterCriteria]


def validate_criteria(criteria: UnifiedFilterCriteria) -> tuple:
    """Validate filter criteria and return detailed error if invalid.
    
    Args:
        criteria: Vector or raster filter criteria
        
    Returns:
        Tuple of (is_valid: bool, error_message: str)
        
    Example:
        >>> criteria = VectorFilterCriteria(layer_id="", expression="test")
        >>> is_valid, error = validate_criteria(criteria)
        >>> is_valid
        False
        >>> error
        'Layer ID is required'
    """
    if not criteria.layer_id:
        return False, "Layer ID is required"
    
    if isinstance(criteria, VectorFilterCriteria):
        if not criteria.expression and not criteria.spatial_predicate:
            return False, "Either expression or spatial predicate is required"
        if criteria.spatial_predicate and not criteria.source_layer_id:
            return False, "Source layer is required for spatial filtering"
    
    elif isinstance(criteria, RasterFilterCriteria):
        if criteria.band_index < 1:
            return False, "Band index must be >= 1"
        if (criteria.min_value is not None and 
            criteria.max_value is not None and 
            criteria.min_value > criteria.max_value):
            return False, "Min value cannot be greater than max value"
        if not criteria.is_valid:
            return False, "At least one filter condition is required (value range, mask, or nodata)"
    
    return True, ""


def criteria_from_dict(data: dict) -> UnifiedFilterCriteria:
    """Create filter criteria from dictionary.
    
    Args:
        data: Dictionary with criteria parameters
              Must include 'layer_type' key
              
    Returns:
        VectorFilterCriteria or RasterFilterCriteria
        
    Raises:
        ValueError: If layer_type is missing or invalid
        
    Example:
        >>> data = {
        ...     'layer_type': 'vector',
        ...     'layer_id': 'layer_123',
        ...     'expression': 'population > 10000'
        ... }
        >>> criteria = criteria_from_dict(data)
        >>> isinstance(criteria, VectorFilterCriteria)
        True
    """
    layer_type_str = data.get('layer_type')
    if not layer_type_str:
        raise ValueError("'layer_type' key is required")
    
    layer_type = LayerType.from_string(layer_type_str)
    
    if layer_type == LayerType.VECTOR:
        return VectorFilterCriteria(
            layer_id=data.get('layer_id', ''),
            expression=data.get('expression', ''),
            source_layer_id=data.get('source_layer_id'),
            spatial_predicate=data.get('spatial_predicate'),
            buffer_value=data.get('buffer_value', 0.0),
            use_selection=data.get('use_selection', False)
        )
    
    elif layer_type == LayerType.RASTER:
        predicate_str = data.get('predicate', 'within_range')
        try:
            predicate = RasterPredicate(predicate_str)
        except ValueError:
            predicate = RasterPredicate.WITHIN_RANGE
        
        mask_fids = data.get('mask_feature_ids')
        
        return RasterFilterCriteria(
            layer_id=data.get('layer_id', ''),
            band_index=data.get('band_index', 1),
            min_value=data.get('min_value'),
            max_value=data.get('max_value'),
            predicate=predicate,
            mask_layer_id=data.get('mask_layer_id'),
            mask_feature_ids=tuple(mask_fids) if mask_fids else None,
            tolerance=data.get('tolerance', 0.001)
        )
    
    else:
        raise ValueError(f"Unsupported layer type: {layer_type}")

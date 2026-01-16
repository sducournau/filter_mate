"""
Filter Expression Value Object.

Immutable representation of a validated filter expression
with provider-specific SQL conversion.

This is a PURE PYTHON module with NO QGIS dependencies,
enabling true unit testing and clear separation of concerns.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict
from enum import Enum


class ProviderType(Enum):
    """
    Supported data provider types.
    
    Maps to QGIS provider types but defined here
    to maintain domain independence.
    """
    POSTGRESQL = "postgresql"
    SPATIALITE = "spatialite"
    OGR = "ogr"
    MEMORY = "memory"
    UNKNOWN = "unknown"
    
    @classmethod
    def from_qgis_provider(cls, provider_type: str) -> 'ProviderType':
        """
        Convert QGIS provider type string to ProviderType.
        
        Args:
            provider_type: QGIS provider type string (e.g., 'postgres', 'spatialite')
            
        Returns:
            Corresponding ProviderType enum value
        """
        mapping = {
            'postgres': cls.POSTGRESQL,
            'postgresql': cls.POSTGRESQL,
            'spatialite': cls.SPATIALITE,
            'ogr': cls.OGR,
            'memory': cls.MEMORY,
        }
        return mapping.get(provider_type.lower(), cls.UNKNOWN)


class SpatialPredicate(Enum):
    """
    Supported spatial predicates for filtering.
    
    These correspond to standard OGC spatial predicates
    used in PostGIS, Spatialite, and QGIS expressions.
    """
    INTERSECTS = "intersects"
    CONTAINS = "contains"
    WITHIN = "within"
    CROSSES = "crosses"
    TOUCHES = "touches"
    OVERLAPS = "overlaps"
    DISJOINT = "disjoint"
    EQUALS = "equals"
    DWITHIN = "dwithin"


@dataclass(frozen=True)
class FilterExpression:
    """
    Immutable value object representing a validated filter expression.

    This object encapsulates:
    - The original QGIS expression
    - The SQL-converted expression for the target provider
    - Metadata about spatial predicates and buffers

    Use the factory method `create()` for proper validation and conversion.

    Attributes:
        raw: Original QGIS expression string
        sql: Provider-specific SQL expression
        provider: Target database provider type
        is_spatial: Whether expression contains spatial predicates
        spatial_predicates: Tuple of spatial predicates used
        source_layer_id: QGIS layer ID of the source layer
        target_layer_ids: QGIS layer IDs of target layers
        buffer_value: Buffer distance if applicable (in layer units)
        buffer_segments: Number of segments for buffer curves
        
    Example:
        >>> expr = FilterExpression.create(
        ...     raw="field_name = 'value'",
        ...     provider=ProviderType.POSTGRESQL,
        ...     source_layer_id="layer_123"
        ... )
        >>> expr.is_simple
        True
    """
    raw: str
    sql: str
    provider: ProviderType
    is_spatial: bool = False
    spatial_predicates: Tuple[SpatialPredicate, ...] = field(default_factory=tuple)
    source_layer_id: str = ""
    target_layer_ids: Tuple[str, ...] = field(default_factory=tuple)
    buffer_value: Optional[float] = None
    buffer_segments: int = 8

    def __post_init__(self) -> None:
        """Validate expression after initialization."""
        if not self.raw or not self.raw.strip():
            raise ValueError("Expression cannot be empty")
        if not isinstance(self.provider, ProviderType):
            raise TypeError(f"provider must be ProviderType, got {type(self.provider)}")
        if self.buffer_value is not None and self.buffer_value < 0:
            raise ValueError("Buffer value cannot be negative")
        if self.buffer_segments < 1:
            raise ValueError("Buffer segments must be at least 1")

    @classmethod
    def create(
        cls,
        raw: str,
        provider: ProviderType,
        source_layer_id: str,
        target_layer_ids: Optional[List[str]] = None,
        buffer_value: Optional[float] = None,
        buffer_segments: int = 8,
        sql: Optional[str] = None
    ) -> 'FilterExpression':
        """
        Factory method with parsing and validation.

        Args:
            raw: QGIS expression string
            provider: Target provider type
            source_layer_id: Source layer QGIS ID
            target_layer_ids: Target layer QGIS IDs
            buffer_value: Optional buffer distance
            buffer_segments: Segments for buffer curves
            sql: Pre-converted SQL (if None, raw is used as placeholder)

        Returns:
            Validated FilterExpression instance

        Raises:
            ValueError: If expression is invalid
        """
        # Detect spatial predicates
        spatial_predicates = cls._detect_spatial_predicates(raw)
        is_spatial = len(spatial_predicates) > 0

        # Use provided SQL or raw as placeholder
        # Actual conversion will be done by ExpressionService
        final_sql = sql if sql is not None else raw

        return cls(
            raw=raw.strip(),
            sql=final_sql,
            provider=provider,
            is_spatial=is_spatial,
            spatial_predicates=tuple(spatial_predicates),
            source_layer_id=source_layer_id,
            target_layer_ids=tuple(target_layer_ids or []),
            buffer_value=buffer_value,
            buffer_segments=buffer_segments
        )

    @classmethod
    def from_spatial_filter(
        cls,
        predicates: Dict,
        source_geometry_wkt: Optional[str] = None,
        buffer_distance: Optional[float] = None,
        use_centroids: bool = False,
        provider: ProviderType = ProviderType.OGR,
        source_layer_id: str = ""
    ) -> 'FilterExpression':
        """
        Create FilterExpression from legacy spatial filter parameters.
        
        v4.2.0: Bridge method for hexagonal architecture activation.
        Converts legacy build_expression() parameters to FilterExpression.
        
        Args:
            predicates: Dict of spatial predicates (e.g., {'0': 'ST_Intersects'})
            source_geometry_wkt: WKT geometry string for source
            buffer_distance: Buffer distance in meters
            use_centroids: Use centroids for filtering
            provider: Target provider type
            source_layer_id: Source layer QGIS ID
            
        Returns:
            FilterExpression for use with new backends
        """
        # Build raw expression from predicates
        predicate_names = []
        for key, value in predicates.items():
            if isinstance(value, str):
                # Extract predicate name (e.g., 'ST_Intersects' -> 'intersects')
                pred_name = value.lower().replace('st_', '')
                predicate_names.append(pred_name)
        
        # Create placeholder expression
        raw = f"SPATIAL_FILTER({', '.join(predicate_names)})"
        if source_geometry_wkt:
            raw += f" WITH GEOMETRY({len(source_geometry_wkt)} chars)"
        if buffer_distance:
            raw += f" BUFFER({buffer_distance}m)"
        if use_centroids:
            raw += " [CENTROIDS]"
        
        # Detect spatial predicates
        spatial_predicates = []
        for pred_name in predicate_names:
            try:
                spatial_predicates.append(SpatialPredicate(pred_name))
            except ValueError:
                pass  # Unknown predicate, skip
        
        return cls(
            raw=raw,
            sql=raw,  # Will be converted by backend
            provider=provider,
            is_spatial=True,
            spatial_predicates=tuple(spatial_predicates),
            source_layer_id=source_layer_id,
            target_layer_ids=(),
            buffer_value=buffer_distance if buffer_distance and buffer_distance > 0 else None,
            buffer_segments=8
        )

    @staticmethod
    def _detect_spatial_predicates(expression: str) -> List[SpatialPredicate]:
        """
        Detect spatial predicates in expression.
        
        Args:
            expression: QGIS expression string
            
        Returns:
            List of detected spatial predicates
        """
        predicates: List[SpatialPredicate] = []
        expr_lower = expression.lower()
        for predicate in SpatialPredicate:
            if predicate.value in expr_lower:
                predicates.append(predicate)
        return predicates

    def with_sql(self, sql: str) -> 'FilterExpression':
        """
        Return new expression with updated SQL.
        
        Args:
            sql: New SQL expression string
            
        Returns:
            New FilterExpression with updated SQL
        """
        return FilterExpression(
            raw=self.raw,
            sql=sql,
            provider=self.provider,
            is_spatial=self.is_spatial,
            spatial_predicates=self.spatial_predicates,
            source_layer_id=self.source_layer_id,
            target_layer_ids=self.target_layer_ids,
            buffer_value=self.buffer_value,
            buffer_segments=self.buffer_segments
        )

    def with_buffer(self, value: float, segments: int = 8) -> 'FilterExpression':
        """
        Return new expression with buffer applied.
        
        Args:
            value: Buffer distance in layer units
            segments: Number of segments for buffer curves
            
        Returns:
            New FilterExpression with buffer applied
        """
        return FilterExpression(
            raw=self.raw,
            sql=self.sql,
            provider=self.provider,
            is_spatial=True,  # Buffer makes it spatial
            spatial_predicates=self.spatial_predicates,
            source_layer_id=self.source_layer_id,
            target_layer_ids=self.target_layer_ids,
            buffer_value=value,
            buffer_segments=segments
        )

    def with_provider(self, provider: ProviderType) -> 'FilterExpression':
        """
        Return new expression with updated provider.
        
        Args:
            provider: New provider type
            
        Returns:
            New FilterExpression with updated provider
        """
        return FilterExpression(
            raw=self.raw,
            sql=self.sql,
            provider=provider,
            is_spatial=self.is_spatial,
            spatial_predicates=self.spatial_predicates,
            source_layer_id=self.source_layer_id,
            target_layer_ids=self.target_layer_ids,
            buffer_value=self.buffer_value,
            buffer_segments=self.buffer_segments
        )

    @property
    def has_buffer(self) -> bool:
        """Check if expression has buffer applied."""
        return self.buffer_value is not None and self.buffer_value > 0

    @property
    def is_simple(self) -> bool:
        """Check if expression is simple (no spatial, no buffer)."""
        return not self.is_spatial and not self.has_buffer

    @property
    def predicate_names(self) -> List[str]:
        """Get list of predicate names as strings."""
        return [p.value for p in self.spatial_predicates]

    def to_sql(self, provider: Optional['ProviderType'] = None) -> str:
        """
        Get SQL representation for the given provider.
        
        v4.2.0: Returns the stored SQL expression.
        For full SQL conversion, use ExpressionService.convert_to_sql().
        
        Args:
            provider: Target provider (optional, defaults to self.provider)
            
        Returns:
            SQL expression string
        """
        # If provider specified and different, note it in logs
        target_provider = provider or self.provider
        
        # Return stored SQL (may need conversion by caller)
        return self.sql

    def __str__(self) -> str:
        """Human-readable representation."""
        buffer_info = f" (buffer: {self.buffer_value})" if self.has_buffer else ""
        spatial_info = " [spatial]" if self.is_spatial else ""
        expr_preview = self.raw[:50] + "..." if len(self.raw) > 50 else self.raw
        return f"FilterExpression({self.provider.value}){spatial_info}: {expr_preview}{buffer_info}"

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"FilterExpression("
            f"raw={self.raw!r}, "
            f"provider={self.provider}, "
            f"is_spatial={self.is_spatial}, "
            f"source_layer_id={self.source_layer_id!r}, "
            f"buffer_value={self.buffer_value})"
        )

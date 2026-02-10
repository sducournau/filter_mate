# -*- coding: utf-8 -*-
"""
Port interface for multi-step filter optimization.

This module defines the abstract interfaces for filter optimization strategies.
The actual implementation is in adapters/qgis/filter_optimizer.py

Part of FilterMate Hexagonal Architecture v3.0
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Set, Callable


class FilterStrategy(Enum):
    """Filter execution strategies for non-PostgreSQL backends."""
    DIRECT = "direct"                           # Direct filter (small datasets)
    ATTRIBUTE_FIRST = "attribute_first"         # Attribute filter then spatial
    BBOX_THEN_EXACT = "bbox_then_exact"         # BBox broad phase, then exact
    PROGRESSIVE_CHUNKS = "progressive_chunks"   # Chunked processing for large sets
    HYBRID = "hybrid"                           # Combined attribute + bbox + exact


@dataclass
class LayerStatistics:
    """
    Statistics about a layer for optimization decisions.

    Pure data class - no QGIS dependencies.
    """
    feature_count: int
    extent_area: float = 0.0
    extent_bounds: Optional[tuple] = None  # (xmin, ymin, xmax, ymax)
    has_spatial_index: bool = False
    geometry_type: int = 0
    avg_vertices_per_feature: float = 0.0
    estimated_complexity: float = 1.0

    @property
    def is_large_dataset(self) -> bool:
        """Check if this is considered a large dataset."""
        return self.feature_count > 50000

    @property
    def is_very_large_dataset(self) -> bool:
        """Check if this is considered a very large dataset."""
        return self.feature_count > 200000


@dataclass
class FilterStep:
    """A single step in a filter execution plan."""
    step_type: str  # "attribute", "bbox_filter", "exact_spatial"
    expression: Optional[str] = None
    estimated_output: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FilterPlan:
    """
    Execution plan for a multi-step filter operation.

    Pure data class - no QGIS dependencies.
    """
    strategy: FilterStrategy
    estimated_selectivity: float  # 0.0 to 1.0
    estimated_cost: float  # Relative cost estimate
    steps: List[FilterStep] = field(default_factory=list)
    chunk_size: int = 10000  # Features per chunk
    use_spatial_index: bool = True
    attribute_filter: Optional[str] = None
    spatial_filter: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "strategy": self.strategy.value,
            "estimated_selectivity": self.estimated_selectivity,
            "estimated_cost": self.estimated_cost,
            "steps": [
                {
                    "type": step.step_type,
                    "expression": step.expression,
                    "estimated_output": step.estimated_output,
                    **step.metadata
                }
                for step in self.steps
            ],
            "chunk_size": self.chunk_size,
            "use_spatial_index": self.use_spatial_index,
            "attribute_filter": self.attribute_filter,
            "spatial_filter": self.spatial_filter
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FilterPlan":
        """Create from dictionary representation."""
        steps = [
            FilterStep(
                step_type=s.get("type", "unknown"),
                expression=s.get("expression"),
                estimated_output=s.get("estimated_output", 0),
                metadata={k: v for k, v in s.items()
                         if k not in ("type", "expression", "estimated_output")}
            )
            for s in data.get("steps", [])
        ]

        return cls(
            strategy=FilterStrategy(data.get("strategy", "direct")),
            estimated_selectivity=data.get("estimated_selectivity", 1.0),
            estimated_cost=data.get("estimated_cost", 1.0),
            steps=steps,
            chunk_size=data.get("chunk_size", 10000),
            use_spatial_index=data.get("use_spatial_index", True),
            attribute_filter=data.get("attribute_filter"),
            spatial_filter=data.get("spatial_filter")
        )


class IFilterOptimizer(ABC):
    """
    Abstract interface for filter optimization.

    Implementations must handle layer analysis, plan building,
    and execution of optimized filter strategies.
    """

    @abstractmethod
    def get_layer_statistics(
        self,
        layer_id: str,
        force_refresh: bool = False
    ) -> LayerStatistics:
        """
        Get statistics for a layer.

        Args:
            layer_id: Unique layer identifier
            force_refresh: Bypass cache if True

        Returns:
            LayerStatistics with layer information
        """

    @abstractmethod
    def build_filter_plan(
        self,
        layer_id: str,
        attribute_filter: Optional[str] = None,
        spatial_extent: Optional[tuple] = None,  # (xmin, ymin, xmax, ymax)
        has_spatial_filter: bool = False
    ) -> FilterPlan:
        """
        Build an optimal filter execution plan.

        Args:
            layer_id: Target layer identifier
            attribute_filter: Optional attribute expression
            spatial_extent: Bounding box for spatial filter
            has_spatial_filter: Whether spatial filtering will be applied

        Returns:
            FilterPlan with optimal strategy
        """

    @abstractmethod
    def execute_attribute_prefilter(
        self,
        layer_id: str,
        expression: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Set[int]:
        """
        Execute attribute pre-filtering phase.

        Args:
            layer_id: Layer identifier
            expression: Attribute filter expression
            progress_callback: Optional (current, total) callback

        Returns:
            Set of matching feature IDs
        """

    @abstractmethod
    def clear_cache(self, layer_id: Optional[str] = None) -> int:
        """
        Clear statistics cache.

        Args:
            layer_id: Optional specific layer to clear

        Returns:
            Number of entries cleared
        """


class ISelectivityEstimator(ABC):
    """Abstract interface for filter selectivity estimation."""

    @abstractmethod
    def estimate_attribute_selectivity(
        self,
        layer_id: str,
        expression: str,
        sample_size: int = 200
    ) -> float:
        """
        Estimate selectivity of an attribute filter by sampling.

        Args:
            layer_id: Layer identifier
            expression: Filter expression
            sample_size: Number of features to sample

        Returns:
            Estimated selectivity (0.0 to 1.0)
        """

    @abstractmethod
    def estimate_spatial_selectivity(
        self,
        layer_id: str,
        source_extent: tuple  # (xmin, ymin, xmax, ymax)
    ) -> float:
        """
        Estimate selectivity of a spatial filter.

        Args:
            layer_id: Layer identifier
            source_extent: Source geometry bounding box

        Returns:
            Estimated selectivity (0.0 to 1.0)
        """


# Configuration for plan building
@dataclass
class PlanBuilderConfig:
    """Configuration thresholds for filter plan building."""
    small_dataset_threshold: int = 1000
    medium_dataset_threshold: int = 50000
    large_dataset_threshold: int = 200000
    very_large_threshold: int = 1000000
    attribute_first_selectivity_threshold: float = 0.3
    bbox_prefilter_threshold: float = 0.5
    base_chunk_size: int = 10000
    min_chunk_size: int = 1000
    max_chunk_size: int = 50000

    def calculate_chunk_size(
        self,
        feature_count: int,
        complexity: float
    ) -> int:
        """Calculate optimal chunk size."""
        base = self.base_chunk_size

        if feature_count > self.very_large_threshold:
            base = self.base_chunk_size // 2

        adjusted = int(base / max(1.0, complexity / 2.0))

        return max(self.min_chunk_size, min(self.max_chunk_size, adjusted))

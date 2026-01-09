# -*- coding: utf-8 -*-
"""
Auto-Optimizer for FilterMate - Hexagonal Architecture.

Intelligent heuristics-based optimizer that automatically recommends and applies
performance optimizations based on layer characteristics.

Part of Phase 4 Backend Refactoring.

Key Optimizations:
==================
1. CENTROID FOR DISTANT LAYERS: Use ST_Centroid() for remote layers
2. GEOMETRY SIMPLIFICATION: Auto-simplify complex geometries
3. BBOX PRE-FILTERING: Use bounding box checks before exact tests
4. ATTRIBUTE-FIRST STRATEGY: Apply attribute filters before spatial
5. BACKEND-SPECIFIC OPTIMIZATIONS

Author: FilterMate Team
Date: January 2026
"""

import logging
import time
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass, field

from ..domain.filter_expression import ProviderType
from ..domain.layer_info import LayerInfo, GeometryType

logger = logging.getLogger('FilterMate.Optimizer.Auto')


# =============================================================================
# Thresholds and Constants
# =============================================================================

# Feature count thresholds for centroid optimization
CENTROID_AUTO_THRESHOLD_DISTANT = 5000
CENTROID_AUTO_THRESHOLD_LOCAL = 50000

# Centroid mode
CENTROID_MODE_DEFAULT = 'point_on_surface'

# Geometry simplification thresholds
SIMPLIFY_AUTO_THRESHOLD = 100000
SIMPLIFY_TOLERANCE_FACTOR = 0.001

# Buffer optimization thresholds
BUFFER_SIMPLIFY_VERTEX_THRESHOLD = 50
BUFFER_SIMPLIFY_FEATURE_THRESHOLD = 1000
BUFFER_SIMPLIFY_DEFAULT_TOLERANCE = 1.0
BUFFER_SEGMENTS_OPTIMIZATION_THRESHOLD = 10000
BUFFER_SEGMENTS_REDUCED_VALUE = 3
BUFFER_SEGMENTS_DEFAULT = 5

# Complexity thresholds
HIGH_COMPLEXITY_VERTICES = 50
VERY_HIGH_COMPLEXITY_VERTICES = 200


class OptimizationType(Enum):
    """Types of automatic optimizations that can be applied."""
    NONE = "none"
    USE_CENTROID_DISTANT = "use_centroid_distant"
    SIMPLIFY_GEOMETRY = "simplify_geometry"
    SIMPLIFY_BEFORE_BUFFER = "simplify_before_buffer"
    REDUCE_BUFFER_SEGMENTS = "reduce_buffer_segments"
    ENABLE_BUFFER_TYPE = "enable_buffer_type"
    BBOX_PREFILTER = "bbox_prefilter"
    ATTRIBUTE_FIRST = "attribute_first"
    PROGRESSIVE_CHUNKS = "progressive_chunks"
    MATERIALIZED_VIEW = "materialized_view"
    RTREE_TEMP_TABLE = "rtree_temp_table"
    MEMORY_OPTIMIZATION = "memory_optimization"


class LayerLocationType(Enum):
    """Classification of layer location/type."""
    LOCAL_FILE = "local_file"
    LOCAL_DATABASE = "local_database"
    REMOTE_DATABASE = "remote_database"
    REMOTE_SERVICE = "remote_service"


@dataclass
class LayerAnalysis:
    """Analysis results for a layer."""
    layer_id: str
    layer_name: str
    provider_type: ProviderType
    location_type: LayerLocationType
    feature_count: int
    geometry_type: GeometryType
    has_spatial_index: bool
    estimated_complexity: float = 1.0
    avg_vertices_per_feature: float = 0.0
    is_distant: bool = False
    is_large: bool = False
    is_complex: bool = False

    @classmethod
    def from_layer_info(cls, layer_info: LayerInfo) -> 'LayerAnalysis':
        """Create analysis from LayerInfo."""
        # Determine location type
        if layer_info.provider_type == ProviderType.POSTGRESQL:
            location_type = LayerLocationType.REMOTE_DATABASE
        elif layer_info.provider_type == ProviderType.SPATIALITE:
            location_type = LayerLocationType.LOCAL_DATABASE
        elif layer_info.provider_type == ProviderType.OGR:
            location_type = LayerLocationType.LOCAL_FILE
        else:
            location_type = LayerLocationType.LOCAL_FILE

        # Determine if distant (WFS, remote services)
        is_distant = location_type == LayerLocationType.REMOTE_SERVICE

        # Determine if large
        is_large = layer_info.feature_count > 50000

        return cls(
            layer_id=layer_info.layer_id,
            layer_name=layer_info.name,
            provider_type=layer_info.provider_type,
            location_type=location_type,
            feature_count=layer_info.feature_count,
            geometry_type=layer_info.geometry_type,
            has_spatial_index=layer_info.has_spatial_index,
            is_distant=is_distant,
            is_large=is_large,
        )


@dataclass
class OptimizationRecommendation:
    """A recommended optimization with justification."""
    optimization_type: OptimizationType
    priority: int  # 1 = highest priority
    estimated_speedup: float  # e.g., 2.0 = 2x faster
    reason: str
    auto_applicable: bool  # Can be applied automatically
    requires_user_consent: bool = False
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert recommendation to dictionary for UI/serialization."""
        return {
            'optimization_type': self.optimization_type.value,
            'priority': self.priority,
            'estimated_speedup': self.estimated_speedup,
            'reason': self.reason,
            'auto_applicable': self.auto_applicable,
            'requires_user_consent': self.requires_user_consent,
            'parameters': self.parameters
        }


@dataclass
class OptimizationPlan:
    """Complete optimization plan for a filtering operation."""
    layer_analysis: LayerAnalysis
    recommendations: List[OptimizationRecommendation]
    final_use_centroids: bool = False
    final_simplify_tolerance: Optional[float] = None
    final_strategy: str = "default"
    estimated_total_speedup: float = 1.0
    warnings: List[str] = field(default_factory=list)

    @property
    def has_recommendations(self) -> bool:
        """Check if plan has any recommendations."""
        return len(self.recommendations) > 0

    @property
    def auto_applicable_count(self) -> int:
        """Count auto-applicable optimizations."""
        return sum(1 for r in self.recommendations if r.auto_applicable)


@dataclass
class OptimizerConfig:
    """Configuration for the AutoOptimizer."""
    enabled: bool = True
    auto_centroid_for_distant: bool = True
    auto_simplify_geometry: bool = False
    auto_strategy_selection: bool = True
    auto_simplify_before_buffer: bool = True
    auto_simplify_after_buffer: bool = True
    show_optimization_hints: bool = True
    centroid_threshold_distant: int = CENTROID_AUTO_THRESHOLD_DISTANT
    centroid_threshold_local: int = CENTROID_AUTO_THRESHOLD_LOCAL
    buffer_simplify_vertex_threshold: int = BUFFER_SIMPLIFY_VERTEX_THRESHOLD
    buffer_simplify_feature_threshold: int = BUFFER_SIMPLIFY_FEATURE_THRESHOLD
    buffer_simplify_default_tolerance: float = BUFFER_SIMPLIFY_DEFAULT_TOLERANCE
    buffer_segments_threshold: int = BUFFER_SEGMENTS_OPTIMIZATION_THRESHOLD
    buffer_segments_reduced: int = BUFFER_SEGMENTS_REDUCED_VALUE

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'OptimizerConfig':
        """Create config from dictionary."""
        def get_value(entry, default):
            if isinstance(entry, dict):
                return entry.get('value', default)
            return entry if entry is not None else default

        return cls(
            enabled=get_value(config_dict.get('enabled'), True),
            auto_centroid_for_distant=get_value(
                config_dict.get('auto_centroid_for_distant'), True
            ),
            auto_simplify_geometry=get_value(
                config_dict.get('auto_simplify_geometry'), False
            ),
            auto_strategy_selection=get_value(
                config_dict.get('auto_strategy_selection'), True
            ),
            auto_simplify_before_buffer=get_value(
                config_dict.get('auto_simplify_before_buffer'), True
            ),
            auto_simplify_after_buffer=get_value(
                config_dict.get('auto_simplify_after_buffer'), True
            ),
            show_optimization_hints=get_value(
                config_dict.get('show_optimization_hints'), True
            ),
            centroid_threshold_distant=get_value(
                config_dict.get('centroid_threshold_distant'),
                CENTROID_AUTO_THRESHOLD_DISTANT
            ),
            centroid_threshold_local=get_value(
                config_dict.get('centroid_threshold_local'),
                CENTROID_AUTO_THRESHOLD_LOCAL
            ),
        )


class AutoOptimizer:
    """
    Automatic optimization engine for FilterMate.

    Analyzes source and target layers and recommends/applies optimizations.
    Pure Python implementation without QGIS dependencies.
    """

    # Analysis cache: layer_id -> (timestamp, analysis)
    _analysis_cache: Dict[str, Tuple[float, LayerAnalysis]] = {}
    _cache_ttl: float = 300.0  # 5 minutes

    def __init__(self, config: Optional[OptimizerConfig] = None):
        """
        Initialize the auto-optimizer.

        Args:
            config: Optimizer configuration
        """
        self._config = config or OptimizerConfig()
        self._metrics = {
            'plans_created': 0,
            'optimizations_applied': 0,
            'total_estimated_speedup': 0.0,
        }

    @property
    def config(self) -> OptimizerConfig:
        """Get optimizer configuration."""
        return self._config

    @property
    def is_enabled(self) -> bool:
        """Check if optimizer is enabled."""
        return self._config.enabled

    def analyze_layer(
        self,
        layer_info: LayerInfo,
        force_refresh: bool = False
    ) -> LayerAnalysis:
        """
        Analyze a layer for optimization opportunities.

        Args:
            layer_info: Layer to analyze
            force_refresh: Bypass cache

        Returns:
            LayerAnalysis with metrics
        """
        current_time = time.time()

        # Check cache
        if not force_refresh and layer_info.layer_id in self._analysis_cache:
            cached_time, cached_analysis = self._analysis_cache[layer_info.layer_id]
            if current_time - cached_time < self._cache_ttl:
                return cached_analysis

        # Perform analysis
        analysis = LayerAnalysis.from_layer_info(layer_info)

        # Update cache
        self._analysis_cache[layer_info.layer_id] = (current_time, analysis)

        return analysis

    def create_optimization_plan(
        self,
        target_layer: LayerInfo,
        source_layer: Optional[LayerInfo] = None,
        source_wkt_length: int = 0,
        predicates: Optional[Dict] = None,
        attribute_filter: Optional[str] = None,
        user_requested_centroids: Optional[bool] = None,
        has_buffer: bool = False,
        buffer_value: float = 0.0
    ) -> OptimizationPlan:
        """
        Create an optimization plan for a filtering operation.

        Args:
            target_layer: Layer being filtered
            source_layer: Source/selection layer
            source_wkt_length: Length of source WKT string
            predicates: Spatial predicates being used
            attribute_filter: Attribute filter expression
            user_requested_centroids: Explicit user choice
            has_buffer: Whether buffer is being applied
            buffer_value: Buffer distance value

        Returns:
            OptimizationPlan with recommendations
        """
        self._metrics['plans_created'] += 1

        # Analyze target layer
        target_analysis = self.analyze_layer(target_layer)

        # Analyze source layer if provided
        source_analysis = None
        if source_layer:
            source_analysis = self.analyze_layer(source_layer)

        # Build recommendations
        recommendations = []
        warnings = []

        # 1. CENTROID OPTIMIZATION
        centroid_rec = self._evaluate_centroid_optimization(
            target_analysis, source_analysis, user_requested_centroids
        )
        if centroid_rec:
            recommendations.append(centroid_rec)

        # 2. SIMPLIFICATION OPTIMIZATION
        simplify_rec = self._evaluate_simplify_optimization(
            target_analysis, source_wkt_length
        )
        if simplify_rec:
            recommendations.append(simplify_rec)
            if simplify_rec.requires_user_consent:
                warnings.append(
                    f"Geometry simplification recommended for {target_analysis.layer_name}"
                )

        # 3. BUFFER SIMPLIFICATION
        buffer_simplify_rec = self._evaluate_buffer_simplify_optimization(
            target_analysis, source_analysis, has_buffer, buffer_value
        )
        if buffer_simplify_rec:
            recommendations.append(buffer_simplify_rec)

        # 4. REDUCE BUFFER SEGMENTS
        buffer_segments_rec = self._evaluate_buffer_segments_optimization(
            target_analysis, has_buffer
        )
        if buffer_segments_rec:
            recommendations.append(buffer_segments_rec)

        # 5. STRATEGY OPTIMIZATION
        strategy_rec = self._evaluate_strategy_optimization(
            target_analysis, attribute_filter, predicates
        )
        if strategy_rec:
            recommendations.append(strategy_rec)

        # Sort by priority
        recommendations.sort(key=lambda r: r.priority)

        # Determine final settings
        final_use_centroids = user_requested_centroids if user_requested_centroids is not None else (
            any(
                r.optimization_type == OptimizationType.USE_CENTROID_DISTANT and r.auto_applicable
                for r in recommendations
            )
        )

        # Calculate final simplify tolerance
        final_simplify = None
        for rec in recommendations:
            if rec.optimization_type in (
                OptimizationType.SIMPLIFY_BEFORE_BUFFER,
                OptimizationType.SIMPLIFY_GEOMETRY
            ) and rec.auto_applicable:
                final_simplify = rec.parameters.get('tolerance')
                break

        # Determine final strategy
        final_strategy = "default"
        for rec in recommendations:
            if rec.optimization_type in (
                OptimizationType.ATTRIBUTE_FIRST,
                OptimizationType.BBOX_PREFILTER,
                OptimizationType.PROGRESSIVE_CHUNKS
            ):
                final_strategy = rec.optimization_type.value
                break

        # Calculate estimated total speedup
        total_speedup = 1.0
        for rec in recommendations:
            if rec.auto_applicable:
                total_speedup *= rec.estimated_speedup

        self._metrics['total_estimated_speedup'] += total_speedup

        return OptimizationPlan(
            layer_analysis=target_analysis,
            recommendations=recommendations,
            final_use_centroids=final_use_centroids,
            final_simplify_tolerance=final_simplify,
            final_strategy=final_strategy,
            estimated_total_speedup=total_speedup,
            warnings=warnings
        )

    def _evaluate_centroid_optimization(
        self,
        target: LayerAnalysis,
        source: Optional[LayerAnalysis],
        user_requested: Optional[bool]
    ) -> Optional[OptimizationRecommendation]:
        """Evaluate if centroid optimization should be applied."""
        if not self._config.auto_centroid_for_distant:
            return None

        # Check if distant layer with enough features
        threshold = (
            self._config.centroid_threshold_distant
            if target.is_distant
            else self._config.centroid_threshold_local
        )

        if target.feature_count < threshold:
            return None

        # Only for polygon geometries
        if target.geometry_type not in (
            GeometryType.POLYGON,
            GeometryType.MULTIPOLYGON
        ):
            return None

        estimated_speedup = 3.0 if target.is_distant else 1.5

        return OptimizationRecommendation(
            optimization_type=OptimizationType.USE_CENTROID_DISTANT,
            priority=1,
            estimated_speedup=estimated_speedup,
            reason=(
                f"Layer '{target.layer_name}' has {target.feature_count} features. "
                f"Using centroids will significantly reduce processing time."
            ),
            auto_applicable=user_requested is None or user_requested,
            parameters={'mode': CENTROID_MODE_DEFAULT}
        )

    def _evaluate_simplify_optimization(
        self,
        target: LayerAnalysis,
        source_wkt_length: int
    ) -> Optional[OptimizationRecommendation]:
        """Evaluate if geometry simplification should be applied."""
        if not self._config.auto_simplify_geometry:
            return None

        if target.feature_count < SIMPLIFY_AUTO_THRESHOLD:
            return None

        if target.avg_vertices_per_feature < HIGH_COMPLEXITY_VERTICES:
            return None

        # Calculate tolerance
        tolerance = SIMPLIFY_TOLERANCE_FACTOR * (target.feature_count / 1000)

        return OptimizationRecommendation(
            optimization_type=OptimizationType.SIMPLIFY_GEOMETRY,
            priority=2,
            estimated_speedup=1.5,
            reason=(
                f"Layer has high geometry complexity "
                f"({target.avg_vertices_per_feature:.0f} avg vertices)"
            ),
            auto_applicable=False,  # Requires user consent
            requires_user_consent=True,
            parameters={'tolerance': tolerance}
        )

    def _evaluate_buffer_simplify_optimization(
        self,
        target: LayerAnalysis,
        source: Optional[LayerAnalysis],
        has_buffer: bool,
        buffer_value: float
    ) -> Optional[OptimizationRecommendation]:
        """Evaluate if buffer simplification should be applied."""
        if not has_buffer or not self._config.auto_simplify_before_buffer:
            return None

        if target.feature_count < self._config.buffer_simplify_feature_threshold:
            return None

        tolerance = self._config.buffer_simplify_default_tolerance

        return OptimizationRecommendation(
            optimization_type=OptimizationType.SIMPLIFY_BEFORE_BUFFER,
            priority=2,
            estimated_speedup=2.0,
            reason=(
                f"Large dataset ({target.feature_count} features) with buffer. "
                f"Simplifying before buffer improves performance."
            ),
            auto_applicable=True,
            parameters={
                'tolerance': tolerance,
                'buffer_value': buffer_value
            }
        )

    def _evaluate_buffer_segments_optimization(
        self,
        target: LayerAnalysis,
        has_buffer: bool
    ) -> Optional[OptimizationRecommendation]:
        """Evaluate if buffer segments should be reduced."""
        if not has_buffer:
            return None

        if target.feature_count < self._config.buffer_segments_threshold:
            return None

        return OptimizationRecommendation(
            optimization_type=OptimizationType.REDUCE_BUFFER_SEGMENTS,
            priority=3,
            estimated_speedup=1.3,
            reason=(
                f"Reducing buffer segments for large dataset "
                f"({target.feature_count} features)"
            ),
            auto_applicable=True,
            parameters={
                'segments': self._config.buffer_segments_reduced,
                'original_segments': BUFFER_SEGMENTS_DEFAULT
            }
        )

    def _evaluate_strategy_optimization(
        self,
        target: LayerAnalysis,
        attribute_filter: Optional[str],
        predicates: Optional[Dict]
    ) -> Optional[OptimizationRecommendation]:
        """Evaluate optimal filtering strategy."""
        if not self._config.auto_strategy_selection:
            return None

        # Attribute-first strategy for selective attribute filters
        if attribute_filter and len(attribute_filter) > 5:
            return OptimizationRecommendation(
                optimization_type=OptimizationType.ATTRIBUTE_FIRST,
                priority=3,
                estimated_speedup=1.5,
                reason="Attribute filter detected, applying attribute-first strategy",
                auto_applicable=True,
                parameters={'filter': attribute_filter}
            )

        # Progressive chunks for very large datasets
        if target.feature_count > 100000:
            return OptimizationRecommendation(
                optimization_type=OptimizationType.PROGRESSIVE_CHUNKS,
                priority=4,
                estimated_speedup=1.2,
                reason=f"Very large dataset ({target.feature_count} features)",
                auto_applicable=True,
                parameters={'chunk_size': 10000}
            )

        return None

    def get_statistics(self) -> Dict[str, Any]:
        """Get optimizer statistics."""
        return self._metrics.copy()

    def reset_statistics(self) -> None:
        """Reset optimizer statistics."""
        self._metrics = {
            'plans_created': 0,
            'optimizations_applied': 0,
            'total_estimated_speedup': 0.0,
        }

    def clear_cache(self) -> int:
        """Clear analysis cache."""
        count = len(self._analysis_cache)
        self._analysis_cache.clear()
        return count


# =============================================================================
# Factory Functions
# =============================================================================

_optimizer_instance: Optional[AutoOptimizer] = None


def get_auto_optimizer(config: Optional[OptimizerConfig] = None) -> AutoOptimizer:
    """
    Get or create the singleton AutoOptimizer instance.

    Args:
        config: Optional configuration

    Returns:
        AutoOptimizer instance
    """
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = AutoOptimizer(config)
    return _optimizer_instance


def create_auto_optimizer(config: Optional[OptimizerConfig] = None) -> AutoOptimizer:
    """
    Create a new AutoOptimizer instance.

    Args:
        config: Optional configuration

    Returns:
        New AutoOptimizer instance
    """
    return AutoOptimizer(config)


def recommend_optimizations(
    target_layer: LayerInfo,
    source_layer: Optional[LayerInfo] = None,
    has_buffer: bool = False,
    attribute_filter: Optional[str] = None
) -> List[OptimizationRecommendation]:
    """
    Quick function to get optimization recommendations.

    Args:
        target_layer: Layer to filter
        source_layer: Source layer
        has_buffer: Whether buffer is applied
        attribute_filter: Attribute filter

    Returns:
        List of recommendations
    """
    optimizer = get_auto_optimizer()
    plan = optimizer.create_optimization_plan(
        target_layer=target_layer,
        source_layer=source_layer,
        has_buffer=has_buffer,
        attribute_filter=attribute_filter
    )
    return plan.recommendations

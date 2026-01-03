# -*- coding: utf-8 -*-
"""
Auto-Optimizer for FilterMate

Intelligent heuristics-based optimizer that automatically recommends and applies
performance optimizations based on:
- Backend type (local vs distant/remote)
- Feature count
- Geometry complexity
- Spatial predicate type

Key Optimizations:
==================
1. CENTROID FOR DISTANT LAYERS: Use ST_Centroid() for remote layers (WFS, ArcGIS)
   - Reduces network data transfer by ~90%
   - Dramatically faster for point-in-polygon queries on distant layers

2. GEOMETRY SIMPLIFICATION: Auto-simplify complex geometries
   - Reduces vertex count for large polygons
   - Improves spatial index efficiency

3. BBOX PRE-FILTERING: Use bounding box checks before exact geometry tests
   - Fast elimination of non-candidates
   - Leverages spatial indexes efficiently

4. ATTRIBUTE-FIRST STRATEGY: Apply attribute filters before spatial
   - Reduces candidates for expensive spatial operations
   - Optimal for highly selective attribute filters

5. BACKEND-SPECIFIC OPTIMIZATIONS:
   - PostgreSQL: Materialized views, R-tree indexes
   - Spatialite: R-tree temp tables
   - OGR/Memory: Progressive chunking

v2.7.0: Initial implementation
"""

import time
from typing import Dict, List, Optional, Tuple, Set, Any
from enum import Enum
from dataclasses import dataclass, field
from qgis.core import (
    QgsVectorLayer,
    QgsRectangle,
    QgsWkbTypes,
)

from ..logging_config import get_tasks_logger
from ..constants import (
    PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR, PROVIDER_MEMORY,
    REMOTE_PROVIDERS, PROVIDER_TYPE_MAPPING,
    PERFORMANCE_THRESHOLD_SMALL, PERFORMANCE_THRESHOLD_MEDIUM,
    PERFORMANCE_THRESHOLD_LARGE, PERFORMANCE_THRESHOLD_XLARGE,
    GEOMETRY_TYPE_POINT, GEOMETRY_TYPE_LINE, GEOMETRY_TYPE_POLYGON,
)

logger = get_tasks_logger()

# Flag to indicate this module is available and functional
# This can be imported by other modules to check availability
AUTO_OPTIMIZER_AVAILABLE = True


# =============================================================================
# Configuration Loading
# =============================================================================

def get_auto_optimization_config() -> Dict[str, Any]:
    """
    Load auto-optimization configuration from ENV_VARS.
    
    Returns:
        Dictionary with configuration values
    """
    # Default values
    defaults = {
        'enabled': True,
        'auto_centroid_for_distant': True,
        'centroid_threshold_distant': 5000,
        'centroid_threshold_local': 50000,
        'auto_simplify_geometry': False,
        'auto_strategy_selection': True,
        'show_optimization_hints': True,
    }
    
    try:
        from ...config.config import ENV_VARS
        
        config_data = ENV_VARS.get('CONFIG_DATA', {})
        auto_opt = config_data.get('APP', {}).get('OPTIONS', {}).get('AUTO_OPTIMIZATION', {})
        
        if not auto_opt:
            return defaults
        
        # Extract values (handle nested 'value' key from config v2.0)
        def get_value(config_entry, default):
            if isinstance(config_entry, dict):
                return config_entry.get('value', default)
            return config_entry
        
        return {
            'enabled': get_value(auto_opt.get('enabled', defaults['enabled']), defaults['enabled']),
            'auto_centroid_for_distant': get_value(
                auto_opt.get('auto_centroid_for_distant', defaults['auto_centroid_for_distant']),
                defaults['auto_centroid_for_distant']
            ),
            'centroid_threshold_distant': get_value(
                auto_opt.get('centroid_threshold_distant', defaults['centroid_threshold_distant']),
                defaults['centroid_threshold_distant']
            ),
            'centroid_threshold_local': get_value(
                auto_opt.get('centroid_threshold_local', defaults['centroid_threshold_local']),
                defaults['centroid_threshold_local']
            ),
            'auto_simplify_geometry': get_value(
                auto_opt.get('auto_simplify_geometry', defaults['auto_simplify_geometry']),
                defaults['auto_simplify_geometry']
            ),
            'auto_strategy_selection': get_value(
                auto_opt.get('auto_strategy_selection', defaults['auto_strategy_selection']),
                defaults['auto_strategy_selection']
            ),
            'show_optimization_hints': get_value(
                auto_opt.get('show_optimization_hints', defaults['show_optimization_hints']),
                defaults['show_optimization_hints']
            ),
        }
    except Exception as e:
        logger.debug(f"Could not load auto-optimization config: {e}")
        return defaults


# =============================================================================
# Optimization Thresholds (loaded from config or defaults)
# =============================================================================

def _get_thresholds() -> Tuple[int, int]:
    """Get centroid thresholds from config."""
    config = get_auto_optimization_config()
    return (
        config.get('centroid_threshold_distant', 5000),
        config.get('centroid_threshold_local', 50000)
    )


# Feature count thresholds for centroid optimization (can be overridden by config)
CENTROID_AUTO_THRESHOLD_DISTANT = 5000      # Auto-enable for distant layers > 5k features
CENTROID_AUTO_THRESHOLD_LOCAL = 50000       # Auto-enable for local layers > 50k features

# Geometry simplification thresholds
SIMPLIFY_AUTO_THRESHOLD = 100000            # Auto-simplify for layers > 100k features
SIMPLIFY_TOLERANCE_FACTOR = 0.001           # Tolerance as fraction of extent diagonal

# Large WKT thresholds (chars)
LARGE_WKT_THRESHOLD = 100000                # Use R-tree optimization above this
VERY_LARGE_WKT_THRESHOLD = 500000           # Force aggressive optimization

# Vertex complexity thresholds
HIGH_COMPLEXITY_VERTICES = 50               # Average vertices per feature for "complex"
VERY_HIGH_COMPLEXITY_VERTICES = 200         # Average vertices for "very complex"


class OptimizationType(Enum):
    """Types of automatic optimizations that can be applied."""
    NONE = "none"
    USE_CENTROID = "use_centroid"
    SIMPLIFY_GEOMETRY = "simplify_geometry"
    BBOX_PREFILTER = "bbox_prefilter"
    ATTRIBUTE_FIRST = "attribute_first"
    PROGRESSIVE_CHUNKS = "progressive_chunks"
    MATERIALIZED_VIEW = "materialized_view"
    RTREE_TEMP_TABLE = "rtree_temp_table"
    MEMORY_OPTIMIZATION = "memory_optimization"


class LayerLocationType(Enum):
    """Classification of layer location/type."""
    LOCAL_FILE = "local_file"           # Shapefile, GeoPackage, etc.
    LOCAL_DATABASE = "local_database"   # Spatialite, local PostgreSQL
    REMOTE_DATABASE = "remote_database" # Remote PostgreSQL
    REMOTE_SERVICE = "remote_service"   # WFS, ArcGIS Feature Service


@dataclass
class LayerAnalysis:
    """Analysis results for a layer."""
    layer_id: str
    layer_name: str
    provider_type: str
    location_type: LayerLocationType
    feature_count: int
    geometry_type: int
    has_spatial_index: bool
    estimated_complexity: float = 1.0
    avg_vertices_per_feature: float = 0.0
    is_distant: bool = False
    is_large: bool = False
    is_complex: bool = False


@dataclass
class OptimizationRecommendation:
    """A recommended optimization with justification."""
    optimization_type: OptimizationType
    priority: int                       # 1 = highest priority
    estimated_speedup: float            # e.g., 2.0 = 2x faster
    reason: str
    auto_applicable: bool               # Can be applied automatically
    requires_user_consent: bool = False # Needs user confirmation (lossy)
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert recommendation to dictionary for UI/serialization."""
        return {
            'optimization_type': self.optimization_type.value if isinstance(self.optimization_type, Enum) else str(self.optimization_type),
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


class LayerAnalyzer:
    """
    Analyzes layers to determine optimal filtering strategies.
    """
    
    # Cache for analysis results (layer_id -> (timestamp, analysis))
    _analysis_cache: Dict[str, Tuple[float, LayerAnalysis]] = {}
    _cache_ttl: float = 300.0  # 5 minutes
    
    @classmethod
    def analyze_layer(
        cls, 
        layer: QgsVectorLayer,
        force_refresh: bool = False
    ) -> LayerAnalysis:
        """
        Perform comprehensive analysis of a layer.
        
        Args:
            layer: Vector layer to analyze
            force_refresh: Bypass cache if True
            
        Returns:
            LayerAnalysis with all relevant metrics
        """
        layer_id = layer.id()
        current_time = time.time()
        
        # Check cache
        if not force_refresh and layer_id in cls._analysis_cache:
            cached_time, cached_analysis = cls._analysis_cache[layer_id]
            if current_time - cached_time < cls._cache_ttl:
                return cached_analysis
        
        # Perform analysis
        analysis = cls._perform_analysis(layer)
        
        # Update cache
        cls._analysis_cache[layer_id] = (current_time, analysis)
        
        return analysis
    
    @classmethod
    def _perform_analysis(cls, layer: QgsVectorLayer) -> LayerAnalysis:
        """Perform the actual layer analysis."""
        provider_type = layer.providerType()
        qgis_provider = provider_type
        
        # Map to FilterMate provider type
        filtermate_provider = PROVIDER_TYPE_MAPPING.get(provider_type, PROVIDER_OGR)
        
        # Determine location type
        location_type = cls._determine_location_type(layer, qgis_provider)
        
        # Get feature count safely
        feature_count = layer.featureCount()
        if feature_count < 0:
            feature_count = 0  # Unknown
        
        # Check spatial index
        has_spatial_index = False
        try:
            has_spatial_index = layer.hasSpatialIndex() if hasattr(layer, 'hasSpatialIndex') else False
        except:
            pass
        
        # Estimate geometry complexity
        avg_vertices, complexity = cls._estimate_complexity(layer)
        
        # Determine flags
        is_distant = location_type in (LayerLocationType.REMOTE_SERVICE, LayerLocationType.REMOTE_DATABASE)
        is_large = feature_count > PERFORMANCE_THRESHOLD_MEDIUM
        is_complex = avg_vertices > HIGH_COMPLEXITY_VERTICES
        
        return LayerAnalysis(
            layer_id=layer.id(),
            layer_name=layer.name(),
            provider_type=filtermate_provider,
            location_type=location_type,
            feature_count=feature_count,
            geometry_type=layer.geometryType(),
            has_spatial_index=has_spatial_index,
            estimated_complexity=complexity,
            avg_vertices_per_feature=avg_vertices,
            is_distant=is_distant,
            is_large=is_large,
            is_complex=is_complex
        )
    
    @classmethod
    def _determine_location_type(
        cls, 
        layer: QgsVectorLayer, 
        provider: str
    ) -> LayerLocationType:
        """Determine if layer is local, remote database, or remote service."""
        
        # Check for remote services
        if provider in REMOTE_PROVIDERS or provider.lower() in REMOTE_PROVIDERS:
            return LayerLocationType.REMOTE_SERVICE
        
        # Check source URI for remote database indicators
        source = layer.source().lower()
        
        # PostgreSQL/PostGIS
        if provider == 'postgres':
            # Check if it's a remote connection
            if 'host=' in source:
                # Extract host
                import re
                host_match = re.search(r"host='?([^'\s]+)'?", source)
                if host_match:
                    host = host_match.group(1)
                    # Local hosts
                    if host in ('localhost', '127.0.0.1', '::1', 'host.docker.internal'):
                        return LayerLocationType.LOCAL_DATABASE
                    else:
                        return LayerLocationType.REMOTE_DATABASE
            return LayerLocationType.LOCAL_DATABASE  # Default if no host
        
        # Spatialite is always local
        if provider == 'spatialite':
            return LayerLocationType.LOCAL_DATABASE
        
        # OGR/memory are local
        if provider in ('ogr', 'memory'):
            return LayerLocationType.LOCAL_FILE
        
        # Default to local file
        return LayerLocationType.LOCAL_FILE
    
    @classmethod
    def _estimate_complexity(
        cls, 
        layer: QgsVectorLayer,
        sample_size: int = 50
    ) -> Tuple[float, float]:
        """
        Estimate geometry complexity by sampling.
        
        Returns:
            Tuple of (avg_vertices, complexity_factor)
        """
        feature_count = layer.featureCount()
        if feature_count == 0:
            return (0.0, 1.0)
        
        try:
            from qgis.core import QgsFeatureRequest
            
            actual_sample = min(sample_size, feature_count)
            request = QgsFeatureRequest()
            request.setLimit(actual_sample)
            
            total_vertices = 0
            sampled = 0
            
            for feat in layer.getFeatures(request):
                geom = feat.geometry()
                if geom and not geom.isEmpty():
                    # Quick vertex count from WKT
                    wkt = geom.asWkt()
                    vertex_count = wkt.count(',') + 1
                    total_vertices += vertex_count
                    sampled += 1
            
            if sampled > 0:
                avg_vertices = total_vertices / sampled
                # Complexity: 1.0 for simple, scales with vertices
                complexity = max(1.0, avg_vertices / 10.0)
                return (avg_vertices, complexity)
            
        except Exception as e:
            logger.debug(f"Complexity estimation failed: {e}")
        
        return (10.0, 1.0)  # Default
    
    @classmethod
    def clear_cache(cls, layer_id: Optional[str] = None):
        """Clear analysis cache."""
        if layer_id:
            cls._analysis_cache.pop(layer_id, None)
        else:
            cls._analysis_cache.clear()


class AutoOptimizer:
    """
    Automatic optimization engine for FilterMate.
    
    Analyzes source and target layers and recommends/applies optimizations.
    Configuration is loaded from config.json AUTO_OPTIMIZATION section.
    """
    
    def __init__(
        self,
        enable_auto_centroid: Optional[bool] = None,
        enable_auto_simplify: Optional[bool] = None,
        enable_auto_strategy: Optional[bool] = None
    ):
        """
        Initialize the auto-optimizer.
        
        Args:
            enable_auto_centroid: Auto-enable centroid for distant layers (None = use config)
            enable_auto_simplify: Auto-enable geometry simplification (None = use config)
            enable_auto_strategy: Auto-select optimal filtering strategy (None = use config)
        """
        # Load configuration
        config = get_auto_optimization_config()
        
        # Check if auto-optimization is globally enabled
        self.globally_enabled = config.get('enabled', True)
        
        # Use provided values or fall back to config
        self.enable_auto_centroid = enable_auto_centroid if enable_auto_centroid is not None else config.get('auto_centroid_for_distant', True)
        self.enable_auto_simplify = enable_auto_simplify if enable_auto_simplify is not None else config.get('auto_simplify_geometry', False)
        self.enable_auto_strategy = enable_auto_strategy if enable_auto_strategy is not None else config.get('auto_strategy_selection', True)
        
        # Load thresholds from config
        self.centroid_threshold_distant = config.get('centroid_threshold_distant', CENTROID_AUTO_THRESHOLD_DISTANT)
        self.centroid_threshold_local = config.get('centroid_threshold_local', CENTROID_AUTO_THRESHOLD_LOCAL)
        self.show_hints = config.get('show_optimization_hints', True)
    
    def create_optimization_plan(
        self,
        target_layer: QgsVectorLayer,
        source_layer: Optional[QgsVectorLayer] = None,
        source_wkt_length: int = 0,
        predicates: Optional[Dict] = None,
        attribute_filter: Optional[str] = None,
        user_requested_centroids: Optional[bool] = None
    ) -> OptimizationPlan:
        """
        Create an optimization plan for a filtering operation.
        
        Args:
            target_layer: Layer being filtered
            source_layer: Source/selection layer (if any)
            source_wkt_length: Length of source WKT string
            predicates: Spatial predicates being used
            attribute_filter: Attribute filter expression
            user_requested_centroids: Explicit user choice (None = auto)
            
        Returns:
            OptimizationPlan with recommendations
        """
        # Analyze target layer
        target_analysis = LayerAnalyzer.analyze_layer(target_layer)
        
        # Analyze source layer if provided
        source_analysis = None
        if source_layer:
            source_analysis = LayerAnalyzer.analyze_layer(source_layer)
        
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
                    f"Geometry simplification recommended for {target_analysis.layer_name} "
                    f"(reduces precision but improves performance)"
                )
        
        # 3. STRATEGY OPTIMIZATION
        strategy_rec = self._evaluate_strategy_optimization(
            target_analysis, attribute_filter, predicates
        )
        if strategy_rec:
            recommendations.append(strategy_rec)
        
        # Sort by priority
        recommendations.sort(key=lambda r: r.priority)
        
        # Determine final settings
        final_use_centroids = user_requested_centroids if user_requested_centroids is not None else (
            any(r.optimization_type == OptimizationType.USE_CENTROID and r.auto_applicable 
                for r in recommendations)
        )
        
        final_simplify = None
        for rec in recommendations:
            if rec.optimization_type == OptimizationType.SIMPLIFY_GEOMETRY and rec.auto_applicable:
                final_simplify = rec.parameters.get('tolerance')
                break
        
        final_strategy = "default"
        for rec in recommendations:
            if rec.optimization_type in (
                OptimizationType.ATTRIBUTE_FIRST,
                OptimizationType.BBOX_PREFILTER,
                OptimizationType.PROGRESSIVE_CHUNKS
            ):
                final_strategy = rec.optimization_type.value
                break
        
        # Calculate total estimated speedup
        total_speedup = 1.0
        for rec in recommendations:
            if rec.auto_applicable or rec.optimization_type == OptimizationType.USE_CENTROID:
                total_speedup *= rec.estimated_speedup
        
        plan = OptimizationPlan(
            layer_analysis=target_analysis,
            recommendations=recommendations,
            final_use_centroids=final_use_centroids,
            final_simplify_tolerance=final_simplify,
            final_strategy=final_strategy,
            estimated_total_speedup=total_speedup,
            warnings=warnings
        )
        
        # Log the plan
        self._log_plan(plan)
        
        return plan
    
    def get_recommendations(
        self,
        layer_analysis: 'LayerAnalysis'
    ) -> List[OptimizationRecommendation]:
        """
        Get optimization recommendations for a single layer.
        
        This is a simplified interface for getting recommendations based solely
        on a layer analysis, without requiring source layer or filter context.
        
        Args:
            layer_analysis: Analysis of the layer to optimize
            
        Returns:
            List of OptimizationRecommendation objects
        """
        if not layer_analysis:
            return []
        
        recommendations = []
        
        # 1. CENTROID OPTIMIZATION - check if layer would benefit from centroid usage
        centroid_rec = self._evaluate_centroid_optimization(
            target=layer_analysis,
            source=None,
            user_requested=None
        )
        if centroid_rec:
            recommendations.append(centroid_rec)
        
        # 2. SIMPLIFICATION OPTIMIZATION - check if complex geometries need simplification
        simplify_rec = self._evaluate_simplify_optimization(
            target=layer_analysis,
            source_wkt_length=0
        )
        if simplify_rec:
            recommendations.append(simplify_rec)
        
        # 3. STRATEGY OPTIMIZATION - check for optimal strategy recommendations
        strategy_rec = self._evaluate_strategy_optimization(
            target=layer_analysis,
            predicates=None,
            attribute_filter=None
        )
        if strategy_rec:
            recommendations.append(strategy_rec)
        
        # Sort by priority (lowest number = highest priority)
        recommendations.sort(key=lambda r: r.priority)
        
        return recommendations
    
    def _evaluate_centroid_optimization(
        self,
        target: LayerAnalysis,
        source: Optional[LayerAnalysis],
        user_requested: Optional[bool]
    ) -> Optional[OptimizationRecommendation]:
        """Evaluate if centroid optimization should be recommended."""
        
        # User explicitly disabled
        if user_requested is False:
            return None
        
        # User explicitly enabled
        if user_requested is True:
            return OptimizationRecommendation(
                optimization_type=OptimizationType.USE_CENTROID,
                priority=1,
                estimated_speedup=3.0,
                reason="User requested centroid optimization",
                auto_applicable=True,
                parameters={"force": True}
            )
        
        # Auto-detection logic - check if globally enabled
        if not self.globally_enabled or not self.enable_auto_centroid:
            return None
        
        # Check target layer characteristics
        should_recommend = False
        reason_parts = []
        speedup = 1.0
        
        # Use configurable thresholds
        threshold_distant = self.centroid_threshold_distant
        threshold_local = self.centroid_threshold_local
        
        # CASE 1: Distant/remote layer with significant data
        if target.is_distant and target.feature_count > threshold_distant:
            should_recommend = True
            reason_parts.append(f"distant layer with {target.feature_count:,} features (> {threshold_distant:,} threshold)")
            speedup = 5.0  # Network reduction is huge
        
        # CASE 2: Large local layer with complex geometries
        elif target.feature_count > threshold_local and target.is_complex:
            should_recommend = True
            reason_parts.append(
                f"large layer ({target.feature_count:,} features > {threshold_local:,}) "
                f"with complex geometries ({target.avg_vertices_per_feature:.0f} avg vertices)"
            )
            speedup = 2.0
        
        # CASE 3: Very large layer regardless of complexity
        elif target.feature_count > PERFORMANCE_THRESHOLD_XLARGE:
            should_recommend = True
            reason_parts.append(f"very large layer ({target.feature_count:,} features)")
            speedup = 1.5
        
        # CASE 4: Polygon geometry on distant layer (any size)
        if target.is_distant and target.geometry_type == GEOMETRY_TYPE_POLYGON:
            if not should_recommend:
                should_recommend = True
                speedup = 3.0
            reason_parts.append("polygon geometries on distant layer")
        
        if not should_recommend:
            return None
        
        return OptimizationRecommendation(
            optimization_type=OptimizationType.USE_CENTROID,
            priority=1,
            estimated_speedup=speedup,
            reason=f"Centroid recommended: {'; '.join(reason_parts)}",
            auto_applicable=True,
            requires_user_consent=False,
            parameters={"auto_detected": True}
        )
    
    def _evaluate_simplify_optimization(
        self,
        target: LayerAnalysis,
        source_wkt_length: int
    ) -> Optional[OptimizationRecommendation]:
        """Evaluate if geometry simplification should be recommended."""
        
        if not self.enable_auto_simplify:
            return None
        
        # Check for very large WKT (source geometry)
        if source_wkt_length > VERY_LARGE_WKT_THRESHOLD:
            return OptimizationRecommendation(
                optimization_type=OptimizationType.SIMPLIFY_GEOMETRY,
                priority=2,
                estimated_speedup=3.0,
                reason=f"Source geometry is very large ({source_wkt_length:,} chars)",
                auto_applicable=False,  # Requires consent (lossy)
                requires_user_consent=True,
                parameters={
                    "tolerance": SIMPLIFY_TOLERANCE_FACTOR,
                    "target": "source"
                }
            )
        
        # Check for complex target layer
        if target.avg_vertices_per_feature > VERY_HIGH_COMPLEXITY_VERTICES:
            return OptimizationRecommendation(
                optimization_type=OptimizationType.SIMPLIFY_GEOMETRY,
                priority=3,
                estimated_speedup=2.0,
                reason=f"Target layer has very complex geometries ({target.avg_vertices_per_feature:.0f} avg vertices)",
                auto_applicable=False,
                requires_user_consent=True,
                parameters={
                    "tolerance": SIMPLIFY_TOLERANCE_FACTOR,
                    "target": "target"
                }
            )
        
        return None
    
    def _evaluate_strategy_optimization(
        self,
        target: LayerAnalysis,
        attribute_filter: Optional[str],
        predicates: Optional[Dict]
    ) -> Optional[OptimizationRecommendation]:
        """Evaluate optimal filtering strategy."""
        
        if not self.enable_auto_strategy:
            return None
        
        feature_count = target.feature_count
        
        # Very large dataset: progressive chunks
        if feature_count > PERFORMANCE_THRESHOLD_LARGE:
            return OptimizationRecommendation(
                optimization_type=OptimizationType.PROGRESSIVE_CHUNKS,
                priority=4,
                estimated_speedup=1.3,
                reason=f"Large dataset ({feature_count:,} features) - using progressive chunking",
                auto_applicable=True,
                parameters={"chunk_size": 10000}
            )
        
        # Has selective attribute filter: attribute-first
        if attribute_filter and feature_count > PERFORMANCE_THRESHOLD_SMALL:
            return OptimizationRecommendation(
                optimization_type=OptimizationType.ATTRIBUTE_FIRST,
                priority=3,
                estimated_speedup=1.5,
                reason="Attribute filter present - applying before spatial operations",
                auto_applicable=True,
                parameters={"expression": attribute_filter}
            )
        
        # Medium dataset with spatial filter: bbox prefilter
        if predicates and feature_count > PERFORMANCE_THRESHOLD_MEDIUM:
            return OptimizationRecommendation(
                optimization_type=OptimizationType.BBOX_PREFILTER,
                priority=5,
                estimated_speedup=1.2,
                reason="Medium dataset with spatial filter - using bbox pre-filtering",
                auto_applicable=True
            )
        
        return None
    
    def _log_plan(self, plan: OptimizationPlan):
        """Log the optimization plan."""
        analysis = plan.layer_analysis
        
        location_emoji = {
            LayerLocationType.LOCAL_FILE: "📁",
            LayerLocationType.LOCAL_DATABASE: "🗄️",
            LayerLocationType.REMOTE_DATABASE: "🌐",
            LayerLocationType.REMOTE_SERVICE: "☁️"
        }
        
        logger.info(
            f"🔧 Auto-Optimization Plan for {analysis.layer_name}:\n"
            f"   📊 Features: {analysis.feature_count:,}\n"
            f"   {location_emoji.get(analysis.location_type, '❓')} Type: {analysis.location_type.value}\n"
            f"   ⚙️ Provider: {analysis.provider_type}\n"
            f"   📐 Complexity: {analysis.estimated_complexity:.1f}x"
        )
        
        if plan.recommendations:
            logger.info(f"   💡 Recommendations ({len(plan.recommendations)}):")
            for rec in plan.recommendations:
                auto_tag = "✅" if rec.auto_applicable else "⚠️"
                logger.info(
                    f"      {auto_tag} {rec.optimization_type.value}: "
                    f"~{rec.estimated_speedup:.1f}x speedup - {rec.reason[:60]}"
                )
        
        if plan.final_use_centroids:
            logger.info(f"   🎯 CENTROID MODE ENABLED")
        
        if plan.estimated_total_speedup > 1.1:
            logger.info(f"   🚀 Estimated total speedup: {plan.estimated_total_speedup:.1f}x")
        
        for warning in plan.warnings:
            logger.warning(f"   ⚠️ {warning}")


def get_auto_optimizer(
    enable_auto_centroid: bool = True,
    enable_auto_simplify: bool = False,
    enable_auto_strategy: bool = True
) -> AutoOptimizer:
    """
    Factory function to get an auto-optimizer instance.
    
    Args:
        enable_auto_centroid: Enable automatic centroid optimization
        enable_auto_simplify: Enable automatic geometry simplification (lossy)
        enable_auto_strategy: Enable automatic strategy selection
        
    Returns:
        Configured AutoOptimizer instance
    """
    return AutoOptimizer(
        enable_auto_centroid=enable_auto_centroid,
        enable_auto_simplify=enable_auto_simplify,
        enable_auto_strategy=enable_auto_strategy
    )


def recommend_optimizations(
    target_layer: QgsVectorLayer,
    source_layer: Optional[QgsVectorLayer] = None,
    source_wkt_length: int = 0,
    predicates: Optional[Dict] = None,
    attribute_filter: Optional[str] = None,
    user_requested_centroids: Optional[bool] = None
) -> OptimizationPlan:
    """
    Convenience function to get optimization recommendations.
    
    Args:
        target_layer: Layer being filtered
        source_layer: Source/selection layer (if any)
        source_wkt_length: Length of source WKT string
        predicates: Spatial predicates being used
        attribute_filter: Attribute filter expression
        user_requested_centroids: Explicit user choice (None = auto)
        
    Returns:
        OptimizationPlan with recommendations
    """
    optimizer = get_auto_optimizer()
    return optimizer.create_optimization_plan(
        target_layer=target_layer,
        source_layer=source_layer,
        source_wkt_length=source_wkt_length,
        predicates=predicates,
        attribute_filter=attribute_filter,
        user_requested_centroids=user_requested_centroids
    )

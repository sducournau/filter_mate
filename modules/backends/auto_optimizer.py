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
from typing import Dict, List, Optional, Tuple, Set, Any, Callable
from enum import Enum
from dataclasses import dataclass, field
from qgis.core import (
    QgsVectorLayer,
    QgsRectangle,
    QgsWkbTypes,
    QgsGeometry,
)

from ..logging_config import get_tasks_logger
from ..constants import (
    PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR, PROVIDER_MEMORY,
    REMOTE_PROVIDERS, PROVIDER_TYPE_MAPPING,
    PERFORMANCE_THRESHOLD_SMALL, PERFORMANCE_THRESHOLD_MEDIUM,
    PERFORMANCE_THRESHOLD_LARGE, PERFORMANCE_THRESHOLD_XLARGE,
    GEOMETRY_TYPE_POINT, GEOMETRY_TYPE_LINE, GEOMETRY_TYPE_POLYGON,
)

# Import metrics and parallel processing (optional - graceful fallback)
try:
    from .optimizer_metrics import (
        get_metrics_collector,
        OptimizationMetricsCollector,
        LRUCache,
        QueryPatternDetector,
        AdaptiveThresholdManager,
        SelectivityHistogram,
    )
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    get_metrics_collector = None

try:
    from .parallel_processor import (
        ParallelChunkProcessor,
        get_parallel_processor,
        should_use_parallel_processing,
        PARALLEL_AVAILABLE,
    )
except ImportError:
    PARALLEL_AVAILABLE = False
    get_parallel_processor = None
    should_use_parallel_processing = lambda *args, **kwargs: False

logger = get_tasks_logger()

# Flag to indicate this module is available and functional
# This can be imported by other modules to check availability
AUTO_OPTIMIZER_AVAILABLE = True

# Additional feature flags
ENHANCED_OPTIMIZER_AVAILABLE = METRICS_AVAILABLE and PARALLEL_AVAILABLE


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
        'auto_simplify_before_buffer': True,
        'auto_simplify_after_buffer': True,
        'buffer_simplify_after_tolerance': 0.5,
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
            'auto_simplify_before_buffer': get_value(
                auto_opt.get('auto_simplify_before_buffer', defaults['auto_simplify_before_buffer']),
                defaults['auto_simplify_before_buffer']
            ),
            'auto_simplify_after_buffer': get_value(
                auto_opt.get('auto_simplify_after_buffer', defaults['auto_simplify_after_buffer']),
                defaults['auto_simplify_after_buffer']
            ),
            'buffer_simplify_after_tolerance': get_value(
                auto_opt.get('buffer_simplify_after_tolerance', defaults['buffer_simplify_after_tolerance']),
                defaults['buffer_simplify_after_tolerance']
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

# v2.9.2: Centroid mode selection
# 'centroid' = ST_Centroid() - fast but may be outside concave polygons
# 'point_on_surface' = ST_PointOnSurface() - guaranteed inside polygon (recommended)
# 'auto' = Use PointOnSurface for polygons, Centroid for lines
CENTROID_MODE_DEFAULT = 'point_on_surface'

# Geometry simplification thresholds
SIMPLIFY_AUTO_THRESHOLD = 100000            # Auto-simplify for layers > 100k features
SIMPLIFY_TOLERANCE_FACTOR = 0.001           # Tolerance as fraction of extent diagonal

# v2.9.2: Enhanced buffer simplification thresholds
# Lower thresholds = more aggressive simplification (better performance)
BUFFER_SIMPLIFY_VERTEX_THRESHOLD = 50       # Simplify before buffer if avg vertices > this
BUFFER_SIMPLIFY_FEATURE_THRESHOLD = 1000    # Simplify before buffer if feature count > this
BUFFER_SIMPLIFY_DEFAULT_TOLERANCE = 1.0     # Default tolerance in meters for buffer simplification

# Buffer segments optimization thresholds
BUFFER_SEGMENTS_OPTIMIZATION_THRESHOLD = 10000  # Reduce segments if feature count > this
BUFFER_SEGMENTS_REDUCED_VALUE = 3               # Reduced number of segments for performance
BUFFER_SEGMENTS_DEFAULT = 5                     # Default number of segments

# Large WKT thresholds (chars)
LARGE_WKT_THRESHOLD = 100000                # Use R-tree optimization above this
VERY_LARGE_WKT_THRESHOLD = 500000           # Force aggressive optimization

# Vertex complexity thresholds
HIGH_COMPLEXITY_VERTICES = 50               # Average vertices per feature for "complex"
VERY_HIGH_COMPLEXITY_VERTICES = 200         # Average vertices for "very complex"


class OptimizationType(Enum):
    """Types of automatic optimizations that can be applied."""
    NONE = "none"
    # v2.8.7: Centroid for distant/filtering layers only
    USE_CENTROID_DISTANT = "use_centroid_distant"
    SIMPLIFY_GEOMETRY = "simplify_geometry"
    SIMPLIFY_BEFORE_BUFFER = "simplify_before_buffer"  # Simplify geometry before buffer
    REDUCE_BUFFER_SEGMENTS = "reduce_buffer_segments"  # Reduce buffer segments
    ENABLE_BUFFER_TYPE = "enable_buffer_type"  # Enable buffer type with 1 segment
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
        # CRITICAL FIX v3.0.10: Protect against None/invalid feature count
        feature_count = layer.featureCount()
        if feature_count is None or feature_count < 0:
            feature_count = 0  # Unknown
        
        # Check spatial index
        has_spatial_index = False
        try:
            has_spatial_index = layer.hasSpatialIndex() if hasattr(layer, 'hasSpatialIndex') else False
        except (RuntimeError, AttributeError):
            pass  # Layer may not support spatial index check
        
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
        # CRITICAL FIX v3.0.10: Protect against None/invalid feature count
        if feature_count is None or feature_count <= 0:
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
        enable_auto_strategy: Optional[bool] = None,
        enable_auto_simplify_buffer: Optional[bool] = None,
        enable_auto_simplify_after_buffer: Optional[bool] = None
    ):
        """
        Initialize the auto-optimizer.
        
        Args:
            enable_auto_centroid: Auto-enable centroid for distant layers (None = use config)
            enable_auto_simplify: Auto-enable geometry simplification (None = use config)
            enable_auto_strategy: Auto-select optimal filtering strategy (None = use config)
            enable_auto_simplify_buffer: Auto-simplify geometry before buffer (None = use config)
            enable_auto_simplify_after_buffer: Auto-simplify result after buffer (None = use config)
        """
        # Load configuration
        config = get_auto_optimization_config()
        
        # Check if auto-optimization is globally enabled
        self.globally_enabled = config.get('enabled', True)
        
        # Use provided values or fall back to config
        self.enable_auto_centroid = enable_auto_centroid if enable_auto_centroid is not None else config.get('auto_centroid_for_distant', True)
        self.enable_auto_simplify = enable_auto_simplify if enable_auto_simplify is not None else config.get('auto_simplify_geometry', False)
        self.enable_auto_strategy = enable_auto_strategy if enable_auto_strategy is not None else config.get('auto_strategy_selection', True)
        self.enable_auto_simplify_buffer = enable_auto_simplify_buffer if enable_auto_simplify_buffer is not None else config.get('auto_simplify_before_buffer', True)
        self.enable_auto_simplify_after_buffer = enable_auto_simplify_after_buffer if enable_auto_simplify_after_buffer is not None else config.get('auto_simplify_after_buffer', True)
        self.enable_reduce_buffer_segments = config.get('auto_reduce_buffer_segments', True)
        
        # Load thresholds from config
        self.centroid_threshold_distant = config.get('centroid_threshold_distant', CENTROID_AUTO_THRESHOLD_DISTANT)
        self.centroid_threshold_local = config.get('centroid_threshold_local', CENTROID_AUTO_THRESHOLD_LOCAL)
        self.buffer_simplify_vertex_threshold = config.get('buffer_simplify_vertex_threshold', BUFFER_SIMPLIFY_VERTEX_THRESHOLD)
        self.buffer_simplify_feature_threshold = config.get('buffer_simplify_feature_threshold', BUFFER_SIMPLIFY_FEATURE_THRESHOLD)
        self.buffer_simplify_default_tolerance = config.get('buffer_simplify_default_tolerance', BUFFER_SIMPLIFY_DEFAULT_TOLERANCE)
        self.buffer_segments_threshold = config.get('buffer_segments_optimization_threshold', BUFFER_SEGMENTS_OPTIMIZATION_THRESHOLD)
        self.buffer_segments_reduced = config.get('buffer_segments_reduced_value', BUFFER_SEGMENTS_REDUCED_VALUE)
        self.show_hints = config.get('show_optimization_hints', True)
    
    def create_optimization_plan(
        self,
        target_layer: QgsVectorLayer,
        source_layer: Optional[QgsVectorLayer] = None,
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
            source_layer: Source/selection layer (if any)
            source_wkt_length: Length of source WKT string
            predicates: Spatial predicates being used
            attribute_filter: Attribute filter expression
            user_requested_centroids: Explicit user choice (None = auto)
            has_buffer: Whether buffer is being applied
            buffer_value: Buffer distance value (positive or negative)
            
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
        
        # 2b. BUFFER SIMPLIFICATION OPTIMIZATION (auto-applicable)
        buffer_simplify_rec = self._evaluate_buffer_simplify_optimization(
            target_analysis, source_analysis, has_buffer, buffer_value
        )
        if buffer_simplify_rec:
            recommendations.append(buffer_simplify_rec)
        
        # 2c. REDUCE BUFFER SEGMENTS OPTIMIZATION
        buffer_segments_rec = self._evaluate_reduce_buffer_segments_optimization(
            target_analysis, has_buffer
        )
        if buffer_segments_rec:
            recommendations.append(buffer_segments_rec)
        
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
            any(r.optimization_type == OptimizationType.USE_CENTROID_DISTANT and r.auto_applicable 
                for r in recommendations)
        )
        
        # Get simplify tolerance - prioritize buffer simplification if applicable
        final_simplify = None
        for rec in recommendations:
            if rec.optimization_type == OptimizationType.SIMPLIFY_BEFORE_BUFFER and rec.auto_applicable:
                final_simplify = rec.parameters.get('tolerance')
                break
        if final_simplify is None:
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
            if rec.auto_applicable or rec.optimization_type == OptimizationType.USE_CENTROID_DISTANT:
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
        layer_analysis: 'LayerAnalysis',
        user_centroid_enabled: Optional[bool] = None,
        has_buffer: bool = False,
        has_buffer_type: bool = False,
        is_source_layer: bool = True
    ) -> List[OptimizationRecommendation]:
        """
        Get optimization recommendations for a single layer.
        
        This is a simplified interface for getting recommendations based solely
        on a layer analysis, without requiring source layer or filter context.
        
        Args:
            layer_analysis: Analysis of the layer to optimize
            user_centroid_enabled: True if user has already enabled centroid optimization
                                   (via checkbox or previous choice). If True, centroid
                                   recommendation will be skipped.
            has_buffer: True if buffer is being applied
            has_buffer_type: True if buffer type UI is already enabled
            is_source_layer: True if this is the source layer for filtering (default True)
            
        Returns:
            List of OptimizationRecommendation objects
        """
        if not layer_analysis:
            return []
        
        recommendations = []
        
        # 1. CENTROID OPTIMIZATION - check if layer would benefit from centroid usage
        # v2.8.9: NEVER recommend centroids for source layer - it doesn't make sense
        # The source layer defines the filtering zone, using centroids would lose spatial information
        # Centroid optimization only makes sense for distant/target layers being filtered
        if is_source_layer:
            # Skip centroid recommendation entirely for source layer
            logger.debug(f"Skipping centroid recommendation for {layer_analysis.layer_name}: "
                        f"source layer - centroid optimization not applicable")
        elif user_centroid_enabled is True:
            # User already has centroid enabled - no need to recommend
            logger.debug(f"Skipping centroid recommendation for {layer_analysis.layer_name}: already enabled by user")
        else:
            # Only evaluate centroid for non-source layers (distant/target layers)
            centroid_rec = self._evaluate_centroid_optimization(
                target=layer_analysis,
                source=None,
                user_requested=None  # None = auto-detect based on layer characteristics
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
        
        # 4. ENABLE BUFFER TYPE OPTIMIZATION - recommend enabling buffer type with segments=1
        # when buffer is active but buffer type UI is disabled
        buffer_type_rec = self._evaluate_enable_buffer_type_optimization(
            target=layer_analysis,
            has_buffer=has_buffer,
            has_buffer_type=has_buffer_type
        )
        if buffer_type_rec:
            recommendations.append(buffer_type_rec)
        
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
                optimization_type=OptimizationType.USE_CENTROID_DISTANT,
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
        
        # v2.9.2: Determine best centroid mode based on geometry type
        # For polygons, use point_on_surface (guaranteed inside)
        # For lines, use centroid (faster)
        centroid_mode = CENTROID_MODE_DEFAULT
        if target.geometry_type == GEOMETRY_TYPE_POLYGON:
            centroid_mode = 'point_on_surface'
            reason_parts.append("using ST_PointOnSurface (guaranteed inside polygon)")
        elif target.geometry_type == GEOMETRY_TYPE_LINE:
            centroid_mode = 'centroid'
            reason_parts.append("using ST_Centroid (optimal for lines)")
        
        return OptimizationRecommendation(
            optimization_type=OptimizationType.USE_CENTROID_DISTANT,
            priority=1,
            estimated_speedup=speedup,
            reason=f"Centroid recommended: {'; '.join(reason_parts)}",
            auto_applicable=True,
            requires_user_consent=False,
            parameters={
                "auto_detected": True,
                "centroid_mode": centroid_mode  # v2.9.2: Include recommended mode
            }
        )
    
    def evaluate_distant_layers_centroid(
        self,
        distant_layers_analyses: List['LayerAnalysis'],
        user_already_enabled: bool = False
    ) -> Optional[OptimizationRecommendation]:
        """
        Evaluate if centroid optimization should be recommended for distant/filtering layers.
        
        v2.8.7: New method to specifically evaluate distant layers used in spatial filtering
        operations. When filtering with Intersect/Contains/etc, the distant layers' geometries
        are used in spatial predicates. Using centroids can significantly speed up operations.
        
        Args:
            distant_layers_analyses: List of LayerAnalysis for distant layers
            user_already_enabled: True if user has already enabled distant centroid checkbox
            
        Returns:
            OptimizationRecommendation if centroid should be recommended, None otherwise
        """
        # Skip if user already enabled centroids for distant layers
        if user_already_enabled:
            return None
        
        # Skip if auto-optimization is disabled
        if not self.globally_enabled or not self.enable_auto_centroid:
            return None
        
        if not distant_layers_analyses:
            return None
        
        # Analyze distant layers for optimization opportunity
        total_features = 0
        has_distant_layer = False
        has_complex_geometries = False
        max_speedup = 1.0
        reason_parts = []
        
        for analysis in distant_layers_analyses:
            total_features += analysis.feature_count
            
            # Case 1: Remote/distant layer
            if analysis.is_distant:
                has_distant_layer = True
                if analysis.feature_count > self.centroid_threshold_distant:
                    reason_parts.append(
                        f"distant layer '{analysis.layer_name}' with {analysis.feature_count:,} features"
                    )
                    max_speedup = max(max_speedup, 5.0)
            
            # Case 2: Complex geometries (polygons)
            if analysis.geometry_type == GEOMETRY_TYPE_POLYGON:
                has_complex_geometries = True
                if analysis.feature_count > 1000:  # Lower threshold for polygon layers
                    reason_parts.append(
                        f"polygon layer '{analysis.layer_name}' ({analysis.feature_count:,} features)"
                    )
                    max_speedup = max(max_speedup, 3.0)
            
            # Case 3: Large local layer
            if analysis.feature_count > self.centroid_threshold_local:
                reason_parts.append(
                    f"large layer '{analysis.layer_name}' ({analysis.feature_count:,} features)"
                )
                max_speedup = max(max_speedup, 2.0)
        
        # Recommend if any significant optimization opportunity found
        if not reason_parts:
            return None
        
        return OptimizationRecommendation(
            optimization_type=OptimizationType.USE_CENTROID_DISTANT,
            priority=1,
            estimated_speedup=max_speedup,
            reason=f"Centroid for distant layers: {'; '.join(reason_parts[:2])}",  # Limit to 2 reasons
            auto_applicable=True,
            requires_user_consent=False,
            parameters={
                "auto_detected": True,
                "total_distant_features": total_features,
                "layer_count": len(distant_layers_analyses)
            }
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
    
    def _evaluate_buffer_simplify_optimization(
        self,
        target: LayerAnalysis,
        source: Optional[LayerAnalysis],
        has_buffer: bool,
        buffer_value: float
    ) -> Optional[OptimizationRecommendation]:
        """
        Evaluate if geometry simplification before buffer should be recommended.
        
        This optimization simplifies geometries BEFORE applying buffer to improve
        performance. Works for both positive and negative buffers.
        
        Args:
            target: Target layer analysis
            source: Source layer analysis (if any)
            has_buffer: Whether buffer is being applied
            buffer_value: Buffer distance (positive or negative)
            
        Returns:
            OptimizationRecommendation if simplification is recommended
        """
        if not self.enable_auto_simplify_buffer:
            return None
        
        if not has_buffer:
            return None
        
        # Determine if simplification is beneficial based on geometry complexity
        # For buffers, we check both source and target layers
        layer_to_simplify = None
        avg_vertices = 0
        feature_count = 0
        
        # Source layer is typically the one being buffered
        if source:
            avg_vertices = source.avg_vertices_per_feature
            feature_count = source.feature_count
            layer_to_simplify = "source"
        else:
            avg_vertices = target.avg_vertices_per_feature
            feature_count = target.feature_count
            layer_to_simplify = "target"
        
        # Check thresholds for buffer simplification
        should_simplify = (
            avg_vertices > self.buffer_simplify_vertex_threshold or
            feature_count > self.buffer_simplify_feature_threshold
        )
        
        if not should_simplify:
            return None
        
        # Calculate adaptive tolerance based on buffer size
        # For small buffers, use smaller tolerance to preserve detail
        # For large buffers, we can use larger tolerance
        abs_buffer = abs(buffer_value)
        if abs_buffer > 0:
            # Tolerance = 10% of buffer size, clamped to reasonable range
            adaptive_tolerance = max(
                0.1,  # minimum 0.1 meters
                min(abs_buffer * 0.1, self.buffer_simplify_default_tolerance)
            )
        else:
            adaptive_tolerance = self.buffer_simplify_default_tolerance
        
        # Higher speedup for negative buffers (more complex operation)
        is_negative_buffer = buffer_value < 0
        estimated_speedup = 2.5 if is_negative_buffer else 2.0
        
        buffer_type = "negative" if is_negative_buffer else "positive"
        
        return OptimizationRecommendation(
            optimization_type=OptimizationType.SIMPLIFY_BEFORE_BUFFER,
            priority=1,  # High priority - buffer operations are expensive
            estimated_speedup=estimated_speedup,
            reason=f"Simplify geometry before {buffer_type} buffer ({avg_vertices:.0f} avg vertices, {feature_count:,} features)",
            auto_applicable=True,  # Auto-apply without consent (safe optimization)
            requires_user_consent=False,
            parameters={
                "tolerance": adaptive_tolerance,
                "target": layer_to_simplify,
                "buffer_value": buffer_value
            }
        )
    
    def _evaluate_reduce_buffer_segments_optimization(
        self,
        target: LayerAnalysis,
        has_buffer: bool
    ) -> Optional[OptimizationRecommendation]:
        """
        Evaluate if reducing buffer segments should be recommended.
        
        Reducing buffer arc segments improves performance for large datasets
        by creating simpler buffer geometries with fewer vertices.
        
        Args:
            target: Target layer analysis
            has_buffer: Whether buffer is being applied
            
        Returns:
            OptimizationRecommendation if segment reduction is recommended
        """
        if not self.enable_reduce_buffer_segments:
            return None
        
        if not has_buffer:
            return None
        
        # CRITICAL FIX v3.0.10: Protect against None/invalid feature count
        # This fixes TypeError '<' not supported between 'int' and 'NoneType'
        if target.feature_count is None or target.feature_count < 0:
            return None
        
        # Check if feature count exceeds threshold for segment reduction
        if target.feature_count < self.buffer_segments_threshold:
            return None
        
        # Calculate speedup based on feature count
        # More features = more benefit from reduced segments
        if target.feature_count > 100000:
            estimated_speedup = 1.8
        elif target.feature_count > 50000:
            estimated_speedup = 1.5
        else:
            estimated_speedup = 1.3
        
        return OptimizationRecommendation(
            optimization_type=OptimizationType.REDUCE_BUFFER_SEGMENTS,
            priority=2,  # Medium priority
            estimated_speedup=estimated_speedup,
            reason=f"Reduce buffer segments ({target.feature_count:,} features - use {self.buffer_segments_reduced} segments instead of 5)",
            auto_applicable=True,
            requires_user_consent=False,
            parameters={
                "segments": self.buffer_segments_reduced,
                "original_segments": BUFFER_SEGMENTS_DEFAULT
            }
        )
    
    def _evaluate_enable_buffer_type_optimization(
        self,
        target: LayerAnalysis,
        has_buffer: bool,
        has_buffer_type: bool
    ) -> Optional[OptimizationRecommendation]:
        """
        Evaluate if enabling buffer type with reduced segments should be recommended.
        
        When the buffer type UI is disabled but buffer is being used, recommend
        enabling buffer type with segments=1 for significant performance improvement.
        Using 1 segment (instead of default 5) creates simpler buffer geometries
        with fewer vertices, dramatically improving performance.
        
        Args:
            target: Target layer analysis
            has_buffer: Whether buffer is being applied
            has_buffer_type: Whether buffer type UI is already enabled
            
        Returns:
            OptimizationRecommendation if buffer type activation is recommended
        """
        # Only recommend if buffer is used but buffer type UI is disabled
        if not has_buffer:
            return None
        
        if has_buffer_type:
            # Buffer type already enabled, no need to recommend
            return None
        
        # Calculate speedup based on feature count
        # Reducing from 5 segments to 1 provides significant speedup
        if target.feature_count > 100000:
            estimated_speedup = 2.5
        elif target.feature_count > 50000:
            estimated_speedup = 2.0
        elif target.feature_count > 10000:
            estimated_speedup = 1.8
        else:
            estimated_speedup = 1.5
        
        return OptimizationRecommendation(
            optimization_type=OptimizationType.ENABLE_BUFFER_TYPE,
            priority=2,  # Medium priority, same as reduce_buffer_segments
            estimated_speedup=estimated_speedup,
            reason=f"Enable buffer type with 1 segment ({target.feature_count:,} features - Flat type with 1 segment instead of Round with 5)",
            auto_applicable=True,
            requires_user_consent=False,
            parameters={
                "buffer_type": "Flat",
                "segments": 1,
                "original_segments": BUFFER_SEGMENTS_DEFAULT
            }
        )
    
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
        
        # v2.7.3: Progressive chunks is now DEFAULT behavior for all datasets
        # No longer proposed as an optimization since it's always applied
        # Very large dataset: was progressive chunks, now just skip this optimization
        # The chunking is handled automatically in apply_filter()
        pass  # Progressive chunking now default
        
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
    user_requested_centroids: Optional[bool] = None,
    has_buffer: bool = False,
    buffer_value: float = 0.0
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
        has_buffer: Whether buffer is being applied
        buffer_value: Buffer distance (positive or negative)
        
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
        user_requested_centroids=user_requested_centroids,
        has_buffer=has_buffer,
        buffer_value=buffer_value
    )


# =============================================================================
# Enhanced Optimizer (v2.8.0)
# =============================================================================

class EnhancedAutoOptimizer(AutoOptimizer):
    """
    Enhanced auto-optimizer with metrics collection, pattern detection,
    adaptive thresholds, and parallel processing support.
    
    v2.8.0 Features:
    - Performance metrics collection and reporting
    - Query pattern detection for recurring optimizations
    - Adaptive threshold tuning based on observed performance
    - Parallel processing for large spatial operations
    - LRU caching with automatic invalidation
    - Selectivity histograms for better estimation
    
    Usage:
        optimizer = get_enhanced_optimizer()
        
        # Start optimization session
        session_id = optimizer.start_optimization_session(layer)
        
        # Get optimized plan
        plan = optimizer.create_optimization_plan(layer, ...)
        
        # Execute with parallel processing if beneficial
        if optimizer.should_use_parallel(layer):
            results = optimizer.execute_parallel_spatial_filter(...)
        
        # End session and get metrics
        summary = optimizer.end_optimization_session(session_id, execution_time_ms)
        
        # Get optimization statistics
        stats = optimizer.get_statistics()
    """
    
    def __init__(
        self,
        enable_auto_centroid: Optional[bool] = None,
        enable_auto_simplify: Optional[bool] = None,
        enable_auto_strategy: Optional[bool] = None,
        enable_metrics: bool = True,
        enable_parallel: bool = True,
        enable_adaptive_thresholds: bool = True
    ):
        """
        Initialize enhanced optimizer.
        
        Args:
            enable_auto_centroid: Enable centroid optimization (None = use config)
            enable_auto_simplify: Enable geometry simplification (None = use config)
            enable_auto_strategy: Enable strategy selection (None = use config)
            enable_metrics: Enable metrics collection
            enable_parallel: Enable parallel processing
            enable_adaptive_thresholds: Enable adaptive threshold adjustment
        """
        super().__init__(
            enable_auto_centroid=enable_auto_centroid,
            enable_auto_simplify=enable_auto_simplify,
            enable_auto_strategy=enable_auto_strategy
        )
        
        self.enable_metrics = enable_metrics and METRICS_AVAILABLE
        self.enable_parallel = enable_parallel and PARALLEL_AVAILABLE
        self.enable_adaptive_thresholds = enable_adaptive_thresholds
        
        # Initialize components
        self._metrics = None
        self._parallel_processor = None
        self._pattern_detector = None
        
        if self.enable_metrics and get_metrics_collector:
            self._metrics = get_metrics_collector()
            if self.enable_adaptive_thresholds:
                # Get adaptive thresholds
                self._update_thresholds_from_metrics()
        
        if self.enable_parallel and get_parallel_processor:
            self._parallel_processor = get_parallel_processor()
    
    def _update_thresholds_from_metrics(self) -> None:
        """Update thresholds from adaptive threshold manager."""
        if not self._metrics:
            return
        
        thresholds = self._metrics.threshold_manager.get_all_thresholds()
        
        # Apply adaptive thresholds
        if 'centroid_threshold_distant' in thresholds:
            self.centroid_threshold_distant = int(thresholds['centroid_threshold_distant'])
        if 'centroid_threshold_local' in thresholds:
            self.centroid_threshold_local = int(thresholds['centroid_threshold_local'])
    
    def start_optimization_session(
        self,
        layer: QgsVectorLayer
    ) -> Optional[str]:
        """
        Start an optimization session for metrics collection.
        
        Args:
            layer: Layer being optimized
            
        Returns:
            Session ID or None if metrics disabled
        """
        if not self._metrics:
            return None
        
        return self._metrics.start_session(
            layer_id=layer.id(),
            layer_name=layer.name(),
            feature_count=layer.featureCount()
        )
    
    def end_optimization_session(
        self,
        session_id: str,
        execution_time_ms: float,
        baseline_estimate_ms: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        End optimization session and get summary.
        
        Args:
            session_id: Session identifier
            execution_time_ms: Actual execution time
            baseline_estimate_ms: Estimated time without optimization
            
        Returns:
            Session summary dictionary
        """
        if not self._metrics or not session_id:
            return None
        
        return self._metrics.end_session(
            session_id=session_id,
            execution_time_ms=execution_time_ms,
            baseline_estimate_ms=baseline_estimate_ms
        )
    
    def create_optimization_plan(
        self,
        target_layer: QgsVectorLayer,
        source_layer: Optional[QgsVectorLayer] = None,
        source_wkt_length: int = 0,
        predicates: Optional[Dict] = None,
        attribute_filter: Optional[str] = None,
        user_requested_centroids: Optional[bool] = None,
        session_id: Optional[str] = None
    ) -> OptimizationPlan:
        """
        Create optimization plan with enhanced features.
        
        Extends base functionality with:
        - Pattern detection for recurring queries
        - Cached analysis results
        - Metrics recording
        - Parallel processing recommendations
        """
        analysis_start = time.time()
        
        # Check for cached/pattern-based recommendation
        if self._metrics:
            predicate_list = list(predicates.keys()) if predicates else []
            
            # Check pattern detector for known good strategy
            recommended = self._metrics.pattern_detector.get_recommended_strategy(
                layer_id=target_layer.id(),
                attribute_filter=attribute_filter,
                spatial_predicates=predicate_list
            )
            
            if recommended:
                strategy, confidence = recommended
                if confidence > 0.7:
                    logger.debug(
                        f"Using pattern-based strategy '{strategy}' "
                        f"with {confidence:.0%} confidence"
                    )
        
        # Get base plan
        plan = super().create_optimization_plan(
            target_layer=target_layer,
            source_layer=source_layer,
            source_wkt_length=source_wkt_length,
            predicates=predicates,
            attribute_filter=attribute_filter,
            user_requested_centroids=user_requested_centroids
        )
        
        # Add parallel processing recommendation if beneficial
        if self.enable_parallel and plan.layer_analysis.feature_count > 0:
            should_parallel = should_use_parallel_processing(
                feature_count=plan.layer_analysis.feature_count,
                has_spatial_filter=bool(predicates),
                geometry_complexity=plan.layer_analysis.estimated_complexity
            )
            
            if should_parallel:
                plan.recommendations.append(
                    OptimizationRecommendation(
                        optimization_type=OptimizationType.MEMORY_OPTIMIZATION,
                        priority=10,  # Low priority - applied in addition to others
                        estimated_speedup=min(2.0, PARALLEL_AVAILABLE and 1.5 or 1.0),
                        reason=f"Large dataset ({plan.layer_analysis.feature_count:,} features) - parallel processing available",
                        auto_applicable=True,
                        parameters={"parallel": True, "workers": 4}
                    )
                )
        
        # Record metrics
        if self._metrics and session_id:
            analysis_time = (time.time() - analysis_start) * 1000
            self._metrics.record_analysis_time(session_id, analysis_time)
            self._metrics.record_strategy(
                session_id, 
                plan.final_strategy,
                plan.estimated_total_speedup
            )
        
        return plan
    
    def should_use_parallel(
        self,
        layer: QgsVectorLayer,
        has_spatial_filter: bool = True
    ) -> bool:
        """
        Check if parallel processing should be used for this layer.
        
        Args:
            layer: Target layer
            has_spatial_filter: Whether spatial filtering is needed
            
        Returns:
            True if parallel processing is recommended
        """
        if not self.enable_parallel:
            return False
        
        analysis = LayerAnalyzer.analyze_layer(layer)
        
        return should_use_parallel_processing(
            feature_count=analysis.feature_count,
            has_spatial_filter=has_spatial_filter,
            geometry_complexity=analysis.estimated_complexity
        )
    
    def execute_parallel_spatial_filter(
        self,
        layer: QgsVectorLayer,
        test_geometry: 'QgsGeometry',
        predicate: str = 'intersects',
        pre_filter_fids: Optional[Set[int]] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Tuple[Set[int], Dict[str, Any]]:
        """
        Execute spatial filter using parallel processing.
        
        Args:
            layer: Target layer
            test_geometry: Geometry to test against
            predicate: Spatial predicate name
            pre_filter_fids: Optional pre-filtered FIDs
            progress_callback: Progress callback
            
        Returns:
            Tuple of (matching_fids, stats_dict)
        """
        if not self._parallel_processor:
            raise RuntimeError("Parallel processing not available")
        
        matching, stats = self._parallel_processor.process_spatial_filter_parallel(
            layer=layer,
            test_geometry=test_geometry,
            predicate=predicate,
            pre_filter_fids=pre_filter_fids,
            progress_callback=progress_callback
        )
        
        return matching, stats.to_dict()
    
    def record_query_pattern(
        self,
        layer_id: str,
        attribute_filter: Optional[str],
        spatial_predicates: Optional[List[str]],
        execution_time_ms: float,
        strategy_used: str
    ) -> None:
        """
        Record query pattern for future optimization.
        
        Args:
            layer_id: Layer identifier
            attribute_filter: Attribute filter used
            spatial_predicates: Spatial predicates used
            execution_time_ms: Execution time
            strategy_used: Strategy that was used
        """
        if not self._metrics:
            return
        
        self._metrics.pattern_detector.record_query(
            layer_id=layer_id,
            attribute_filter=attribute_filter,
            spatial_predicates=spatial_predicates,
            execution_time_ms=execution_time_ms,
            strategy_used=strategy_used
        )
    
    def build_selectivity_histogram(
        self,
        layer: QgsVectorLayer,
        field_name: str,
        sample_size: int = 500
    ) -> None:
        """
        Build selectivity histogram for a field.
        
        Args:
            layer: Layer to sample
            field_name: Field to analyze
            sample_size: Number of features to sample
        """
        if not self._metrics:
            return
        
        from qgis.core import QgsFeatureRequest
        
        field_idx = layer.fields().indexOf(field_name)
        if field_idx < 0:
            return
        
        # Sample values
        request = QgsFeatureRequest()
        request.setLimit(sample_size)
        request.setFlags(QgsFeatureRequest.NoGeometry)
        request.setSubsetOfAttributes([field_idx])
        
        values = []
        for feat in layer.getFeatures(request):
            val = feat.attribute(field_idx)
            if val is not None:
                values.append(val)
        
        if values:
            self._metrics.histograms.build_histogram(
                layer_id=layer.id(),
                field_name=field_name,
                values=values
            )
    
    def estimate_selectivity(
        self,
        layer: QgsVectorLayer,
        field_name: str,
        operator: str,
        value: Any
    ) -> float:
        """
        Estimate selectivity for a condition using histograms.
        
        Args:
            layer: Layer to query
            field_name: Field name
            operator: Comparison operator
            value: Comparison value
            
        Returns:
            Estimated selectivity (0.0 to 1.0)
        """
        if not self._metrics:
            return 0.5
        
        return self._metrics.histograms.estimate_selectivity(
            layer_id=layer.id(),
            field_name=field_name,
            operator=operator,
            value=value
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get optimization statistics.
        
        Returns:
            Dictionary with optimization statistics
        """
        if not self._metrics:
            return {
                'metrics_available': False,
                'parallel_available': self.enable_parallel,
            }
        
        stats = self._metrics.get_statistics()
        stats['metrics_available'] = True
        stats['parallel_available'] = self.enable_parallel
        stats['adaptive_thresholds_enabled'] = self.enable_adaptive_thresholds
        
        return stats
    
    def get_recent_sessions(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent optimization session summaries."""
        if not self._metrics:
            return []
        return self._metrics.get_recent_sessions(count)
    
    def invalidate_layer_cache(self, layer_id: str) -> None:
        """
        Invalidate cached data for a layer.
        
        Call this when a layer's data changes.
        
        Args:
            layer_id: Layer identifier
        """
        # Clear layer analyzer cache
        LayerAnalyzer.clear_cache(layer_id)
        
        # Clear metrics cache
        if self._metrics:
            self._metrics.cache.invalidate_pattern(
                lambda k: k.startswith(layer_id)
            )
    
    def reset_adaptive_thresholds(self) -> None:
        """Reset adaptive thresholds to defaults."""
        if self._metrics:
            self._metrics.threshold_manager.reset_to_defaults()


def get_enhanced_optimizer(
    enable_metrics: bool = True,
    enable_parallel: bool = True,
    enable_adaptive_thresholds: bool = True
) -> EnhancedAutoOptimizer:
    """
    Factory function to get an enhanced auto-optimizer instance.
    
    Args:
        enable_metrics: Enable metrics collection
        enable_parallel: Enable parallel processing
        enable_adaptive_thresholds: Enable adaptive threshold adjustment
        
    Returns:
        Configured EnhancedAutoOptimizer instance
    """
    return EnhancedAutoOptimizer(
        enable_metrics=enable_metrics,
        enable_parallel=enable_parallel,
        enable_adaptive_thresholds=enable_adaptive_thresholds
    )


# =============================================================================
# Convenience Functions
# =============================================================================

def get_optimization_statistics() -> Dict[str, Any]:
    """
    Get global optimization statistics.
    
    Returns:
        Dictionary with optimization statistics
    """
    if METRICS_AVAILABLE and get_metrics_collector:
        return get_metrics_collector().get_statistics()
    return {'metrics_available': False}


def clear_optimization_cache() -> None:
    """Clear all optimization caches."""
    LayerAnalyzer.clear_cache()
    
    if METRICS_AVAILABLE and get_metrics_collector:
        collector = get_metrics_collector()
        collector.cache.clear()
        collector.pattern_detector.clear_old_patterns(0)  # Clear all

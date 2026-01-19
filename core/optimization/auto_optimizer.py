# -*- coding: utf-8 -*-
"""
FilterMate Auto-Optimizer Module

Intelligent heuristics-based optimizer that automatically recommends and applies
performance optimizations based on:
- Backend type (local vs distant/remote)
- Feature count
- Geometry complexity
- Spatial predicate type

Migrated from: before_migration/modules/backends/auto_optimizer.py (1785 lines)
Target: core/optimization/auto_optimizer.py

v4.1.0 - Hexagonal Architecture Migration (January 2026)

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

5. BACKEND-SPECIFIC OPTIMIZATIONS:
   - PostgreSQL: Materialized views, R-tree indexes
   - Spatialite: R-tree temp tables
   - OGR/Memory: Progressive chunking
"""

import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass, field

from qgis.core import (
    QgsVectorLayer,
    QgsWkbTypes,
)

from ...infrastructure.constants import (
    PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR, PROVIDER_MEMORY,
    REMOTE_PROVIDERS, PROVIDER_TYPE_MAPPING,
    PERFORMANCE_THRESHOLD_SMALL, PERFORMANCE_THRESHOLD_MEDIUM,
    PERFORMANCE_THRESHOLD_LARGE, PERFORMANCE_THRESHOLD_XLARGE,
    GEOMETRY_TYPE_POINT, GEOMETRY_TYPE_LINE, GEOMETRY_TYPE_POLYGON,
)

logger = logging.getLogger('FilterMate.Core.Optimization.AutoOptimizer')

# Flag to indicate this module is available and functional
AUTO_OPTIMIZER_AVAILABLE = True

# =============================================================================
# Thresholds and Constants
# =============================================================================

# Feature count thresholds for centroid optimization
CENTROID_AUTO_THRESHOLD_DISTANT = 5000      # Auto-enable for distant layers > 5k features
CENTROID_AUTO_THRESHOLD_LOCAL = 50000       # Auto-enable for local layers > 50k features

# Centroid mode: 'point_on_surface' guaranteed inside polygon (recommended)
CENTROID_MODE_DEFAULT = 'point_on_surface'

# Geometry simplification thresholds
SIMPLIFY_AUTO_THRESHOLD = 100000            # Auto-simplify for layers > 100k features
SIMPLIFY_TOLERANCE_FACTOR = 0.001           # Tolerance as fraction of extent diagonal

# Buffer simplification thresholds
BUFFER_SIMPLIFY_VERTEX_THRESHOLD = 50       # Simplify before buffer if avg vertices > this
BUFFER_SIMPLIFY_FEATURE_THRESHOLD = 1000    # Simplify before buffer if feature count > this
BUFFER_SIMPLIFY_DEFAULT_TOLERANCE = 1.0     # Default tolerance in meters

# Buffer segments optimization thresholds
BUFFER_SEGMENTS_OPTIMIZATION_THRESHOLD = 10000  # Reduce segments if feature count > this
BUFFER_SEGMENTS_REDUCED_VALUE = 3               # Reduced number of segments
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


# =============================================================================
# Configuration Loading
# =============================================================================

def get_auto_optimization_config() -> Dict[str, Any]:
    """
    Load auto-optimization configuration from ENV_VARS.
    
    Returns:
        Dictionary with configuration values
    """
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
# Layer Analyzer
# =============================================================================

class LayerAnalyzer:
    """
    Analyzes layers to determine optimal filtering strategies.
    """
    
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
        
        # Map to FilterMate provider type
        filtermate_provider = PROVIDER_TYPE_MAPPING.get(provider_type, PROVIDER_OGR)
        
        # Determine location type
        location_type = cls._determine_location_type(layer, provider_type)
        
        # Get feature count safely
        feature_count = layer.featureCount()
        if feature_count < 0:
            feature_count = 0
        
        # Check spatial index
        has_spatial_index = False
        try:
            has_spatial_index = layer.hasSpatialIndex() if hasattr(layer, 'hasSpatialIndex') else False
        except (RuntimeError, AttributeError):
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
        
        source = layer.source().lower()
        
        # PostgreSQL/PostGIS
        if provider == 'postgres':
            if 'host=' in source:
                import re
                host_match = re.search(r"host='?([^'\s]+)'?", source)
                if host_match:
                    host = host_match.group(1)
                    if host in ('localhost', '127.0.0.1', '::1', 'host.docker.internal'):
                        return LayerLocationType.LOCAL_DATABASE
                    else:
                        return LayerLocationType.REMOTE_DATABASE
            return LayerLocationType.LOCAL_DATABASE
        
        # Spatialite is always local
        if provider == 'spatialite':
            return LayerLocationType.LOCAL_DATABASE
        
        # OGR/memory are local
        if provider in ('ogr', 'memory'):
            return LayerLocationType.LOCAL_FILE
        
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
                    wkt = geom.asWkt()
                    vertex_count = wkt.count(',') + 1
                    total_vertices += vertex_count
                    sampled += 1
            
            if sampled > 0:
                avg_vertices = total_vertices / sampled
                complexity = max(1.0, avg_vertices / 10.0)
                return (avg_vertices, complexity)
            
        except Exception as e:
            logger.debug(f"Complexity estimation failed: {e}")
        
        return (10.0, 1.0)
    
    @classmethod
    def clear_cache(cls, layer_id: Optional[str] = None):
        """Clear analysis cache."""
        if layer_id:
            cls._analysis_cache.pop(layer_id, None)
        else:
            cls._analysis_cache.clear()


# =============================================================================
# Auto Optimizer
# =============================================================================

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
            enable_auto_centroid: Auto-enable centroid for distant layers
            enable_auto_simplify: Auto-enable geometry simplification
            enable_auto_strategy: Auto-select optimal filtering strategy
        """
        config = get_auto_optimization_config()
        
        self.globally_enabled = config.get('enabled', True)
        self.enable_auto_centroid = enable_auto_centroid if enable_auto_centroid is not None else config.get('auto_centroid_for_distant', True)
        self.enable_auto_simplify = enable_auto_simplify if enable_auto_simplify is not None else config.get('auto_simplify_geometry', False)
        self.enable_auto_strategy = enable_auto_strategy if enable_auto_strategy is not None else config.get('auto_strategy_selection', True)
        self.enable_auto_simplify_buffer = config.get('auto_simplify_before_buffer', True)
        self.show_hints = config.get('show_optimization_hints', True)
        
        # Thresholds
        self.centroid_threshold_distant = config.get('centroid_threshold_distant', CENTROID_AUTO_THRESHOLD_DISTANT)
        self.centroid_threshold_local = config.get('centroid_threshold_local', CENTROID_AUTO_THRESHOLD_LOCAL)
    
    def create_optimization_plan(
        self,
        target_layer: QgsVectorLayer,
        source_layer: Optional[QgsVectorLayer] = None,
        source_wkt_length: int = 0,
        user_requested_centroids: Optional[bool] = None,
        has_buffer: bool = False
    ) -> OptimizationPlan:
        """
        Create an optimization plan for a filtering operation.
        
        Args:
            target_layer: Layer being filtered
            source_layer: Source/selection layer (if any)
            source_wkt_length: Length of source WKT string
            user_requested_centroids: Explicit user choice (None = auto)
            has_buffer: Whether buffer is being applied
            
        Returns:
            OptimizationPlan with recommendations
        """
        target_analysis = LayerAnalyzer.analyze_layer(target_layer)
        
        source_analysis = None
        if source_layer:
            source_analysis = LayerAnalyzer.analyze_layer(source_layer)
        
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
        
        # Sort by priority
        recommendations.sort(key=lambda r: r.priority)
        
        # Determine final settings
        final_use_centroids = user_requested_centroids if user_requested_centroids is not None else (
            any(r.optimization_type == OptimizationType.USE_CENTROID_DISTANT and r.auto_applicable 
                for r in recommendations)
        )
        
        final_simplify = None
        for rec in recommendations:
            if rec.optimization_type == OptimizationType.SIMPLIFY_GEOMETRY and rec.auto_applicable:
                final_simplify = rec.parameters.get('tolerance')
                break
        
        # Calculate total estimated speedup
        total_speedup = 1.0
        for rec in recommendations:
            if rec.auto_applicable:
                total_speedup *= rec.estimated_speedup
        
        return OptimizationPlan(
            layer_analysis=target_analysis,
            recommendations=recommendations,
            final_use_centroids=final_use_centroids,
            final_simplify_tolerance=final_simplify,
            final_strategy="default",
            estimated_total_speedup=total_speedup,
            warnings=warnings
        )
    
    def _evaluate_centroid_optimization(
        self,
        target: LayerAnalysis,
        source: Optional[LayerAnalysis],
        user_requested: Optional[bool]
    ) -> Optional[OptimizationRecommendation]:
        """Evaluate if centroid optimization should be recommended."""
        
        if user_requested is False:
            return None
        
        if user_requested is True:
            return OptimizationRecommendation(
                optimization_type=OptimizationType.USE_CENTROID_DISTANT,
                priority=1,
                estimated_speedup=3.0,
                reason="User requested centroid optimization",
                auto_applicable=True,
                parameters={"force": True}
            )
        
        if not self.globally_enabled or not self.enable_auto_centroid:
            return None
        
        should_recommend = False
        reason_parts = []
        speedup = 1.0
        
        # CASE 1: Distant layer with significant data
        if target.is_distant and target.feature_count > self.centroid_threshold_distant:
            should_recommend = True
            reason_parts.append(f"distant layer with {target.feature_count:,} features")
            speedup = 5.0
        
        # CASE 2: Large local layer with complex geometries
        elif target.feature_count > self.centroid_threshold_local and target.is_complex:
            should_recommend = True
            reason_parts.append(
                f"large layer ({target.feature_count:,} features) "
                f"with complex geometries ({target.avg_vertices_per_feature:.0f} avg vertices)"
            )
            speedup = 2.0
        
        # CASE 3: Very large layer
        elif target.feature_count > PERFORMANCE_THRESHOLD_XLARGE:
            should_recommend = True
            reason_parts.append(f"very large layer ({target.feature_count:,} features)")
            speedup = 1.5
        
        if not should_recommend:
            return None
        
        # Determine best centroid mode
        centroid_mode = CENTROID_MODE_DEFAULT
        if target.geometry_type == GEOMETRY_TYPE_POLYGON:
            centroid_mode = 'point_on_surface'
        elif target.geometry_type == GEOMETRY_TYPE_LINE:
            centroid_mode = 'centroid'
        
        return OptimizationRecommendation(
            optimization_type=OptimizationType.USE_CENTROID_DISTANT,
            priority=1,
            estimated_speedup=speedup,
            reason=f"Centroid recommended: {'; '.join(reason_parts)}",
            auto_applicable=True,
            requires_user_consent=False,
            parameters={
                "auto_detected": True,
                "centroid_mode": centroid_mode
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
        
        if source_wkt_length > VERY_LARGE_WKT_THRESHOLD:
            return OptimizationRecommendation(
                optimization_type=OptimizationType.SIMPLIFY_GEOMETRY,
                priority=2,
                estimated_speedup=3.0,
                reason=f"Source geometry is very large ({source_wkt_length:,} chars)",
                auto_applicable=False,
                requires_user_consent=True,
                parameters={
                    "tolerance": SIMPLIFY_TOLERANCE_FACTOR,
                    "target": "source"
                }
            )
        
        if target.avg_vertices_per_feature > VERY_HIGH_COMPLEXITY_VERTICES:
            return OptimizationRecommendation(
                optimization_type=OptimizationType.SIMPLIFY_GEOMETRY,
                priority=3,
                estimated_speedup=2.0,
                reason=f"Target has complex geometries ({target.avg_vertices_per_feature:.0f} avg vertices)",
                auto_applicable=False,
                requires_user_consent=True,
                parameters={
                    "tolerance": SIMPLIFY_TOLERANCE_FACTOR,
                    "target": "target"
                }
            )
        
        return None


# =============================================================================
# Convenience Functions
# =============================================================================

def get_auto_optimizer() -> AutoOptimizer:
    """Get a configured AutoOptimizer instance."""
    return AutoOptimizer()


def analyze_layer(layer: QgsVectorLayer, force_refresh: bool = False) -> LayerAnalysis:
    """Convenience function to analyze a layer."""
    return LayerAnalyzer.analyze_layer(layer, force_refresh)


# Export symbols
__all__ = [
    'AUTO_OPTIMIZER_AVAILABLE',
    'OptimizationType',
    'LayerLocationType',
    'LayerAnalysis',
    'OptimizationRecommendation',
    'OptimizationPlan',
    'LayerAnalyzer',
    'AutoOptimizer',
    'get_auto_optimization_config',
    'get_auto_optimizer',
    'analyze_layer',
    # Constants
    'CENTROID_AUTO_THRESHOLD_DISTANT',
    'CENTROID_AUTO_THRESHOLD_LOCAL',
    'HIGH_COMPLEXITY_VERTICES',
    'VERY_HIGH_COMPLEXITY_VERTICES',
    'LARGE_WKT_THRESHOLD',
    'VERY_LARGE_WKT_THRESHOLD',
]

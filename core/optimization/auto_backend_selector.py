"""
Auto Backend Selector
Chooses optimal backend based on layer characteristics and filter complexity.

Phase 2 (v4.1.0-beta.2): Restoration from v2.5.10 auto_optimizer.py
Architecture: Hexagonal Core - Domain Service

v4.1.5: BackendType removed - use canonical ProviderType from core.domain.filter_expression
"""

from dataclasses import dataclass
from typing import Optional, Dict, List
import logging

from ..domain.filter_expression import ProviderType

logger = logging.getLogger(__name__)

# Alias for backward compatibility
BackendType = ProviderType


@dataclass
class BackendRecommendation:
    """
    Recommendation for backend selection.
    
    Attributes:
        backend_type: Recommended backend ('postgresql', 'spatialite', 'ogr')
        confidence: Confidence score 0.0-1.0
        reason: Human-readable explanation
        estimated_time_ms: Estimated execution time in milliseconds
        fallback_backend: Alternative backend if primary fails
    """
    backend_type: str
    confidence: float
    reason: str
    estimated_time_ms: int
    fallback_backend: Optional[str] = None


class AutoBackendSelector:
    """
    Automatically selects optimal backend for filtering operations.
    
    Decision Factors:
        1. Layer provider type (postgres, spatialite, ogr)
        2. Feature count (small, medium, large datasets)
        3. Filter complexity (simple attribute vs complex spatial)
        4. Available backends (psycopg2 installed?)
        5. Historical performance (optional learning)
    
    Thresholds (based on v2.5.10 benchmarks):
        - PostgreSQL MV: > 10,000 features (optimal)
        - Spatialite: 100-50,000 features (sweet spot)
        - OGR: > 100,000 features (Spatialite becomes slow)
    
    Example:
        >>> selector = AutoBackendSelector()
        >>> recommendation = selector.recommend_backend(
        ...     layer=my_layer,
        ...     filter_params={'expression': '"pop" > 10000'},
        ...     available_backends=['postgresql', 'spatialite', 'ogr']
        ... )
        >>> print(f"Use {recommendation.backend_type}: {recommendation.reason}")
    """
    
    # Performance thresholds (tuned from v2.5.10 production data)
    POSTGRESQL_MV_THRESHOLD = 10000  # Use MV if >= 10k features
    SPATIALITE_OPTIMAL_MIN = 100  # Spatialite optimal >= 100 features
    SPATIALITE_OPTIMAL_MAX = 50000  # Spatialite optimal <= 50k features
    OGR_FALLBACK_THRESHOLD = 100000  # Switch to OGR if > 100k (Spatialite slow)
    
    # Complexity multipliers for estimated time
    SIMPLE_FILTER_MULTIPLIER = 1.0  # Simple attribute filter
    SPATIAL_FILTER_MULTIPLIER = 2.5  # Spatial predicates (ST_Intersects, etc.)
    COMPLEX_FILTER_MULTIPLIER = 5.0  # Complex expressions (multiple AND/OR)
    
    def __init__(self):
        """Initialize selector with empty performance history."""
        # Performance history: backend → {layer_id: [execution_times_ms]}
        self.performance_history: Dict[str, Dict[str, List[int]]] = {
            'postgresql': {},
            'spatialite': {},
            'ogr': {}
        }
    
    def recommend_backend(
        self,
        layer,
        filter_params: dict,
        available_backends: List[str]
    ) -> BackendRecommendation:
        """
        Recommend optimal backend for given layer and filter.
        
        Args:
            layer: QgsVectorLayer instance
            filter_params: Filter parameters dict with keys:
                - expression: QGIS expression string
                - spatial_op: Optional spatial operation name
                - use_spatial_index: Boolean
            available_backends: List of available backends
                Example: ['postgresql', 'spatialite', 'ogr']
        
        Returns:
            BackendRecommendation with backend type and reasoning
        
        Algorithm:
            1. Check layer provider type (native backend preferred)
            2. Evaluate feature count against thresholds
            3. Assess filter complexity (spatial vs attribute)
            4. Consider historical performance (if available)
            5. Select backend with highest confidence score
        """
        feature_count = layer.featureCount()
        provider_type = layer.providerType()
        layer_id = layer.id()
        
        # Extract filter complexity
        expression = filter_params.get('expression', '')
        has_spatial = filter_params.get('spatial_op') or self._has_spatial_predicates(expression)
        complexity_multiplier = self._get_complexity_multiplier(expression, has_spatial)
        
        logger.debug(
            f"AutoBackendSelector: layer={layer.name()}, "
            f"provider={provider_type}, features={feature_count}, "
            f"spatial={has_spatial}, available={available_backends}"
        )
        
        # Strategy 1: PostgreSQL native - always prefer if available and large dataset
        if provider_type == 'postgres' and 'postgresql' in available_backends:
            if feature_count >= self.POSTGRESQL_MV_THRESHOLD:
                estimated_time = self._estimate_postgresql_time(feature_count, complexity_multiplier)
                return BackendRecommendation(
                    backend_type='postgresql',
                    confidence=0.95,
                    reason=f"PostgreSQL MV optimal for {feature_count:,} features (native provider)",
                    estimated_time_ms=estimated_time,
                    fallback_backend='spatialite' if 'spatialite' in available_backends else 'ogr'
                )
            else:
                # Small PostgreSQL layer - direct subset may be faster than MV overhead
                estimated_time = self._estimate_postgresql_time(feature_count, complexity_multiplier)
                return BackendRecommendation(
                    backend_type='postgresql',
                    confidence=0.85,
                    reason=f"PostgreSQL direct subset for {feature_count:,} features (small dataset)",
                    estimated_time_ms=estimated_time,
                    fallback_backend='ogr'
                )
        
        # Strategy 2: Spatialite sweet spot (100-50k features)
        if provider_type == 'spatialite' and 'spatialite' in available_backends:
            if self.SPATIALITE_OPTIMAL_MIN <= feature_count <= self.SPATIALITE_OPTIMAL_MAX:
                estimated_time = self._estimate_spatialite_time(feature_count, complexity_multiplier)
                return BackendRecommendation(
                    backend_type='spatialite',
                    confidence=0.90,
                    reason=f"Spatialite optimal for {feature_count:,} features (sweet spot 100-50k)",
                    estimated_time_ms=estimated_time,
                    fallback_backend='ogr'
                )
            elif feature_count > self.OGR_FALLBACK_THRESHOLD and 'ogr' in available_backends:
                # Very large Spatialite - OGR may be faster
                estimated_time = self._estimate_ogr_time(feature_count, complexity_multiplier)
                return BackendRecommendation(
                    backend_type='ogr',
                    confidence=0.80,
                    reason=f"OGR recommended for large Spatialite ({feature_count:,} features > 100k threshold)",
                    estimated_time_ms=estimated_time,
                    fallback_backend='spatialite'
                )
        
        # Strategy 3: Historical performance (if data available)
        if layer_id in self.performance_history.get('postgresql', {}):
            avg_time_pg = self._get_average_performance('postgresql', layer_id)
            avg_time_sl = self._get_average_performance('spatialite', layer_id)
            
            if avg_time_pg and avg_time_sl and avg_time_pg < avg_time_sl * 0.7:
                # PostgreSQL 30% faster historically
                return BackendRecommendation(
                    backend_type='postgresql',
                    confidence=0.88,
                    reason=f"PostgreSQL historically 30% faster for this layer (avg: {avg_time_pg}ms)",
                    estimated_time_ms=avg_time_pg,
                    fallback_backend='spatialite'
                )
        
        # Strategy 4: OGR universal fallback
        if 'ogr' in available_backends:
            estimated_time = self._estimate_ogr_time(feature_count, complexity_multiplier)
            confidence = 0.75 if provider_type in ['postgres', 'spatialite'] else 0.85
            
            return BackendRecommendation(
                backend_type='ogr',
                confidence=confidence,
                reason=f"OGR universal fallback for {provider_type} ({feature_count:,} features)",
                estimated_time_ms=estimated_time,
                fallback_backend=None  # OGR is last resort
            )
        
        # Fallback: First available backend
        first_backend = available_backends[0] if available_backends else 'ogr'
        return BackendRecommendation(
            backend_type=first_backend,
            confidence=0.50,
            reason=f"Default to first available backend: {first_backend}",
            estimated_time_ms=1000,
            fallback_backend=None
        )
    
    def record_performance(
        self,
        backend_type: str,
        layer_id: str,
        execution_time_ms: int
    ):
        """
        Record actual execution time for learning.
        
        Args:
            backend_type: Backend used ('postgresql', 'spatialite', 'ogr')
            layer_id: QGIS layer ID
            execution_time_ms: Actual execution time in milliseconds
        
        Example:
            >>> selector.record_performance('postgresql', 'layer_123', 450)
        """
        if backend_type not in self.performance_history:
            logger.warning(f"Unknown backend type: {backend_type}")
            return
        
        if layer_id not in self.performance_history[backend_type]:
            self.performance_history[backend_type][layer_id] = []
        
        # Keep last 10 measurements (rolling window)
        history = self.performance_history[backend_type][layer_id]
        history.append(execution_time_ms)
        if len(history) > 10:
            history.pop(0)
        
        logger.debug(
            f"Performance recorded: {backend_type}/{layer_id[:8]}... → {execution_time_ms}ms "
            f"(avg: {sum(history) / len(history):.0f}ms over {len(history)} runs)"
        )
    
    def _has_spatial_predicates(self, expression: str) -> bool:
        """Check if expression contains spatial predicates."""
        spatial_keywords = [
            'ST_Intersects', 'ST_Contains', 'ST_Within', 'ST_Overlaps',
            'ST_Crosses', 'ST_Touches', 'ST_Disjoint', 'ST_Distance',
            'intersects', 'contains', 'within', 'overlaps',  # QGIS functions
            'crosses', 'touches', 'disjoint', 'distance'
        ]
        
        expression_lower = expression.lower()
        return any(keyword.lower() in expression_lower for keyword in spatial_keywords)
    
    def _get_complexity_multiplier(self, expression: str, has_spatial: bool) -> float:
        """Calculate filter complexity multiplier."""
        if has_spatial:
            return self.SPATIAL_FILTER_MULTIPLIER
        
        # Count logical operators for complexity
        and_count = expression.upper().count(' AND ')
        or_count = expression.upper().count(' OR ')
        
        if and_count + or_count > 3:
            return self.COMPLEX_FILTER_MULTIPLIER
        
        return self.SIMPLE_FILTER_MULTIPLIER
    
    def _estimate_postgresql_time(self, feature_count: int, complexity: float) -> int:
        """
        Estimate PostgreSQL execution time in ms.
        
        Based on v2.5.10 benchmarks:
        - Materialized View creation: ~0.01ms per feature
        - Index scan: ~0.005ms per feature
        """
        base_time = int(feature_count * 0.01 * complexity)
        mv_overhead = 50  # MV creation overhead
        return max(base_time + mv_overhead, 10)
    
    def _estimate_spatialite_time(self, feature_count: int, complexity: float) -> int:
        """
        Estimate Spatialite execution time in ms.
        
        Based on v2.5.10 benchmarks:
        - R-tree index scan: ~0.05ms per feature
        - Full table scan: ~0.1ms per feature
        """
        base_time = int(feature_count * 0.05 * complexity)
        return max(base_time, 10)
    
    def _estimate_ogr_time(self, feature_count: int, complexity: float) -> int:
        """
        Estimate OGR execution time in ms.
        
        Based on v2.5.10 benchmarks:
        - setSubsetString: ~0.1ms per feature (no indexes)
        """
        base_time = int(feature_count * 0.1 * complexity)
        return max(base_time, 20)
    
    def _get_average_performance(self, backend_type: str, layer_id: str) -> Optional[int]:
        """Get average performance from history."""
        history = self.performance_history.get(backend_type, {}).get(layer_id)
        if history and len(history) > 0:
            return int(sum(history) / len(history))
        return None


# Singleton instance
_selector_instance = None


def get_auto_backend_selector() -> AutoBackendSelector:
    """
    Get singleton AutoBackendSelector instance.
    
    Returns:
        Shared AutoBackendSelector instance
    
    Example:
        >>> selector = get_auto_backend_selector()
        >>> recommendation = selector.recommend_backend(layer, params, backends)
    """
    global _selector_instance
    if _selector_instance is None:
        _selector_instance = AutoBackendSelector()
        logger.info("AutoBackendSelector singleton created")
    return _selector_instance

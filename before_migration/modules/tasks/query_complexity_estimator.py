# -*- coding: utf-8 -*-
"""
Query Complexity Estimator for FilterMate

Analyzes SQL expressions to estimate query complexity and recommend
optimal execution strategies. Used by the progressive filter system
to choose between direct, materialized, two-phase, or streaming approaches.

Key Factors Analyzed:
- Number and types of spatial predicates
- Presence of buffer operations (expensive)
- Coordinate transformations (moderate cost)
- Subqueries and EXISTS clauses (expensive)
- Geometry validation functions
- Data volume (feature count)

Performance Impact Guide:
- Simple filter (complexity < 20): Direct setSubsetString
- Medium complexity (20-100): Materialized view
- High complexity (100-500): Two-phase filtering
- Very high complexity (> 500): Progressive streaming

Usage:
    from modules.tasks.query_complexity_estimator import (
        QueryComplexityEstimator,
        estimate_query_complexity
    )
    
    estimator = QueryComplexityEstimator()
    score = estimator.estimate(expression, layer_props)
    strategy = estimator.recommend_strategy(score)
"""

import re
import logging
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

from ..logging_config import get_tasks_logger

logger = get_tasks_logger()


class QueryComplexity(Enum):
    """Query complexity levels."""
    TRIVIAL = "trivial"      # Score < 10
    SIMPLE = "simple"        # Score 10-50
    MODERATE = "moderate"    # Score 50-150
    COMPLEX = "complex"      # Score 150-500
    VERY_COMPLEX = "very_complex"  # Score > 500


@dataclass
class ComplexityBreakdown:
    """Detailed breakdown of query complexity factors."""
    # Spatial predicates
    spatial_predicates: int = 0
    spatial_predicate_cost: float = 0.0
    
    # Buffer operations
    buffer_operations: int = 0
    buffer_cost: float = 0.0
    negative_buffer_count: int = 0  # Extra expensive
    
    # Coordinate transformations
    transform_operations: int = 0
    transform_cost: float = 0.0
    
    # Geometry functions
    geometry_functions: int = 0
    geometry_function_cost: float = 0.0
    
    # Subqueries and EXISTS
    subqueries: int = 0
    subquery_cost: float = 0.0
    
    # Data volume factors
    estimated_features: int = 0
    volume_multiplier: float = 1.0
    
    # Total
    total_score: float = 0.0
    complexity_level: QueryComplexity = QueryComplexity.SIMPLE
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for logging/debugging."""
        return {
            'spatial_predicates': self.spatial_predicates,
            'buffer_operations': self.buffer_operations,
            'negative_buffers': self.negative_buffer_count,
            'transforms': self.transform_operations,
            'geometry_functions': self.geometry_functions,
            'subqueries': self.subqueries,
            'estimated_features': self.estimated_features,
            'volume_multiplier': round(self.volume_multiplier, 2),
            'total_score': round(self.total_score, 2),
            'complexity': self.complexity_level.value
        }


@dataclass
class OperationCosts:
    """
    Cost weights for different SQL operations.
    
    These are empirically derived from PostgreSQL query analysis.
    Higher values = more expensive operations.
    """
    # Spatial predicates (PostGIS)
    ST_INTERSECTS: float = 5.0      # Fast with GIST index
    ST_CONTAINS: float = 8.0        # Moderate
    ST_WITHIN: float = 8.0          # Moderate  
    ST_OVERLAPS: float = 10.0       # Expensive
    ST_TOUCHES: float = 6.0         # Fast
    ST_CROSSES: float = 7.0         # Moderate
    ST_DISJOINT: float = 4.0        # Fastest (eliminates most)
    ST_EQUALS: float = 15.0         # Most expensive
    ST_DWITHIN: float = 6.0         # Fast (uses index)
    ST_COVERS: float = 9.0          # Moderate-expensive
    ST_COVEREDBY: float = 9.0       # Moderate-expensive
    
    # Buffer operations
    ST_BUFFER: float = 12.0         # Expensive geometry creation
    ST_BUFFER_NEGATIVE: float = 18.0  # Very expensive (erosion)
    
    # Coordinate transformations
    ST_TRANSFORM: float = 8.0       # Moderate
    ST_SETSRID: float = 1.0         # Cheap (just metadata)
    
    # Geometry validation/repair
    ST_MAKEVALID: float = 5.0       # Moderate
    ST_ISEMPTY: float = 1.0         # Very fast
    ST_ISVALID: float = 3.0         # Fast
    ST_AREA: float = 3.0            # Fast
    ST_LENGTH: float = 3.0          # Fast
    
    # Geometry creation
    ST_GEOMFROMTEXT: float = 2.0    # Fast
    ST_GEOMFROMEWKT: float = 2.0    # Fast
    ST_MAKEENVELOPE: float = 1.0    # Very fast
    ST_UNION: float = 15.0          # Expensive
    ST_COLLECT: float = 8.0         # Moderate
    ST_DIFFERENCE: float = 18.0     # Very expensive
    ST_INTERSECTION: float = 18.0   # Very expensive
    
    # Subqueries
    EXISTS: float = 20.0            # Expensive (depends on subquery)
    IN_SUBQUERY: float = 15.0       # Moderate-expensive
    NOT_EXISTS: float = 25.0        # More expensive than EXISTS
    
    # Aggregations
    ST_EXTENT: float = 5.0          # Fast aggregate
    ST_UNARYUNION: float = 12.0     # Moderate
    
    def get_cost(self, operation: str) -> float:
        """Get cost for an operation name."""
        op_upper = operation.upper().replace('_', '')
        
        # Try exact match first
        for attr in dir(self):
            if attr.upper().replace('_', '') == op_upper:
                return getattr(self, attr)
        
        # Default cost for unknown operations
        return 5.0


class QueryComplexityEstimator:
    """
    Estimates SQL query complexity for optimal strategy selection.
    
    Analyzes query expressions to determine:
    1. Number and type of operations
    2. Expected computational cost
    3. Memory requirements
    4. Recommended execution strategy
    
    Usage:
        estimator = QueryComplexityEstimator()
        
        breakdown = estimator.analyze(expression, feature_count=100000)
        print(f"Complexity: {breakdown.complexity_level.value}")
        print(f"Score: {breakdown.total_score}")
        
        strategy = estimator.recommend_strategy(breakdown.total_score)
    """
    
    # Strategy thresholds
    TRIVIAL_THRESHOLD = 10
    SIMPLE_THRESHOLD = 50
    MODERATE_THRESHOLD = 150
    COMPLEX_THRESHOLD = 500
    
    # Volume scaling factors
    VOLUME_SCALE_BASE = 10000  # Features at which multiplier = 1.0
    VOLUME_SCALE_FACTOR = 0.5  # How much volume affects score
    
    def __init__(self, costs: Optional[OperationCosts] = None):
        """
        Initialize estimator with optional custom costs.
        
        Args:
            costs: Custom operation costs (uses defaults if None)
        """
        self.costs = costs or OperationCosts()
        
        # Compile regex patterns for operation detection
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns for SQL operation detection."""
        
        # Spatial predicates
        self.spatial_pred_pattern = re.compile(
            r'\bST_(Intersects|Contains|Within|Overlaps|Touches|'
            r'Crosses|Disjoint|Equals|DWithin|Covers|CoveredBy)\s*\(',
            re.IGNORECASE
        )
        
        # Buffer operations
        self.buffer_pattern = re.compile(
            r'\bST_Buffer\s*\([^,]+,\s*([-\d.]+)',
            re.IGNORECASE
        )
        
        # Transform operations
        self.transform_pattern = re.compile(
            r'\bST_(Transform|SetSRID)\s*\(',
            re.IGNORECASE
        )
        
        # Geometry validation
        self.validation_pattern = re.compile(
            r'\bST_(MakeValid|IsEmpty|IsValid)\s*\(',
            re.IGNORECASE
        )
        
        # Geometry creation
        self.geom_create_pattern = re.compile(
            r'\bST_(GeomFromText|GeomFromEWKT|MakeEnvelope|'
            r'GeomFromGeoJSON|Point|MakePoint|MakeLine|MakePolygon)\s*\(',
            re.IGNORECASE
        )
        
        # Expensive operations
        self.expensive_pattern = re.compile(
            r'\bST_(Union|Difference|Intersection|SymDifference|'
            r'VoronoiPolygons|DelaunayTriangles)\s*\(',
            re.IGNORECASE
        )
        
        # Subqueries
        self.subquery_pattern = re.compile(
            r'\b(EXISTS|NOT\s+EXISTS)\s*\(',
            re.IGNORECASE
        )
        
        # IN subquery
        self.in_subquery_pattern = re.compile(
            r'\bIN\s*\(\s*SELECT\b',
            re.IGNORECASE
        )
        
        # All ST_ functions
        self.all_st_pattern = re.compile(
            r'\bST_(\w+)\s*\(',
            re.IGNORECASE
        )
    
    def estimate(
        self,
        expression: str,
        feature_count: int = 0,
        source_feature_count: int = 0
    ) -> float:
        """
        Estimate query complexity score.
        
        Args:
            expression: SQL WHERE clause or full expression
            feature_count: Estimated target layer feature count
            source_feature_count: Estimated source geometry count
        
        Returns:
            Complexity score (higher = more complex)
        """
        breakdown = self.analyze(expression, feature_count, source_feature_count)
        return breakdown.total_score
    
    def analyze(
        self,
        expression: str,
        feature_count: int = 0,
        source_feature_count: int = 0
    ) -> ComplexityBreakdown:
        """
        Analyze expression and return detailed complexity breakdown.
        
        Args:
            expression: SQL expression to analyze
            feature_count: Target layer feature count
            source_feature_count: Source geometry count
        
        Returns:
            ComplexityBreakdown with all cost factors
        """
        breakdown = ComplexityBreakdown()
        breakdown.estimated_features = feature_count
        
        # 1. Analyze spatial predicates
        spatial_matches = self.spatial_pred_pattern.findall(expression)
        breakdown.spatial_predicates = len(spatial_matches)
        for match in spatial_matches:
            cost_attr = f"ST_{match.upper()}"
            breakdown.spatial_predicate_cost += self.costs.get_cost(cost_attr)
        
        # 2. Analyze buffer operations
        buffer_matches = self.buffer_pattern.findall(expression)
        breakdown.buffer_operations = len(buffer_matches)
        for buffer_value in buffer_matches:
            try:
                if float(buffer_value) < 0:
                    breakdown.negative_buffer_count += 1
                    breakdown.buffer_cost += self.costs.ST_BUFFER_NEGATIVE
                else:
                    breakdown.buffer_cost += self.costs.ST_BUFFER
            except ValueError:
                breakdown.buffer_cost += self.costs.ST_BUFFER
        
        # 3. Analyze transforms
        transform_matches = self.transform_pattern.findall(expression)
        breakdown.transform_operations = len(transform_matches)
        for match in transform_matches:
            breakdown.transform_cost += self.costs.get_cost(f"ST_{match}")
        
        # 4. Analyze geometry functions
        validation_matches = self.validation_pattern.findall(expression)
        geom_create_matches = self.geom_create_pattern.findall(expression)
        expensive_matches = self.expensive_pattern.findall(expression)
        
        breakdown.geometry_functions = (
            len(validation_matches) + 
            len(geom_create_matches) + 
            len(expensive_matches)
        )
        
        for match in validation_matches:
            breakdown.geometry_function_cost += self.costs.get_cost(f"ST_{match}")
        for match in geom_create_matches:
            breakdown.geometry_function_cost += self.costs.get_cost(f"ST_{match}")
        for match in expensive_matches:
            breakdown.geometry_function_cost += self.costs.get_cost(f"ST_{match}")
        
        # 5. Analyze subqueries
        subquery_matches = self.subquery_pattern.findall(expression)
        in_subquery_count = len(self.in_subquery_pattern.findall(expression))
        
        breakdown.subqueries = len(subquery_matches) + in_subquery_count
        for match in subquery_matches:
            if 'NOT' in match.upper():
                breakdown.subquery_cost += self.costs.NOT_EXISTS
            else:
                breakdown.subquery_cost += self.costs.EXISTS
        breakdown.subquery_cost += in_subquery_count * self.costs.IN_SUBQUERY
        
        # 6. Calculate volume multiplier
        if feature_count > 0:
            # Logarithmic scaling to prevent extreme values
            import math
            ratio = feature_count / self.VOLUME_SCALE_BASE
            breakdown.volume_multiplier = 1.0 + (
                math.log10(max(1, ratio)) * self.VOLUME_SCALE_FACTOR
            )
        
        # 7. Calculate total score
        base_score = (
            breakdown.spatial_predicate_cost +
            breakdown.buffer_cost +
            breakdown.transform_cost +
            breakdown.geometry_function_cost +
            breakdown.subquery_cost
        )
        
        breakdown.total_score = base_score * breakdown.volume_multiplier
        
        # 8. Determine complexity level
        breakdown.complexity_level = self._classify_complexity(breakdown.total_score)
        
        logger.debug(
            f"Query complexity analysis: {breakdown.to_dict()}"
        )
        
        return breakdown
    
    def _classify_complexity(self, score: float) -> QueryComplexity:
        """Classify score into complexity level."""
        if score < self.TRIVIAL_THRESHOLD:
            return QueryComplexity.TRIVIAL
        elif score < self.SIMPLE_THRESHOLD:
            return QueryComplexity.SIMPLE
        elif score < self.MODERATE_THRESHOLD:
            return QueryComplexity.MODERATE
        elif score < self.COMPLEX_THRESHOLD:
            return QueryComplexity.COMPLEX
        else:
            return QueryComplexity.VERY_COMPLEX
    
    def recommend_strategy(self, score: float) -> str:
        """
        Recommend execution strategy based on complexity score.
        
        Args:
            score: Complexity score from estimate()
        
        Returns:
            Strategy name: 'direct', 'materialized', 'two_phase', 'progressive'
        """
        complexity = self._classify_complexity(score)
        
        strategy_map = {
            QueryComplexity.TRIVIAL: 'direct',
            QueryComplexity.SIMPLE: 'direct',
            QueryComplexity.MODERATE: 'materialized',
            QueryComplexity.COMPLEX: 'two_phase',
            QueryComplexity.VERY_COMPLEX: 'progressive'
        }
        
        return strategy_map.get(complexity, 'direct')
    
    def should_use_two_phase(
        self,
        expression: str,
        feature_count: int = 0,
        has_source_bounds: bool = False
    ) -> Tuple[bool, str]:
        """
        Determine if two-phase filtering should be used.
        
        Args:
            expression: SQL expression
            feature_count: Target feature count
            has_source_bounds: Whether source bbox/geometry is available
        
        Returns:
            Tuple of (should_use, reason)
        """
        if not has_source_bounds:
            return False, "No source bounds available for bbox pre-filter"
        
        breakdown = self.analyze(expression, feature_count)
        
        # Criteria for two-phase
        if breakdown.complexity_level in (
            QueryComplexity.COMPLEX, 
            QueryComplexity.VERY_COMPLEX
        ):
            return True, f"High complexity ({breakdown.total_score:.1f}) benefits from two-phase"
        
        if breakdown.buffer_operations > 0 and feature_count > 10000:
            return True, f"Buffer operations with {feature_count:,} features"
        
        if breakdown.subqueries > 0 and feature_count > 5000:
            return True, f"Subqueries with {feature_count:,} features"
        
        if feature_count > 50000 and breakdown.spatial_predicates > 1:
            return True, f"Multiple predicates on {feature_count:,} features"
        
        return False, "Query is simple enough for direct execution"
    
    def estimate_memory_usage(
        self,
        expression: str,
        feature_count: int,
        avg_geometry_vertices: int = 50
    ) -> Dict[str, float]:
        """
        Estimate memory usage for different execution strategies.
        
        Args:
            expression: SQL expression
            feature_count: Expected result count
            avg_geometry_vertices: Average vertices per geometry
        
        Returns:
            Dict with memory estimates (in MB) for each strategy
        """
        # Base size estimates
        id_size = 8  # bytes per ID (int64)
        vertex_size = 16  # bytes per vertex (2 doubles)
        row_overhead = 50  # bytes overhead per row
        
        geometry_size = avg_geometry_vertices * vertex_size
        full_row_size = id_size + geometry_size + row_overhead
        
        # Strategy estimates
        direct_mb = (feature_count * full_row_size) / (1024 * 1024)
        
        # Progressive only loads IDs, not full geometries
        progressive_mb = (feature_count * id_size) / (1024 * 1024)
        
        # Two-phase loads candidates first (assume 30% pass bbox filter)
        candidate_ratio = 0.3
        two_phase_mb = (
            (feature_count * candidate_ratio * id_size) +  # Phase 1
            (feature_count * 0.1 * id_size)  # Phase 2 results
        ) / (1024 * 1024)
        
        # Streaming uses fixed buffer regardless of result size
        streaming_chunk_size = 5000
        streaming_mb = (streaming_chunk_size * id_size) / (1024 * 1024)
        
        return {
            'direct': round(direct_mb, 2),
            'materialized': round(direct_mb * 1.2, 2),  # MV adds some overhead
            'two_phase': round(two_phase_mb, 2),
            'progressive': round(progressive_mb, 2),
            'streaming': round(streaming_mb, 2)
        }


# Global estimator instance
_global_estimator: Optional[QueryComplexityEstimator] = None


def get_complexity_estimator() -> QueryComplexityEstimator:
    """Get the global complexity estimator instance."""
    global _global_estimator
    if _global_estimator is None:
        _global_estimator = QueryComplexityEstimator()
    return _global_estimator


def estimate_query_complexity(
    expression: str,
    feature_count: int = 0
) -> float:
    """
    Convenience function to estimate query complexity.
    
    Usage:
        score = estimate_query_complexity(expression, 100000)
        if score > 100:
            use_two_phase_filter()
    """
    return get_complexity_estimator().estimate(expression, feature_count)

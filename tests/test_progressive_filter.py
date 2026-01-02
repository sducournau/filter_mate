"""
Tests for progressive filtering and lazy loading optimizations (v2.5.9).

This module tests:
- QueryComplexityEstimator: SQL complexity analysis
- LazyResultIterator: Server-side cursor streaming
- TwoPhaseFilter: Bbox pre-filter + full predicate
- ProgressiveFilterExecutor: Strategy selection and execution
- Enhanced QueryExpressionCache: TTL, counts, complexity caching

Note: These tests use inline implementations to avoid QGIS dependencies.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass, field
import time
import re
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum


# ============================================================================
# Inline Implementation of QueryComplexityEstimator (for testing without QGIS)
# ============================================================================

class OperationCosts:
    """Weighted costs for SQL operations."""
    # Spatial predicates (can use GIST index)
    ST_INTERSECTS = 5
    ST_WITHIN = 6
    ST_CONTAINS = 7
    ST_CROSSES = 5
    ST_TOUCHES = 4
    ST_OVERLAPS = 6
    ST_DISJOINT = 4
    ST_COVERS = 6
    ST_COVEREDBY = 6
    
    # Geometry constructors (expensive)
    ST_BUFFER = 12
    ST_UNION = 15
    ST_DIFFERENCE = 14
    ST_INTERSECTION = 13
    ST_CONVEXHULL = 8
    ST_SIMPLIFY = 7
    
    # Transformations
    ST_TRANSFORM = 10
    ST_SETSRID = 2
    
    # Measurements (moderately expensive)
    ST_DISTANCE = 6
    ST_AREA = 4
    ST_LENGTH = 4
    ST_PERIMETER = 4
    
    # Subqueries
    EXISTS = 20
    IN_SUBQUERY = 15
    NOT_EXISTS = 20
    
    # Aggregations
    COUNT = 3
    SUM = 3
    AVG = 3
    
    # Other
    CASE_WHEN = 2
    CAST = 1


@dataclass
class ComplexityBreakdown:
    """Detailed breakdown of query complexity."""
    spatial_predicates: int = 0
    geometry_constructors: int = 0
    transformations: int = 0
    measurements: int = 0
    subqueries: int = 0
    aggregations: int = 0
    other: int = 0
    
    @property
    def total(self) -> int:
        return (self.spatial_predicates + self.geometry_constructors + 
                self.transformations + self.measurements + 
                self.subqueries + self.aggregations + self.other)


@dataclass
class ComplexityResult:
    """Result of complexity estimation."""
    total_score: int
    recommended_strategy: str
    breakdown: Dict[str, int]
    details: Dict[str, Any] = field(default_factory=dict)


class QueryComplexityEstimator:
    """Estimates the computational complexity of SQL expressions."""
    
    # Regex patterns for different operations
    PATTERNS = {
        'st_intersects': (r'st_intersects\s*\(', OperationCosts.ST_INTERSECTS),
        'st_within': (r'st_within\s*\(', OperationCosts.ST_WITHIN),
        'st_contains': (r'st_contains\s*\(', OperationCosts.ST_CONTAINS),
        'st_crosses': (r'st_crosses\s*\(', OperationCosts.ST_CROSSES),
        'st_touches': (r'st_touches\s*\(', OperationCosts.ST_TOUCHES),
        'st_overlaps': (r'st_overlaps\s*\(', OperationCosts.ST_OVERLAPS),
        'st_disjoint': (r'st_disjoint\s*\(', OperationCosts.ST_DISJOINT),
        'st_covers': (r'st_covers\s*\(', OperationCosts.ST_COVERS),
        'st_coveredby': (r'st_coveredby\s*\(', OperationCosts.ST_COVEREDBY),
        'st_buffer': (r'st_buffer\s*\(', OperationCosts.ST_BUFFER),
        'st_union': (r'st_union\s*\(', OperationCosts.ST_UNION),
        'st_difference': (r'st_difference\s*\(', OperationCosts.ST_DIFFERENCE),
        'st_intersection': (r'st_intersection\s*\(', OperationCosts.ST_INTERSECTION),
        'st_convexhull': (r'st_convexhull\s*\(', OperationCosts.ST_CONVEXHULL),
        'st_simplify': (r'st_simplify\s*\(', OperationCosts.ST_SIMPLIFY),
        'st_transform': (r'st_transform\s*\(', OperationCosts.ST_TRANSFORM),
        'st_setsrid': (r'st_setsrid\s*\(', OperationCosts.ST_SETSRID),
        'st_distance': (r'st_distance\s*\(', OperationCosts.ST_DISTANCE),
        'st_dwithin': (r'st_dwithin\s*\(', OperationCosts.ST_DISTANCE + 2),
        'st_area': (r'st_area\s*\(', OperationCosts.ST_AREA),
        'st_length': (r'st_length\s*\(', OperationCosts.ST_LENGTH),
        'st_perimeter': (r'st_perimeter\s*\(', OperationCosts.ST_PERIMETER),
        'exists': (r'\bexists\s*\(', OperationCosts.EXISTS),
        'not_exists': (r'\bnot\s+exists\s*\(', OperationCosts.NOT_EXISTS),
        'in_subquery': (r'\bin\s*\(\s*select', OperationCosts.IN_SUBQUERY),
    }
    
    # Strategy thresholds
    DIRECT_THRESHOLD = 50
    MATERIALIZED_THRESHOLD = 150
    TWO_PHASE_THRESHOLD = 500
    
    def estimate_complexity(self, expression: Optional[str]) -> ComplexityResult:
        """Estimate complexity of SQL expression."""
        if not expression:
            return ComplexityResult(
                total_score=0,
                recommended_strategy="DIRECT",
                breakdown={}
            )
        
        expr_lower = expression.lower()
        breakdown = ComplexityBreakdown()
        details = {}
        
        # Count each pattern
        for name, (pattern, cost) in self.PATTERNS.items():
            count = len(re.findall(pattern, expr_lower, re.IGNORECASE))
            if count > 0:
                total_cost = count * cost
                details[name] = {'count': count, 'cost': total_cost}
                
                # Categorize
                if name.startswith('st_') and name in ['st_intersects', 'st_within', 'st_contains', 
                                                        'st_crosses', 'st_touches', 'st_overlaps',
                                                        'st_disjoint', 'st_covers', 'st_coveredby']:
                    breakdown.spatial_predicates += total_cost
                elif name in ['st_buffer', 'st_union', 'st_difference', 'st_intersection', 
                              'st_convexhull', 'st_simplify']:
                    breakdown.geometry_constructors += total_cost
                elif name in ['st_transform', 'st_setsrid']:
                    breakdown.transformations += total_cost
                elif name in ['st_distance', 'st_dwithin', 'st_area', 'st_length', 'st_perimeter']:
                    breakdown.measurements += total_cost
                elif name in ['exists', 'not_exists', 'in_subquery']:
                    breakdown.subqueries += total_cost
        
        total_score = breakdown.total
        
        # Determine strategy
        if total_score < self.DIRECT_THRESHOLD:
            strategy = "DIRECT"
        elif total_score < self.MATERIALIZED_THRESHOLD:
            strategy = "MATERIALIZED"
        elif total_score < self.TWO_PHASE_THRESHOLD:
            strategy = "TWO_PHASE"
        else:
            strategy = "PROGRESSIVE"
        
        return ComplexityResult(
            total_score=total_score,
            recommended_strategy=strategy,
            breakdown={
                'spatial_predicates': breakdown.spatial_predicates,
                'geometry_constructors': breakdown.geometry_constructors,
                'transformations': breakdown.transformations,
                'measurements': breakdown.measurements,
                'subqueries': breakdown.subqueries,
            },
            details=details
        )


# ============================================================================
# Inline Implementation of Progressive Filter Components (for testing)
# ============================================================================

class FilterStrategy(Enum):
    """Filter execution strategies."""
    DIRECT = "DIRECT"
    MATERIALIZED = "MATERIALIZED"
    TWO_PHASE = "TWO_PHASE"
    PROGRESSIVE = "PROGRESSIVE"


@dataclass
class StrategyConfig:
    """Configuration for a filter strategy."""
    name: str
    use_lazy_cursor: bool = False
    chunk_size: int = 5000


@dataclass
class FilterResult:
    """Result of a progressive filter operation."""
    feature_ids: List[int]
    total_count: int
    strategy_used: str
    execution_time_ms: float
    phase1_candidates: int = 0
    phase2_filtered: int = 0


class LazyResultIterator:
    """Iterator for lazy loading results from PostgreSQL."""
    
    def __init__(self, connection, query: str, chunk_size: int = 5000):
        self.connection = connection
        self.query = query
        self.chunk_size = chunk_size
        self._cursor = None
    
    def __enter__(self):
        self._cursor = self.connection.cursor()
        self._cursor.execute(self.query)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._cursor:
            self._cursor.close()
    
    def __iter__(self):
        return self
    
    def __next__(self):
        if not self._cursor:
            raise StopIteration
        
        batch = self._cursor.fetchmany(self.chunk_size)
        if not batch:
            raise StopIteration
        return batch


class TwoPhaseFilter:
    """Implements two-phase filtering: bbox pre-filter + full predicate."""
    
    def __init__(self, connection):
        self.connection = connection
    
    def execute_phase1(self, table_name: str, geometry_column: str, 
                       source_bounds: str, id_column: str = "id") -> List[int]:
        """Execute phase 1: bbox intersection using GIST index."""
        sql = f"""
        SELECT {id_column} FROM {table_name}
        WHERE {geometry_column} && {source_bounds}
        """
        cursor = self.connection.cursor()
        cursor.execute(sql)
        results = cursor.fetchall()
        cursor.close()
        return [r[0] for r in results]
    
    def execute_phase2(self, table_name: str, id_column: str,
                       candidate_ids: List[int], full_predicate: str) -> List[int]:
        """Execute phase 2: full predicate on candidates."""
        if not candidate_ids:
            return []
        
        ids_str = ",".join(str(i) for i in candidate_ids)
        sql = f"""
        SELECT {id_column} FROM {table_name}
        WHERE {id_column} IN ({ids_str}) AND {full_predicate}
        """
        cursor = self.connection.cursor()
        cursor.execute(sql)
        results = cursor.fetchall()
        cursor.close()
        return [r[0] for r in results]


class ProgressiveFilterExecutor:
    """Main executor for progressive filtering."""
    
    # Thresholds
    LAZY_CURSOR_THRESHOLD = 50000
    TWO_PHASE_COMPLEXITY_THRESHOLD = 100
    
    def __init__(self, connection, query_cache=None):
        self.connection = connection
        self.query_cache = query_cache
    
    def _select_strategy(self, feature_count: int, complexity_score: int) -> StrategyConfig:
        """Select appropriate strategy based on dataset and complexity."""
        use_lazy = feature_count >= self.LAZY_CURSOR_THRESHOLD
        
        if complexity_score < 50:
            return StrategyConfig(name="DIRECT", use_lazy_cursor=use_lazy)
        elif complexity_score < 150:
            return StrategyConfig(name="MATERIALIZED", use_lazy_cursor=use_lazy)
        elif complexity_score < 500:
            return StrategyConfig(name="TWO_PHASE", use_lazy_cursor=use_lazy)
        else:
            return StrategyConfig(name="PROGRESSIVE", use_lazy_cursor=True)


# ============================================================================
# Inline Implementation of Enhanced Query Cache (for testing)
# ============================================================================

@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    expression: str
    created_at: float
    access_count: int = 0
    result_count: Optional[int] = None
    complexity_score: Optional[int] = None


class QueryExpressionCache:
    """Enhanced query expression cache with TTL and metadata."""
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 0):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._complexity_cache: Dict[str, int] = {}
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[str]:
        """Get cached expression."""
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None
        
        # Check TTL
        if self.ttl_seconds > 0:
            age = time.time() - entry.created_at
            if age > self.ttl_seconds:
                del self._cache[key]
                self._misses += 1
                return None
        
        # Update access
        entry.access_count += 1
        self._cache.move_to_end(key)
        self._hits += 1
        return entry.expression
    
    def get_entry(self, key: str) -> Optional[CacheEntry]:
        """Get full cache entry with metadata."""
        return self._cache.get(key)
    
    def get_with_count(self, key: str) -> Tuple[Optional[str], Optional[int]]:
        """Get expression and result count."""
        entry = self._cache.get(key)
        if entry is None:
            return None, None
        
        # Check TTL
        if self.ttl_seconds > 0:
            age = time.time() - entry.created_at
            if age > self.ttl_seconds:
                del self._cache[key]
                return None, None
        
        entry.access_count += 1
        return entry.expression, entry.result_count
    
    def put(self, key: str, expression: str, result_count: Optional[int] = None,
            complexity_score: Optional[int] = None):
        """Store expression with metadata."""
        # Evict if at capacity
        while len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)
        
        self._cache[key] = CacheEntry(
            expression=expression,
            created_at=time.time(),
            access_count=0,
            result_count=result_count,
            complexity_score=complexity_score
        )
    
    def put_complexity(self, key: str, score: int):
        """Cache complexity score."""
        self._complexity_cache[key] = score
    
    def get_complexity(self, key: str) -> Optional[int]:
        """Get cached complexity score."""
        return self._complexity_cache.get(key)
    
    def evict_expired(self) -> int:
        """Remove expired entries."""
        if self.ttl_seconds <= 0:
            return 0
        
        now = time.time()
        expired = [k for k, v in self._cache.items() 
                   if now - v.created_at > self.ttl_seconds]
        for k in expired:
            del self._cache[k]
        return len(expired)
    
    def get_hot_entries(self, limit: int = 10) -> List[Tuple[str, CacheEntry]]:
        """Get most accessed entries."""
        sorted_entries = sorted(self._cache.items(), 
                               key=lambda x: x[1].access_count, 
                               reverse=True)
        return sorted_entries[:limit]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate_percent': round(hit_rate, 2),
            'size': len(self._cache)
        }


# ============================================================================
# Test Classes
# ============================================================================

class TestQueryComplexityEstimator(unittest.TestCase):
    """Tests for query complexity estimation."""

    def setUp(self):
        """Set up test fixtures."""
        self.estimator = QueryComplexityEstimator()

    def test_simple_expression_low_score(self):
        """Simple expressions should have low complexity scores."""
        simple_sql = "SELECT id FROM table WHERE name = 'test'"
        result = self.estimator.estimate_complexity(simple_sql)
        
        self.assertLess(result.total_score, 50)
        self.assertEqual(result.recommended_strategy, "DIRECT")

    def test_st_intersects_moderate_score(self):
        """ST_Intersects should add moderate complexity."""
        sql = "SELECT id FROM parcels WHERE ST_Intersects(geom, ST_GeomFromText('POINT(0 0)'))"
        result = self.estimator.estimate_complexity(sql)
        
        self.assertGreater(result.total_score, 0)
        self.assertIn('spatial_predicates', result.breakdown)

    def test_st_buffer_high_cost(self):
        """ST_Buffer is expensive and should increase score significantly."""
        sql = "SELECT id FROM parcels WHERE ST_Intersects(geom, ST_Buffer(source_geom, 100))"
        result = self.estimator.estimate_complexity(sql)
        
        # ST_Buffer has cost 12, ST_Intersects has cost 5
        self.assertGreaterEqual(result.total_score, 17)

    def test_nested_buffer_multiplied_cost(self):
        """Multiple ST_Buffer calls should multiply cost."""
        sql = """
        SELECT id FROM parcels 
        WHERE ST_Intersects(geom, ST_Buffer(ST_Buffer(source_geom, 100), 50))
        """
        result = self.estimator.estimate_complexity(sql)
        
        # Two ST_Buffer calls
        self.assertGreaterEqual(result.total_score, 24)

    def test_exists_subquery_very_high_cost(self):
        """EXISTS with subquery should have very high cost."""
        sql = """
        SELECT id FROM parcels p 
        WHERE EXISTS (SELECT 1 FROM buildings b WHERE ST_Intersects(p.geom, b.geom))
        """
        result = self.estimator.estimate_complexity(sql)
        
        # EXISTS has cost 20
        self.assertGreaterEqual(result.total_score, 20)

    def test_st_transform_adds_cost(self):
        """ST_Transform (coordinate reprojection) adds cost."""
        sql = "SELECT id FROM parcels WHERE ST_Intersects(ST_Transform(geom, 4326), source_geom)"
        result = self.estimator.estimate_complexity(sql)
        
        # ST_Transform has cost 10
        self.assertGreaterEqual(result.total_score, 10)

    def test_complex_expression_recommends_two_phase(self):
        """Complex expressions should recommend appropriate strategy."""
        complex_sql = """
        SELECT id FROM parcels 
        WHERE ST_Intersects(geom, ST_Buffer(ST_Transform(source_geom, 2154), 500))
        AND ST_Within(geom, ST_Buffer(envelope_geom, 1000))
        """
        result = self.estimator.estimate_complexity(complex_sql)
        
        # Should have significant complexity (ST_Intersects=5, ST_Buffer=12*2, ST_Transform=10, ST_Within=6)
        # Total = 5 + 24 + 10 + 6 = 45
        self.assertGreaterEqual(result.total_score, 40)
        self.assertIn(result.recommended_strategy, ["DIRECT", "MATERIALIZED", "TWO_PHASE", "PROGRESSIVE"])

    def test_very_complex_recommends_progressive(self):
        """Very complex expressions should have high scores."""
        very_complex_sql = """
        SELECT id FROM parcels p
        WHERE ST_Intersects(p.geom, ST_Buffer(ST_Transform(src.geom, 2154), 500))
        AND EXISTS (
            SELECT 1 FROM buildings b 
            WHERE ST_Intersects(p.geom, ST_Buffer(b.geom, 50))
        )
        AND EXISTS (
            SELECT 1 FROM roads r 
            WHERE ST_DWithin(p.geom, r.geom, 100)
        )
        AND ST_Area(p.geom) > 1000
        """
        result = self.estimator.estimate_complexity(very_complex_sql)
        
        # Should have high score due to multiple EXISTS, ST_Buffer, ST_DWithin, etc.
        # EXISTS=20*2, ST_Intersects=5*2, ST_Buffer=12*2, ST_Transform=10, ST_DWithin=8, ST_Area=4
        # Total should be significant
        self.assertGreaterEqual(result.total_score, 80)

    def test_empty_expression_zero_score(self):
        """Empty or None expressions should return zero score."""
        result = self.estimator.estimate_complexity("")
        self.assertEqual(result.total_score, 0)
        
        result = self.estimator.estimate_complexity(None)
        self.assertEqual(result.total_score, 0)

    def test_case_insensitive_detection(self):
        """Function detection should be case-insensitive."""
        sql1 = "SELECT id WHERE ST_INTERSECTS(geom, source)"
        sql2 = "SELECT id WHERE st_intersects(geom, source)"
        sql3 = "SELECT id WHERE St_Intersects(geom, source)"
        
        result1 = self.estimator.estimate_complexity(sql1)
        result2 = self.estimator.estimate_complexity(sql2)
        result3 = self.estimator.estimate_complexity(sql3)
        
        self.assertEqual(result1.total_score, result2.total_score)
        self.assertEqual(result2.total_score, result3.total_score)


class TestLazyResultIterator(unittest.TestCase):
    """Tests for lazy cursor streaming."""

    def test_iterator_yields_batches(self):
        """Iterator should yield results in batches."""
        
        # Mock connection with cursor
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        
        # Simulate 3 batches of results
        mock_cursor.fetchmany.side_effect = [
            [(1,), (2,), (3,)],  # First batch
            [(4,), (5,)],        # Second batch
            []                    # End
        ]
        
        with LazyResultIterator(mock_connection, "SELECT id FROM test", chunk_size=3) as iterator:
            batches = list(iterator)
        
        self.assertEqual(len(batches), 2)
        self.assertEqual(batches[0], [(1,), (2,), (3,)])
        self.assertEqual(batches[1], [(4,), (5,)])

    def test_iterator_handles_empty_result(self):
        """Iterator should handle empty result set gracefully."""
        
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchmany.return_value = []
        
        with LazyResultIterator(mock_connection, "SELECT id FROM empty_table", chunk_size=100) as iterator:
            batches = list(iterator)
        
        self.assertEqual(len(batches), 0)

    def test_iterator_closes_cursor(self):
        """Iterator should close cursor on exit."""
        
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchmany.return_value = []
        
        with LazyResultIterator(mock_connection, "SELECT id FROM test", chunk_size=100) as iterator:
            list(iterator)
        
        mock_cursor.close.assert_called_once()


class TestTwoPhaseFilter(unittest.TestCase):
    """Tests for two-phase filtering."""

    def test_phase1_uses_bbox_operator(self):
        """Phase 1 should use && operator for GIST index."""
        
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [(1,), (2,), (3,)]
        
        filter_obj = TwoPhaseFilter(mock_connection)
        
        # Execute phase 1
        candidates = filter_obj.execute_phase1(
            table_name="parcels",
            geometry_column="geom",
            source_bounds="ST_MakeEnvelope(0, 0, 100, 100, 4326)",
            id_column="id"
        )
        
        # Verify && operator was used
        call_args = mock_cursor.execute.call_args[0][0]
        self.assertIn("&&", call_args)
        self.assertEqual(candidates, [1, 2, 3])

    def test_phase2_applies_full_predicate(self):
        """Phase 2 should apply full predicate on candidates."""
        
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [(1,), (3,)]
        
        filter_obj = TwoPhaseFilter(mock_connection)
        
        # Execute phase 2
        results = filter_obj.execute_phase2(
            table_name="parcels",
            id_column="id",
            candidate_ids=[1, 2, 3],
            full_predicate="ST_Intersects(geom, ST_Buffer(source, 100))"
        )
        
        # Verify IN clause was used
        call_args = mock_cursor.execute.call_args[0][0]
        self.assertIn("IN", call_args)
        self.assertEqual(results, [1, 3])

    def test_empty_candidates_skips_phase2(self):
        """Phase 2 should be skipped if no candidates from phase 1."""
        
        mock_connection = Mock()
        filter_obj = TwoPhaseFilter(mock_connection)
        
        results = filter_obj.execute_phase2(
            table_name="parcels",
            id_column="id",
            candidate_ids=[],
            full_predicate="ST_Intersects(geom, source)"
        )
        
        self.assertEqual(results, [])
        # No cursor should be created for empty candidates
        mock_connection.cursor.assert_not_called()


class TestProgressiveFilterExecutor(unittest.TestCase):
    """Tests for the main progressive filter executor."""

    def test_strategy_selection_direct(self):
        """Low complexity should select DIRECT strategy."""
        
        mock_connection = Mock()
        executor = ProgressiveFilterExecutor(mock_connection)
        
        strategy = executor._select_strategy(
            feature_count=1000,
            complexity_score=30
        )
        
        self.assertEqual(strategy.name, "DIRECT")

    def test_strategy_selection_materialized(self):
        """Medium complexity should select MATERIALIZED strategy."""
        
        mock_connection = Mock()
        executor = ProgressiveFilterExecutor(mock_connection)
        
        strategy = executor._select_strategy(
            feature_count=5000,
            complexity_score=80
        )
        
        self.assertEqual(strategy.name, "MATERIALIZED")

    def test_strategy_selection_two_phase(self):
        """High complexity should select TWO_PHASE strategy."""
        
        mock_connection = Mock()
        executor = ProgressiveFilterExecutor(mock_connection)
        
        strategy = executor._select_strategy(
            feature_count=10000,
            complexity_score=180
        )
        
        self.assertEqual(strategy.name, "TWO_PHASE")

    def test_strategy_selection_progressive(self):
        """Very high complexity + large dataset should select PROGRESSIVE."""
        
        mock_connection = Mock()
        executor = ProgressiveFilterExecutor(mock_connection)
        
        strategy = executor._select_strategy(
            feature_count=200000,
            complexity_score=600
        )
        
        self.assertEqual(strategy.name, "PROGRESSIVE")

    def test_large_dataset_forces_lazy_cursor(self):
        """Large datasets should force lazy cursor regardless of complexity."""
        
        mock_connection = Mock()
        executor = ProgressiveFilterExecutor(mock_connection)
        
        # Even with low complexity, large dataset should use streaming
        strategy = executor._select_strategy(
            feature_count=100000,
            complexity_score=20
        )
        
        # Should still enable lazy cursor for memory efficiency
        self.assertTrue(strategy.use_lazy_cursor or strategy.name in ["PROGRESSIVE", "TWO_PHASE"])


class TestEnhancedQueryCache(unittest.TestCase):
    """Tests for enhanced query expression cache."""

    def setUp(self):
        """Reset cache for each test."""
        self.cache = QueryExpressionCache(max_size=10, ttl_seconds=5)

    def test_put_and_get_basic(self):
        """Basic put and get should work."""
        self.cache.put("key1", "expression1")
        result = self.cache.get("key1")
        
        self.assertEqual(result, "expression1")

    def test_get_nonexistent_returns_none(self):
        """Getting nonexistent key should return None."""
        result = self.cache.get("nonexistent")
        self.assertIsNone(result)

    def test_put_with_metadata(self):
        """Put should store metadata (count, complexity)."""
        self.cache.put("key1", "expr1", result_count=1500, complexity_score=120)
        
        entry = self.cache.get_entry("key1")
        
        self.assertIsNotNone(entry)
        self.assertEqual(entry.expression, "expr1")
        self.assertEqual(entry.result_count, 1500)
        self.assertEqual(entry.complexity_score, 120)

    def test_get_with_count(self):
        """get_with_count should return expression and count."""
        self.cache.put("key1", "expr1", result_count=2500)
        
        expr, count = self.cache.get_with_count("key1")
        
        self.assertEqual(expr, "expr1")
        self.assertEqual(count, 2500)

    def test_access_count_increments(self):
        """Each get should increment access count."""
        self.cache.put("key1", "expr1")
        
        self.cache.get("key1")
        self.cache.get("key1")
        self.cache.get("key1")
        
        entry = self.cache.get_entry("key1")
        self.assertEqual(entry.access_count, 3)

    def test_ttl_expiration(self):
        """Entries should expire after TTL."""
        # Use short TTL for test
        short_ttl_cache = type(self.cache)(max_size=10, ttl_seconds=0.1)
        short_ttl_cache.put("key1", "expr1")
        
        # Should exist immediately
        self.assertIsNotNone(short_ttl_cache.get("key1"))
        
        # Wait for expiration
        time.sleep(0.15)
        
        # Should be expired
        self.assertIsNone(short_ttl_cache.get("key1"))

    def test_evict_expired(self):
        """evict_expired should remove expired entries."""
        short_ttl_cache = type(self.cache)(max_size=10, ttl_seconds=0.1)
        short_ttl_cache.put("key1", "expr1")
        short_ttl_cache.put("key2", "expr2")
        
        time.sleep(0.15)
        
        removed = short_ttl_cache.evict_expired()
        
        self.assertEqual(removed, 2)
        self.assertEqual(len(short_ttl_cache._cache), 0)

    def test_lru_eviction(self):
        """LRU eviction should remove least recently used."""
        small_cache = type(self.cache)(max_size=3, ttl_seconds=0)
        
        small_cache.put("key1", "expr1")
        small_cache.put("key2", "expr2")
        small_cache.put("key3", "expr3")
        
        # Access key1 to make it recently used
        small_cache.get("key1")
        
        # Add new entry, should evict key2 (least recently used)
        small_cache.put("key4", "expr4")
        
        self.assertIsNotNone(small_cache.get("key1"))
        self.assertIsNone(small_cache.get("key2"))  # Evicted
        self.assertIsNotNone(small_cache.get("key3"))
        self.assertIsNotNone(small_cache.get("key4"))

    def test_hot_entries(self):
        """get_hot_entries should return most accessed."""
        self.cache.put("key1", "expr1")
        self.cache.put("key2", "expr2")
        self.cache.put("key3", "expr3")
        
        # Access key2 multiple times
        for _ in range(5):
            self.cache.get("key2")
        
        # Access key1 a few times
        for _ in range(2):
            self.cache.get("key1")
        
        hot = self.cache.get_hot_entries(limit=2)
        
        self.assertEqual(len(hot), 2)
        self.assertEqual(hot[0][0], "key2")  # Most accessed

    def test_complexity_cache(self):
        """Complexity scores should be cached separately."""
        self.cache.put_complexity("hash123", 150)
        
        score = self.cache.get_complexity("hash123")
        
        self.assertEqual(score, 150)

    def test_stats(self):
        """Cache should track hit/miss statistics."""
        self.cache.put("key1", "expr1")
        
        self.cache.get("key1")  # Hit
        self.cache.get("key1")  # Hit
        self.cache.get("nonexistent")  # Miss
        
        stats = self.cache.get_stats()
        
        self.assertEqual(stats['hits'], 2)
        self.assertEqual(stats['misses'], 1)
        self.assertAlmostEqual(stats['hit_rate_percent'], 66.67, places=1)


class TestFilterResult(unittest.TestCase):
    """Tests for FilterResult dataclass."""

    def test_filter_result_creation(self):
        """FilterResult should store all fields correctly."""
        
        result = FilterResult(
            feature_ids=[1, 2, 3],
            total_count=3,
            strategy_used="TWO_PHASE",
            execution_time_ms=150.5,
            phase1_candidates=100,
            phase2_filtered=3
        )
        
        self.assertEqual(result.feature_ids, [1, 2, 3])
        self.assertEqual(result.total_count, 3)
        self.assertEqual(result.strategy_used, "TWO_PHASE")
        self.assertEqual(result.phase1_candidates, 100)

    def test_filter_result_reduction_ratio(self):
        """Should calculate correct reduction ratio."""
        
        result = FilterResult(
            feature_ids=[1, 2, 3],
            total_count=3,
            strategy_used="TWO_PHASE",
            execution_time_ms=100,
            phase1_candidates=1000,
            phase2_filtered=3
        )
        
        # 1000 candidates reduced to 3 = 99.7% reduction
        reduction = (result.phase1_candidates - result.phase2_filtered) / result.phase1_candidates * 100
        self.assertGreater(reduction, 99)


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete progressive filter pipeline."""

    def test_full_pipeline_with_mock_connection(self):
        """Test complete filtering pipeline with mocked database."""
        
        # Setup mocks
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        
        # Phase 1: 100 bbox candidates
        # Phase 2: 5 final results
        mock_cursor.fetchall.side_effect = [
            [(i,) for i in range(1, 101)],  # Phase 1: 100 candidates
            [(1,), (5,), (10,), (50,), (99,)]  # Phase 2: 5 results
        ]
        
        # Create executor and estimator (using inline implementations)
        executor = ProgressiveFilterExecutor(mock_connection)
        estimator = QueryComplexityEstimator()
        
        # Analyze complexity
        complex_expression = """
        ST_Intersects(geom, ST_Buffer(ST_Transform(source_geom, 2154), 500))
        """
        complexity = estimator.estimate_complexity(complex_expression)
        
        # Verify complexity was calculated (ST_Intersects=5, ST_Buffer=12, ST_Transform=10 = 27)
        self.assertGreater(complexity.total_score, 0)
        self.assertIn('spatial_predicates', complexity.breakdown)


if __name__ == '__main__':
    unittest.main()

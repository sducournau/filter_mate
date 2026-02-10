# -*- coding: utf-8 -*-
"""
FilterMate PostgreSQL Query Optimizer - ARCH-037

Query optimization for PostgreSQL filter operations.
Extracted from monolithic postgresql_backend.py as part of Phase 4.

Features:
- Query analysis and complexity estimation
- Index usage recommendations
- Query rewriting for optimization
- Execution plan analysis

Author: FilterMate Team
Date: January 2026
"""

import logging
import re
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

try:
    import psycopg2
except ImportError:
    psycopg2 = None

logger = logging.getLogger('FilterMate.PostgreSQL.Optimizer')


class QueryType(Enum):
    """Types of SQL queries."""
    SELECT = "SELECT"
    SPATIAL = "SPATIAL"
    AGGREGATE = "AGGREGATE"
    SUBQUERY = "SUBQUERY"


@dataclass
class QueryAnalysis:
    """Analysis results for a query."""
    query_type: QueryType
    estimated_complexity: int
    uses_spatial_index: bool
    uses_btree_index: bool
    has_subquery: bool
    table_scans: List[str] = field(default_factory=list)
    index_scans: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class OptimizationResult:
    """Result of query optimization."""
    original_query: str
    optimized_query: str
    changes_made: List[str]
    estimated_speedup: float  # 1.0 = no change, 2.0 = 2x faster


class QueryOptimizer:
    """
    Optimizes SQL queries for PostgreSQL/PostGIS.

    Provides:
    - Query analysis and complexity estimation
    - Index usage detection
    - Query rewriting suggestions
    - Execution plan analysis

    Example:
        optimizer = QueryOptimizer(connection_pool)

        # Analyze query
        analysis = optimizer.analyze("SELECT * FROM roads WHERE type = 'highway'")

        # Optimize query
        result = optimizer.optimize("SELECT * FROM roads WHERE ST_Distance(geom, point) < 100")
    """

    # Patterns for query analysis
    SPATIAL_FUNCTIONS = {
        'st_intersects', 'st_contains', 'st_within', 'st_crosses',
        'st_touches', 'st_overlaps', 'st_dwithin', 'st_distance',
        'st_buffer', 'st_union', 'st_intersection', 'st_area',
        'st_length', 'st_centroid', 'st_envelope', 'st_transform',
        'st_setsrid', 'st_point', 'st_makepoint', 'st_geomfromtext',
        'st_astext', 'st_asgeojson', 'st_asbinary'
    }

    SPATIAL_INDEXABLE = {
        'st_intersects', 'st_dwithin', 'st_contains', 'st_within',
        'st_crosses', 'st_touches', 'st_overlaps'
    }

    AGGREGATE_FUNCTIONS = {
        'count', 'sum', 'avg', 'min', 'max', 'array_agg',
        'string_agg', 'json_agg', 'jsonb_agg', 'st_collect',
        'st_union', 'st_extent'
    }

    def __init__(self, connection_pool=None):
        """
        Initialize QueryOptimizer.

        Args:
            connection_pool: Optional connection pool for EXPLAIN analysis
        """
        self._pool = connection_pool
        self._metrics = {
            'queries_analyzed': 0,
            'queries_optimized': 0,
            'total_speedup': 0.0
        }

    @property
    def metrics(self) -> Dict[str, Any]:
        """Get optimizer metrics."""
        return self._metrics.copy()

    def analyze(self, query: str) -> QueryAnalysis:
        """
        Analyze a SQL query.

        Args:
            query: SQL query string

        Returns:
            QueryAnalysis with complexity and recommendations
        """
        query_lower = query.lower()

        # Determine query type
        query_type = self._detect_query_type(query_lower)

        # Estimate complexity
        complexity = self._estimate_complexity(query_lower)

        # Check for index usage patterns
        uses_spatial = self._has_spatial_index_usage(query_lower)
        uses_btree = self._has_btree_index_usage(query_lower)

        # Detect subqueries
        has_subquery = 'select' in query_lower[7:] if query_lower.startswith('select') else False

        # Generate warnings and suggestions
        warnings = self._generate_warnings(query_lower)
        suggestions = self._generate_suggestions(query_lower, query_type)

        self._metrics['queries_analyzed'] += 1

        return QueryAnalysis(
            query_type=query_type,
            estimated_complexity=complexity,
            uses_spatial_index=uses_spatial,
            uses_btree_index=uses_btree,
            has_subquery=has_subquery,
            table_scans=[],
            index_scans=[],
            warnings=warnings,
            suggestions=suggestions
        )

    def optimize(self, query: str) -> OptimizationResult:
        """
        Optimize a SQL query.

        Args:
            query: SQL query string

        Returns:
            OptimizationResult with optimized query
        """
        optimized = query
        changes: List[str] = []
        speedup = 1.0

        # Apply optimizations
        optimized, change = self._optimize_spatial_predicates(optimized)
        if change:
            changes.append(change)
            speedup *= 1.2

        optimized, change = self._optimize_like_patterns(optimized)
        if change:
            changes.append(change)
            speedup *= 1.1

        optimized, change = self._optimize_null_checks(optimized)
        if change:
            changes.append(change)
            speedup *= 1.05

        optimized, change = self._optimize_in_clauses(optimized)
        if change:
            changes.append(change)
            speedup *= 1.15

        self._metrics['queries_optimized'] += 1
        self._metrics['total_speedup'] += speedup

        return OptimizationResult(
            original_query=query,
            optimized_query=optimized,
            changes_made=changes,
            estimated_speedup=speedup
        )

    def get_execution_plan(
        self,
        query: str,
        connection=None
    ) -> Optional[Dict[str, Any]]:
        """
        Get execution plan for query.

        Args:
            query: SQL query string
            connection: Database connection (optional)

        Returns:
            Execution plan as dictionary or None
        """
        conn = connection or self._get_connection()
        if conn is None:
            return None

        try:
            cursor = conn.cursor()
            cursor.execute(f"EXPLAIN (FORMAT JSON, ANALYZE false) {query}")
            result = cursor.fetchone()
            return result[0] if result else None
        except (psycopg2.Error if psycopg2 else Exception) as e:
            logger.warning(f"[PostgreSQL] Failed to get execution plan: {e}")
            return None

    def estimate_row_count(
        self,
        query: str,
        connection=None
    ) -> int:
        """
        Estimate result row count from execution plan.

        Args:
            query: SQL query string
            connection: Database connection (optional)

        Returns:
            Estimated row count or -1 if unavailable
        """
        plan = self.get_execution_plan(query, connection)
        if plan and isinstance(plan, list) and plan:
            return int(plan[0].get('Plan', {}).get('Plan Rows', -1))
        return -1

    def estimate_cost(
        self,
        query: str,
        connection=None
    ) -> Tuple[float, float]:
        """
        Estimate query cost from execution plan.

        Args:
            query: SQL query string
            connection: Database connection (optional)

        Returns:
            Tuple of (startup_cost, total_cost) or (0, 0) if unavailable
        """
        plan = self.get_execution_plan(query, connection)
        if plan and isinstance(plan, list) and plan:
            plan_info = plan[0].get('Plan', {})
            startup = plan_info.get('Startup Cost', 0.0)
            total = plan_info.get('Total Cost', 0.0)
            return (startup, total)
        return (0.0, 0.0)

    def suggest_indexes(
        self,
        query: str,
        table_name: str,
        connection=None
    ) -> List[str]:
        """
        Suggest indexes that could improve query performance.

        Args:
            query: SQL query string
            table_name: Table being queried
            connection: Database connection (optional)

        Returns:
            List of suggested CREATE INDEX statements
        """
        suggestions: List[str] = []
        query_lower = query.lower()

        # Find columns in WHERE clause
        where_match = re.search(r'where\s+(.+?)(?:order|group|limit|$)', query_lower, re.DOTALL)
        if not where_match:
            return suggestions

        where_clause = where_match.group(1)

        # Extract column names from conditions
        column_pattern = r'(\w+)\s*(?:=|<|>|<=|>=|<>|!=|like|in|between)'
        columns = set(re.findall(column_pattern, where_clause))

        # Check for spatial functions
        for func in self.SPATIAL_INDEXABLE:
            if func in where_clause:
                geom_match = re.search(rf'{func}\s*\(\s*(\w+)', where_clause)
                if geom_match:
                    geom_col = geom_match.group(1)
                    suggestions.append(
                        f"CREATE INDEX ON {table_name} USING GIST ({geom_col})"
                    )

        # Suggest btree indexes for other columns
        for col in columns:
            if col not in ('and', 'or', 'not', 'is', 'null'):
                suggestions.append(
                    f"CREATE INDEX ON {table_name} ({col})"
                )

        return suggestions

    # === Private Methods ===

    def _get_connection(self):
        """Get connection from pool."""
        if self._pool is None:
            return None
        try:
            if hasattr(self._pool, 'get_connection'):
                return self._pool.get_connection()
            elif hasattr(self._pool, 'getconn'):
                return self._pool.getconn()
            else:
                return self._pool
        except Exception:  # catch-all safety net (pool abstraction may raise varied errors)
            return None

    def _detect_query_type(self, query: str) -> QueryType:
        """Detect type of query."""
        if any(fn in query for fn in self.SPATIAL_FUNCTIONS):
            return QueryType.SPATIAL
        if any(fn + '(' in query for fn in self.AGGREGATE_FUNCTIONS):
            return QueryType.AGGREGATE
        if query.count('select') > 1:
            return QueryType.SUBQUERY
        return QueryType.SELECT

    def _estimate_complexity(self, query: str) -> int:
        """
        Estimate query complexity (1-10 scale).

        Higher values indicate more complex/expensive queries.
        """
        complexity = 1

        # Joins add complexity
        complexity += query.count(' join ') * 2
        complexity += query.count(' left join ') * 2
        complexity += query.count(' right join ') * 2
        complexity += query.count(' full join ') * 3

        # Subqueries add complexity
        complexity += (query.count('select') - 1) * 2

        # Spatial functions add complexity
        spatial_count = sum(1 for fn in self.SPATIAL_FUNCTIONS if fn in query)
        complexity += min(spatial_count, 3)

        # Aggregate functions add complexity
        agg_count = sum(1 for fn in self.AGGREGATE_FUNCTIONS if fn + '(' in query)
        complexity += agg_count

        # OR conditions add complexity
        complexity += query.count(' or ')

        # LIKE patterns add complexity
        complexity += query.count(' like ')

        # Group by adds complexity
        if ' group by ' in query:
            complexity += 1

        # Order by adds complexity
        if ' order by ' in query:
            complexity += 1

        return min(complexity, 10)

    def _has_spatial_index_usage(self, query: str) -> bool:
        """Check if query can use spatial index."""
        return any(fn in query for fn in self.SPATIAL_INDEXABLE)

    def _has_btree_index_usage(self, query: str) -> bool:
        """Check if query can use btree index."""
        # Look for equality and range conditions
        return bool(re.search(r'\w+\s*(?:=|<|>|<=|>=|between)\s*', query))

    def _generate_warnings(self, query: str) -> List[str]:
        """Generate warnings for potential issues."""
        warnings: List[str] = []

        if ' or ' in query and ' and ' in query:
            warnings.append("Mixed OR/AND conditions may prevent index usage")

        if re.search(r"like\s+'%", query):
            warnings.append("Leading wildcard in LIKE prevents index usage")

        if re.search(r'select\s+\*', query):
            warnings.append("SELECT * may retrieve unnecessary columns")

        if query.count(' join ') > 3:
            warnings.append("Multiple joins may benefit from query restructuring")

        if 'st_distance' in query and 'order by' in query:
            warnings.append("ST_Distance in ORDER BY can be slow for large datasets")

        if ' in (' in query:
            in_match = re.search(r'in\s*\(((?:[^()]+|\([^()]*\))*)\)', query)
            if in_match:
                values = in_match.group(1).count(',') + 1
                if values > 100:
                    warnings.append(f"Large IN clause ({values} values) may be slow")

        return warnings

    def _generate_suggestions(
        self,
        query: str,
        query_type: QueryType
    ) -> List[str]:
        """Generate optimization suggestions."""
        suggestions: List[str] = []

        if query_type == QueryType.SPATIAL:
            if 'st_distance' in query and 'st_dwithin' not in query:
                if re.search(r'st_distance.*<', query):
                    suggestions.append(
                        "Consider ST_DWithin instead of ST_Distance < X for better index usage"
                    )

            if 'st_buffer' in query and 'st_intersects' in query:
                suggestions.append(
                    "Pre-computed buffer in MV may improve performance"
                )

            if 'st_transform' in query:
                suggestions.append(
                    "Consider pre-transforming data to avoid runtime transformation"
                )

        if 'order by' in query and 'limit' not in query:
            suggestions.append("Consider adding LIMIT for large result sets")

        if query.count(' or ') > 2:
            suggestions.append("Consider using UNION instead of multiple ORs")

        if 'distinct' in query and 'group by' not in query:
            suggestions.append("GROUP BY may be faster than DISTINCT for some queries")

        return suggestions

    def _optimize_spatial_predicates(self, query: str) -> Tuple[str, Optional[str]]:
        """Optimize spatial predicates."""
        # Convert ST_Distance < X to ST_DWithin
        pattern = r"st_distance\s*\(([^,]+),\s*([^)]+)\)\s*<\s*(\d+(?:\.\d+)?)"
        if re.search(pattern, query, re.IGNORECASE):
            optimized = re.sub(
                pattern,
                r"ST_DWithin(\1, \2, \3)",
                query,
                flags=re.IGNORECASE
            )
            return optimized, "Converted ST_Distance < X to ST_DWithin for index usage"
        return query, None

    def _optimize_like_patterns(self, query: str) -> Tuple[str, Optional[str]]:
        """Optimize LIKE patterns where possible."""
        # Convert LIKE 'prefix%' to >= and < for better index usage
        # This is a complex optimization - placeholder for now
        return query, None

    def _optimize_null_checks(self, query: str) -> Tuple[str, Optional[str]]:
        """Optimize NULL checks."""
        # Convert != NULL to IS NOT NULL
        if re.search(r'(?:!=|<>)\s*null', query, re.IGNORECASE):
            optimized = re.sub(
                r"(\w+)\s*(?:!=|<>)\s*null",
                r"\1 IS NOT NULL",
                query,
                flags=re.IGNORECASE
            )
            return optimized, "Converted != NULL to IS NOT NULL"

        # Convert = NULL to IS NULL
        if re.search(r'=\s*null', query, re.IGNORECASE):
            optimized = re.sub(
                r"(\w+)\s*=\s*null",
                r"\1 IS NULL",
                query,
                flags=re.IGNORECASE
            )
            return optimized, "Converted = NULL to IS NULL"

        return query, None

    def _optimize_in_clauses(self, query: str) -> Tuple[str, Optional[str]]:
        """Optimize large IN clauses."""
        # For very large IN clauses, suggest using a temporary table or VALUES
        # This is a placeholder - actual optimization would require more context
        return query, None


def create_optimizer(connection_pool=None) -> QueryOptimizer:
    """
    Factory function for QueryOptimizer.

    Args:
        connection_pool: Optional database connection pool

    Returns:
        Configured QueryOptimizer instance
    """
    return QueryOptimizer(connection_pool=connection_pool)

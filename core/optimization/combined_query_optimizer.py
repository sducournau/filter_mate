# -*- coding: utf-8 -*-
"""
Combined Query Optimizer for FilterMate

Optimizes multi-step filter expressions for PostgreSQL, Spatialite, and OGR
by detecting and reusing previous filter results.

Problem Solved:
When a user applies successive filters, the naive approach combines them with AND:
    PostgreSQL: ("fid" IN (SELECT "pk" FROM "mv_xxx")) AND (EXISTS (...ST_Intersects...))
    Spatialite: ("fid" IN (1, 2, 3, ...)) AND (Intersects(geom, ...))

This is slow because all conditions are evaluated for every feature.

Solution (by backend):

PostgreSQL:
    Rewrite queries to use the materialized view as the SOURCE:
        Instead of: base_table WHERE (IN mv_xxx) AND (spatial_condition)
        Use:       mv_xxx WHERE (spatial_condition) -> new result set

Spatialite/OGR:
    1. Ensure FID check is evaluated FIRST (left-to-right short-circuit)
    2. Convert large FID lists to range expressions when consecutive
    3. Restructure expressions for optimal query planning

Key Optimizations:
1. MV_REUSE (PostgreSQL) - Use existing MV as source table
2. FID_LIST_OPTIMIZE (Spatialite/OGR) - Restructure FID + spatial queries
3. RANGE_OPTIMIZE (Spatialite/OGR) - Convert FID lists to range checks
4. EXPRESSION_SIMPLIFY - Flatten nested parentheses and redundant AND/OR
5. CACHE_HIT - Reuse previously optimized expressions

Performance Benefits:
- 10-50x faster for PostgreSQL with MV reuse
- 2-5x faster for Spatialite/OGR with FID optimizations
- Reduced memory usage (smaller intermediate result sets)

Usage:
    from ...core.optimization import CombinedQueryOptimizer
    optimizer = CombinedQueryOptimizer()
    optimized = optimizer.optimize_combined_expression(
        old_subset='"fid" IN (SELECT "pk" FROM "public"."filtermate_mv_xxx")',
        new_expression='EXISTS (SELECT 1 FROM ... ST_Intersects(...))',
        combine_operator='AND',
        layer_props={...}
    )

v2.8.0 - Multi-step filter optimization (January 2026)
"""

import re
import hashlib
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass
from enum import Enum, auto

from ...infrastructure.logging import get_logger
# DEFAULT_TEMP_SCHEMA is hardcoded - no longer imported from constants

logger = get_logger(__name__)

# Use dedicated FilterMate temp schema for all MVs
# Constant defined locally after removal of modules.constants dependency
DEFAULT_TEMP_SCHEMA = 'filtermate_temp'
FILTERMATE_MV_SCHEMA = DEFAULT_TEMP_SCHEMA


class OptimizationType(Enum):
    """Types of query optimizations applied."""
    NONE = auto()                      # No optimization possible
    MV_REUSE = auto()                  # Reuse materialized view as source (PostgreSQL)
    FID_LIST_OPTIMIZE = auto()         # Optimize FID list combination (Spatialite/OGR)
    SUBQUERY_MERGE = auto()            # Merge subqueries into single query
    EXPRESSION_SIMPLIFY = auto()       # Simplify expression structure
    CACHE_HIT = auto()                 # Result from cache
    RANGE_OPTIMIZE = auto()            # Convert IN list to range (Spatialite/OGR)
    SOURCE_MV_OPTIMIZE = auto()        # Create source MV with pre-computed buffer (PostgreSQL)


@dataclass
class MaterializedViewInfo:
    """Information about a detected materialized view reference."""
    schema: str
    view_name: str
    primary_key: str
    full_match: str  # The full IN clause match

    @property
    def qualified_name(self) -> str:
        """Get fully qualified view name."""
        return f'"{self.schema}"."{self.view_name}"'


@dataclass
class FidListInfo:
    """Information about a detected FID IN list (Spatialite/OGR pattern)."""
    primary_key: str
    fid_list: List[int]
    full_match: str
    is_range_based: bool = False  # True if uses >= AND <= pattern
    min_fid: Optional[int] = None
    max_fid: Optional[int] = None


@dataclass
class ExistsClauseInfo:
    """Information about a detected EXISTS clause."""
    source_table: str
    source_schema: str
    source_alias: str
    spatial_predicate: str  # ST_Intersects, ST_Within, etc.
    target_geometry: str
    source_geometry: str
    buffer_expression: Optional[str] = None
    full_match: str = ""
    source_fid_list: Optional[List[int]] = None  # FID filter inside EXISTS
    buffer_distance: Optional[float] = None  # Extracted buffer distance
    buffer_style: Optional[str] = None  # Buffer style params (e.g., 'quad_segs=1')


@dataclass
class SpatialPredicateInfo:
    """Information about a spatial predicate (Spatialite style)."""
    predicate: str  # Intersects, Contains, etc.
    target_geometry_col: str
    source_wkt_or_geom: str
    buffer_distance: Optional[float] = None
    full_match: str = ""


@dataclass
class SourceMVInfo:
    """Information about source MV with pre-computed buffer to create."""
    schema: str
    view_name: str  # e.g., filtermate_src_abc123
    source_table: str
    source_schema: str
    source_geom_col: str
    fid_column: str
    fid_list: List[int]
    buffer_distance: str
    buffer_style: str
    create_sql: str  # Full CREATE MATERIALIZED VIEW statement

    @property
    def qualified_name(self) -> str:
        return f'"{self.schema}"."{self.view_name}"'


@dataclass
class OptimizationResult:
    """Result of query optimization."""
    success: bool
    optimized_expression: str
    optimization_type: OptimizationType
    original_expression: str
    performance_hint: str = ""
    mv_info: Optional[MaterializedViewInfo] = None
    fid_info: Optional[FidListInfo] = None
    source_mv_info: Optional[SourceMVInfo] = None  # Source MV to create

    # Statistics
    estimated_speedup: float = 1.0  # Multiplier (e.g., 10.0 = 10x faster)
    complexity_reduction: float = 0.0  # Percentage reduction in query complexity


class CombinedQueryOptimizer:
    """
    Optimizes combined filter expressions for PostgreSQL, Spatialite, and OGR.

    Detects patterns from successive filter operations and rewrites
    queries to use more efficient execution strategies.

    v2.9.0: Enhanced multi-step optimization
    - Detects MV + EXISTS with inline FID lists and rewrites for efficiency
    - Creates source selection MVs for large FID lists (> SOURCE_FID_MV_THRESHOLD)
    - Pre-computes ST_Buffer in subquery to avoid per-row recalculation
    """

    # ============== Configuration Thresholds ==============

    # Threshold for converting inline FID list to source selection MV
    # When EXISTS contains more than this many FIDs, create a temp MV instead
    SOURCE_FID_MV_THRESHOLD = 50

    # Threshold for converting FID list to range expression
    # Only applies when FIDs are mostly consecutive (>50% coverage)
    FID_RANGE_THRESHOLD = 20

    # Maximum FIDs to keep inline (for small lists, inline is faster)
    MAX_INLINE_FIDS = 30

    # ============== Regex patterns for detecting materialized view references ==============
    # Matches: "fid" IN (SELECT "pk" FROM "public"."filtermate_mv_xxx")
    MV_IN_PATTERN = re.compile(
        r'"?(\w+)"?\s+IN\s*\(\s*SELECT\s+"?(\w+)"?\s+FROM\s+"?(\w+)"?\s*\.\s*"?(\w+)"?\s*\)',
        re.IGNORECASE
    )

    # Pattern for filtermate materialized views specifically
    # Matches: "fid" IN (SELECT "pk" FROM "public"."fm_temp_mv_xxx") or fm_temp_*
    FILTERMATE_MV_PATTERN = re.compile(
        r'"?(\w+)"?\s+IN\s*\(\s*SELECT\s+"?(\w+)"?\s+FROM\s+"?(\w+)"?\s*\.\s*"?((?:fm_temp_|filtermate_)\w+)"?\s*\)',
        re.IGNORECASE
    )

    # Pattern for EXISTS clauses with spatial predicates
    # More flexible pattern to match various spatial predicate formats
    # Matches: EXISTS (SELECT 1 FROM "schema"."table" AS alias WHERE ST_Predicate("target"."geom", ...))
    EXISTS_SPATIAL_PATTERN = re.compile(
        r'EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+"?(\w+)"?\s*\.\s*"?(\w+)"?\s+AS\s+(\w+)\s+WHERE\s+(ST_\w+)\s*\(\s*"?(\w+)"?\s*\.\s*"?(\w+)"?\s*,\s*(.+?)\s*\)\s*(?:AND\s+(.+?))?\s*\)',
        re.IGNORECASE | re.DOTALL
    )

    # Pattern for EXISTS with FID filter inside (more specific for optimization)
    # Matches: EXISTS (SELECT 1 FROM ... WHERE ST_Intersects(...) AND (__source."fid" IN (...)))
    EXISTS_WITH_FID_PATTERN = re.compile(
        r'EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+"?(\w+)"?\s*\.\s*"?(\w+)"?\s+AS\s+(\w+)\s+WHERE\s+(ST_\w+)\s*\([^)]+\)\s*AND\s*\(\s*\3\s*\.\s*"?(\w+)"?\s+IN\s*\(\s*([\d\s,]+)\s*\)\s*\)\s*\)',
        re.IGNORECASE | re.DOTALL
    )

    # Enhanced pattern for EXISTS with large FID lists and ST_Buffer
    # Matches the full EXISTS clause including buffer parameters
    # Example: EXISTS (SELECT 1 FROM "public"."table" AS __source
    #          WHERE ST_Intersects("target"."geom", ST_Buffer(__source."geom", 50.0, 'quad_segs=5'))
    #          AND (__source."fid" IN (1, 2, 3, ...)))
    EXISTS_BUFFER_FID_PATTERN = re.compile(
        r'EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+"([^"]+)"\s*\.\s*"([^"]+)"\s+AS\s+(\w+)\s+'
        r'WHERE\s+(ST_\w+)\s*\(\s*"([^"]+)"\s*\.\s*"([^"]+)"\s*,\s*'
        r'ST_Buffer\s*\(\s*\3\s*\.\s*"([^"]+)"\s*,\s*([^,)]+)\s*(?:,\s*[\'"]([^"\']+)[\'"])?\s*\)\s*\)\s*'
        r'AND\s*\(\s*\3\s*\.\s*"(\w+)"\s+IN\s*\(\s*([\d\s,]+)\s*\)\s*\)\s*\)',
        re.IGNORECASE | re.DOTALL
    )

    # Pattern for ST_Buffer in EXISTS - more flexible
    BUFFER_PATTERN = re.compile(
        r'ST_Buffer\s*\(\s*(\w+)\s*\.\s*"?(\w+)"?\s*,\s*([^,)]+)\s*(?:,\s*[\'"]([^"\']+)[\'"])?\s*\)',
        re.IGNORECASE
    )

    # ============== Spatialite/OGR Patterns ==============

    # Pattern for FID IN list (Spatialite/OGR style)
    # Matches: "fid" IN (1, 2, 3, 45, 67) or "pk_col" IN (1,2,3)
    FID_LIST_PATTERN = re.compile(
        r'"?(\w+)"?\s+IN\s*\(\s*((?:\d+\s*,\s*)*\d+)\s*\)',
        re.IGNORECASE
    )

    # Pattern for range-based FID filtering
    # Matches: ("pk" >= 1 AND "pk" <= 100)
    FID_RANGE_PATTERN = re.compile(
        r'\(\s*"?(\w+)"?\s*>=\s*(\d+)\s+AND\s+"?\1"?\s*<=\s*(\d+)\s*\)',
        re.IGNORECASE
    )

    # Pattern for Spatialite spatial predicates (no ST_ prefix)
    # Matches: Intersects(geometry, MakePoint(x, y)) or Intersects(geometry, geom_column)
    SPATIALITE_SPATIAL_PATTERN = re.compile(
        r'(Intersects|Contains|Within|Touches|Overlaps|Crosses)\s*\(\s*"?(\w+)"?\s*,\s*(.+?)\s*\)',
        re.IGNORECASE
    )

    # Pattern for Spatialite EXISTS with spatial predicate
    # Matches: EXISTS (SELECT 1 FROM table WHERE Intersects(...))
    SPATIALITE_EXISTS_PATTERN = re.compile(
        r'EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+"?(\w+)"?\s+(?:AS\s+(\w+)\s+)?WHERE\s+(Intersects|Contains|Within)\s*\(\s*(.+?)\s*\)\s*\)',
        re.IGNORECASE | re.DOTALL
    )

    # Pattern for Buffer in Spatialite
    # Matches: Buffer(geom, distance) or ST_Buffer(geom, distance)
    SPATIALITE_BUFFER_PATTERN = re.compile(
        r'(?:ST_)?Buffer\s*\(\s*"?(\w+)"?\s*,\s*([^)]+)\s*\)',
        re.IGNORECASE
    )

    def __init__(self, cache_size: int = 50):
        """
        Initialize the optimizer.

        Args:
            cache_size: Maximum number of optimized expressions to cache
        """
        self._cache: Dict[str, OptimizationResult] = {}
        self._cache_size = cache_size
        self._optimization_count = 0
        self._cache_hits = 0

        logger.info("✓ CombinedQueryOptimizer initialized")

    def optimize_combined_expression(
        self,
        old_subset: str,
        new_expression: str,
        combine_operator: str = 'AND',
        layer_props: Optional[Dict[str, Any]] = None,
        target_table: Optional[str] = None,
        target_schema: Optional[str] = None,
        primary_key: Optional[str] = None
    ) -> OptimizationResult:
        """
        Optimize a combined filter expression.

        Args:
            old_subset: Existing subset string (may contain MV reference)
            new_expression: New filter expression to combine
            combine_operator: SQL operator ('AND', 'OR')
            layer_props: Layer properties dict
            target_table: Target table name
            target_schema: Target schema name
            primary_key: Primary key column name

        Returns:
            OptimizationResult with optimized expression or original if no optimization possible
        """
        if not old_subset or not new_expression:
            return OptimizationResult(
                success=False,
                optimized_expression=new_expression or old_subset or "",
                optimization_type=OptimizationType.NONE,
                original_expression=f"({old_subset}) {combine_operator} ({new_expression})"
            )

        # Check cache first
        cache_key = self._get_cache_key(old_subset, new_expression, combine_operator)
        if cache_key in self._cache:
            self._cache_hits += 1
            cached = self._cache[cache_key]
            logger.debug("Cache HIT for combined query optimization")
            return OptimizationResult(
                success=cached.success,
                optimized_expression=cached.optimized_expression,
                optimization_type=OptimizationType.CACHE_HIT,
                original_expression=cached.original_expression,
                performance_hint=cached.performance_hint,
                mv_info=cached.mv_info
            )

        # Build original combined expression for reference
        f"({old_subset}) {combine_operator} ({new_expression})"

        # Extract layer info from props
        if layer_props:
            target_table = target_table or layer_props.get('layer_name')
            target_schema = target_schema or layer_props.get('layer_schema', 'public')
            primary_key = primary_key or layer_props.get('primary_key_name', 'fid')

        # Try optimization strategies in order of effectiveness

        # 1. Try PostgreSQL MV reuse optimization
        result = self._try_mv_reuse_optimization(
            old_subset, new_expression, combine_operator,
            target_table, target_schema, primary_key
        )

        # 2. Try MV + EXISTS with large FID list optimization
        # This handles the case: (IN mv_step1) AND (EXISTS ... AND (fid IN (long list)))
        if not result.success:
            result = self._try_mv_exists_fid_optimization(
                old_subset, new_expression, combine_operator,
                target_table, target_schema, primary_key
            )

        # 3. Try Spatialite/OGR FID list optimization
        if not result.success:
            result = self._try_fid_list_optimization(
                old_subset, new_expression, combine_operator, primary_key
            )

        # 4. Try simpler optimizations
        if not result.success:
            # Try simpler optimizations
            result = self._try_expression_simplification(
                old_subset, new_expression, combine_operator
            )

        # Cache result
        self._cache_result(cache_key, result)
        self._optimization_count += 1

        if result.success:
            logger.info(
                f"✓ Query optimized ({result.optimization_type.name}): "
                f"~{result.estimated_speedup:.1f}x speedup expected"
            )

        return result

    def _try_mv_reuse_optimization(
        self,
        old_subset: str,
        new_expression: str,
        combine_operator: str,
        target_table: Optional[str],
        target_schema: Optional[str],
        primary_key: Optional[str]
    ) -> OptimizationResult:
        """
        Try to optimize by reusing materialized view as source.

        Instead of:
            target_table WHERE (pk IN (SELECT pk FROM mv_xxx)) AND (EXISTS (...))

        Generate:
            pk IN (SELECT pk FROM mv_xxx WHERE pk IN (
                SELECT pk FROM target_table WHERE EXISTS (...)
            ))

        Or better - create new MV based on existing MV:
            New spatial filter uses mv_xxx as source instead of full table
        """
        original = f"({old_subset}) {combine_operator} ({new_expression})"

        # Detect materialized view in old_subset
        mv_info = self._detect_materialized_view(old_subset)
        if not mv_info:
            return OptimizationResult(
                success=False,
                optimized_expression=original,
                optimization_type=OptimizationType.NONE,
                original_expression=original
            )

        # Detect EXISTS clause with spatial predicate in new_expression
        exists_info = self._detect_exists_clause(new_expression)

        if exists_info and combine_operator.upper() == 'AND':
            # OPTIMAL CASE: MV + EXISTS with spatial predicate
            # Rewrite to use MV as the constraint for the EXISTS
            optimized = self._rewrite_mv_exists_query(
                mv_info, exists_info, target_table, target_schema, primary_key
            )

            if optimized:
                return OptimizationResult(
                    success=True,
                    optimized_expression=optimized,
                    optimization_type=OptimizationType.MV_REUSE,
                    original_expression=original,
                    performance_hint=(
                        f"Reused materialized view '{mv_info.view_name}' as filter constraint. "
                        f"Spatial predicate now only evaluates {mv_info.view_name} features."
                    ),
                    mv_info=mv_info,
                    estimated_speedup=10.0,  # Typical improvement
                    complexity_reduction=0.5
                )

        # Fallback: Simpler optimization - just ensure MV is referenced efficiently
        return self._optimize_mv_reference(mv_info, new_expression, combine_operator, original)

    def _try_mv_exists_fid_optimization(
        self,
        old_subset: str,
        new_expression: str,
        combine_operator: str,
        target_table: Optional[str],
        target_schema: Optional[str],
        primary_key: Optional[str]
    ) -> OptimizationResult:
        """
        v2.9.0: Optimize MV + EXISTS with large FID list pattern.

        This handles the specific case where:
        - old_subset contains a MV reference: "fid" IN (SELECT "pk" FROM "public"."filtermate_mv_xxx")
        - new_expression contains an EXISTS with a large inline FID list

        Original (slow):
            ("fid" IN (SELECT "pk" FROM "public"."filtermate_mv_xxx"))
            AND
            (EXISTS (SELECT 1 FROM "public"."source" AS __source
                     WHERE ST_Intersects("target"."geom", ST_Buffer(__source."geom", 50))
                     AND (__source."fid" IN (1, 2, 3, ... 300+ FIDs))))

        Optimized (fast):
            "fid" IN (
                SELECT mv.pk FROM "public"."filtermate_mv_xxx" AS mv
                WHERE EXISTS (
                    SELECT 1 FROM (
                        SELECT "geom", ST_Buffer("geom", 50, 'quad_segs=5') AS geom_buffered
                        FROM "public"."source"
                        WHERE "fid" IN (1, 2, 3, ...)
                    ) AS src
                    WHERE ST_Intersects(mv.geom, src.geom_buffered)
                )
            )

        Benefits:
        - ST_Buffer computed only once per source feature (not per comparison)
        - Spatial comparison limited to MV features (already filtered)
        - PostgreSQL can use spatial indexes on both sides
        - For very large FID lists (>50), can create temp MV instead
        """
        original = f"({old_subset}) {combine_operator} ({new_expression})"

        # Only optimize AND combinations
        if combine_operator.upper() != 'AND':
            return OptimizationResult(
                success=False,
                optimized_expression=original,
                optimization_type=OptimizationType.NONE,
                original_expression=original
            )

        # Detect MV in old_subset
        mv_info = self._detect_materialized_view(old_subset)
        if not mv_info:
            return OptimizationResult(
                success=False,
                optimized_expression=original,
                optimization_type=OptimizationType.NONE,
                original_expression=original
            )

        # Try to match the enhanced EXISTS pattern with buffer and FID list
        match = self.EXISTS_BUFFER_FID_PATTERN.search(new_expression)

        if match:
            # Extract components from match
            source_schema = match.group(1)
            source_table = match.group(2)
            match.group(3)
            spatial_predicate = match.group(4)
            match.group(5)
            target_geom_col = match.group(6)
            source_geom_col = match.group(7)
            buffer_distance = match.group(8).strip()
            buffer_style = match.group(9) if match.group(9) else 'quad_segs=5'
            fid_column = match.group(10)
            fid_list_str = match.group(11)

            # Parse FID list
            try:
                fid_list = [int(fid.strip()) for fid in fid_list_str.split(',') if fid.strip()]
            except ValueError:
                logger.warning("Could not parse FID list, skipping optimization")
                return OptimizationResult(
                    success=False,
                    optimized_expression=original,
                    optimization_type=OptimizationType.NONE,
                    original_expression=original
                )

            fid_count = len(fid_list)
            logger.info(f"🔍 v2.9.0: Detected MV + EXISTS + {fid_count} FIDs pattern")

            # Build optimized subquery (may create source MV if threshold exceeded)
            optimized, source_mv_info = self._build_mv_buffered_subquery(
                mv_info=mv_info,
                source_schema=source_schema,
                source_table=source_table,
                source_geom_col=source_geom_col,
                target_geom_col=target_geom_col,
                spatial_predicate=spatial_predicate,
                buffer_distance=buffer_distance,
                buffer_style=buffer_style,
                fid_column=fid_column,
                fid_list=fid_list,
                primary_key=primary_key or 'fid'
            )

            # Determine optimization type and hint based on whether source MV will be created
            if source_mv_info:
                opt_type = OptimizationType.SOURCE_MV_OPTIMIZE
                hint = f"Source MV with pre-computed buffer ({fid_count} FIDs → {source_mv_info.view_name})"
                speedup = 20.0  # Highest speedup with indexed source MV
            elif fid_count <= self.MAX_INLINE_FIDS:
                opt_type = OptimizationType.MV_REUSE
                hint = f"Restructured query with pre-computed buffer ({fid_count} FIDs inline)"
                speedup = 5.0
            else:
                opt_type = OptimizationType.MV_REUSE
                hint = f"Restructured query with pre-computed buffer ({fid_count} FIDs, buffer pre-computed)"
                speedup = 10.0

            if optimized:
                # Clean up whitespace
                optimized = ' '.join(optimized.split())

                return OptimizationResult(
                    success=True,
                    optimized_expression=optimized,
                    optimization_type=opt_type,
                    original_expression=original,
                    performance_hint=hint,
                    mv_info=mv_info,
                    source_mv_info=source_mv_info,
                    estimated_speedup=speedup,
                    complexity_reduction=0.7 if source_mv_info else 0.6
                )

        # Pattern not matched - try simpler FID list extraction
        fid_match = re.search(
            r'__source\s*\.\s*"?(\w+)"?\s+IN\s*\(\s*([\d\s,]+)\s*\)',
            new_expression,
            re.IGNORECASE
        )

        if fid_match:
            fid_column = fid_match.group(1)
            fid_list_str = fid_match.group(2)
            try:
                fid_list = [int(fid.strip()) for fid in fid_list_str.split(',') if fid.strip()]
                fid_count = len(fid_list)

                if fid_count > self.FID_RANGE_THRESHOLD:
                    # Try to convert to range if FIDs are mostly consecutive
                    range_result = self._try_convert_fid_to_range(fid_list, fid_column)
                    if range_result:
                        # Replace inline FID list with range expression
                        optimized = new_expression.replace(
                            fid_match.group(0),
                            f'{range_result}'
                        )
                        optimized = f"({old_subset}) AND ({optimized})"
                        optimized = ' '.join(optimized.split())

                        return OptimizationResult(
                            success=True,
                            optimized_expression=optimized,
                            optimization_type=OptimizationType.RANGE_OPTIMIZE,
                            original_expression=original,
                            performance_hint=f"Converted {fid_count} FIDs to range expression",
                            mv_info=mv_info,
                            estimated_speedup=2.0,
                            complexity_reduction=0.3
                        )
            except ValueError:
                pass

        return OptimizationResult(
            success=False,
            optimized_expression=original,
            optimization_type=OptimizationType.NONE,
            original_expression=original
        )

    def _build_mv_buffered_subquery(
        self,
        mv_info: MaterializedViewInfo,
        source_schema: str,
        source_table: str,
        source_geom_col: str,
        target_geom_col: str,
        spatial_predicate: str,
        buffer_distance: str,
        buffer_style: str,
        fid_column: str,
        fid_list: List[int],
        primary_key: str
    ) -> Tuple[str, Optional[SourceMVInfo]]:
        """
        Build optimized subquery that pre-computes buffer.

        This structure ensures:
        1. ST_Buffer is computed only once per source feature
        2. Spatial comparison is limited to MV features
        3. PostgreSQL can use spatial indexes efficiently

        Returns:
            Tuple of (optimized_expression, source_mv_info)
            source_mv_info is None if FID count < SOURCE_FID_MV_THRESHOLD
        """
        fid_count = len(fid_list)
        ', '.join(str(fid) for fid in fid_list)
        source_mv_info = None

        # Use FilterMate temp schema for all MVs instead of source schema
        mv_schema = FILTERMATE_MV_SCHEMA

        # If FID count exceeds threshold, create a source MV with pre-computed buffer
        if fid_count > self.SOURCE_FID_MV_THRESHOLD:
            # Generate unique source MV name (unified fm_temp_src_ prefix)
            fid_hash = hashlib.md5(','.join(str(f, usedforsecurity=False) for f in sorted(fid_list)).encode()).hexdigest()[:8]
            src_mv_name = f"fm_temp_src_{fid_hash}"

            # Build CREATE MATERIALIZED VIEW SQL for source selection
            # Use filtermate temp schema instead of source schema
            create_sql = '''CREATE MATERIALIZED VIEW IF NOT EXISTS "{mv_schema}"."{src_mv_name}" AS
    SELECT "{fid_column}",
           "{source_geom_col}" AS geom,
           ST_Buffer("{source_geom_col}", {buffer_distance}, '{buffer_style}') AS geom_buffered
    FROM "{source_schema}"."{source_table}"
    WHERE "{fid_column}" IN ({fid_list_str})
    WITH DATA;'''

            source_mv_info = SourceMVInfo(
                schema=mv_schema,  # Use temp schema
                view_name=src_mv_name,
                source_table=source_table,
                source_schema=source_schema,
                source_geom_col=source_geom_col,
                fid_column=fid_column,
                fid_list=fid_list,
                buffer_distance=buffer_distance,
                buffer_style=buffer_style,
                create_sql=create_sql
            )

            # Build simplified query using the source MV
            optimized = '''"{primary_key}" IN (
    SELECT mv."pk"
    FROM {mv_info.qualified_name} AS mv
    WHERE EXISTS (
        SELECT 1
        FROM "{mv_schema}"."{src_mv_name}" AS __src
        WHERE {spatial_predicate}(mv."geom", __src.geom_buffered)
    )
)'''
            logger.info(f"🔧 v2.9.0: Will create source MV '{mv_schema}.{src_mv_name}' for {fid_count} FIDs with pre-computed buffer")
        else:
            # Standard inline subquery for small FID lists
            optimized = '''"{primary_key}" IN (
    SELECT mv."pk"
    FROM {mv_info.qualified_name} AS mv
    WHERE EXISTS (
        SELECT 1
        FROM (
            SELECT "{source_geom_col}",
                   ST_Buffer("{source_geom_col}", {buffer_distance}, '{buffer_style}') AS geom_buffered
            FROM "{source_schema}"."{source_table}"
            WHERE "{fid_column}" IN ({fid_list_str})
        ) AS __src
        WHERE {spatial_predicate}(mv."geom", __src.geom_buffered)
    )
)'''

        return optimized, source_mv_info

    def _try_convert_fid_to_range(
        self,
        fid_list: List[int],
        fid_column: str
    ) -> Optional[str]:
        """
        Try to convert FID list to range expression if mostly consecutive.

        Returns optimized expression like:
            (__source."fid" >= 100 AND __source."fid" <= 500)
        Or with exclusions:
            (__source."fid" >= 100 AND __source."fid" <= 500 AND __source."fid" NOT IN (105, 110))

        Returns None if range optimization is not beneficial.
        """
        if len(fid_list) < self.FID_RANGE_THRESHOLD:
            return None

        fids = sorted(fid_list)
        min_fid = fids[0]
        max_fid = fids[-1]

        # Calculate coverage
        range_size = max_fid - min_fid + 1
        coverage = len(fids) / range_size

        # Only optimize if >50% coverage
        if coverage < 0.5:
            return None

        # Find gaps
        full_range = set(range(min_fid, max_fid + 1))
        actual_fids = set(fids)
        gaps = sorted(full_range - actual_fids)

        if len(gaps) == 0:
            # Perfect range
            return f'(__source."{fid_column}" >= {min_fid} AND __source."{fid_column}" <= {max_fid})'
        elif len(gaps) < len(fids) / 4:
            # Few gaps - use range with exclusions
            gaps_str = ', '.join(str(g) for g in gaps)
            return (f'(__source."{fid_column}" >= {min_fid} AND __source."{fid_column}" <= {max_fid} '
                    f'AND __source."{fid_column}" NOT IN ({gaps_str}))')
        else:
            # Too many gaps
            return None

    def _detect_materialized_view(self, expression: str) -> Optional[MaterializedViewInfo]:
        """
        Detect materialized view reference in expression.

        Looks for patterns like:
            "fid" IN (SELECT "pk" FROM "schema"."filtermate_mv_xxx")
            "fid" IN (SELECT "pk" FROM "public"."mv_0c6823bc")
        """
        # Try FilterMate-specific pattern first
        # Pattern captures: (1)pk_column, (2)select_column, (3)schema, (4)view_name
        match = self.FILTERMATE_MV_PATTERN.search(expression)
        if match:
            return MaterializedViewInfo(
                primary_key=match.group(1),  # The column in IN clause (e.g., "fid")
                schema=match.group(3),       # Schema name (e.g., "public")
                view_name=match.group(4),    # View name (e.g., "filtermate_mv_xxx")
                full_match=match.group(0)
            )

        # Try generic MV pattern
        match = self.MV_IN_PATTERN.search(expression)
        if match:
            view_name = match.group(4)
            # Check if it looks like a FilterMate view
            if 'mv_' in view_name.lower() or 'filtermate' in view_name.lower():
                return MaterializedViewInfo(
                    primary_key=match.group(1),
                    schema=match.group(3),
                    view_name=view_name,
                    full_match=match.group(0)
                )

        return None

    def _detect_exists_clause(self, expression: str) -> Optional[ExistsClauseInfo]:
        """
        Detect EXISTS clause with spatial predicate.

        Looks for patterns like:
            EXISTS (SELECT 1 FROM "schema"."table" AS alias
                    WHERE ST_Intersects("target"."geom", ST_Buffer(alias."geom", 50))
                    AND (alias."fid" IN (1, 2, 3)))

        Enhanced to extract:
        - Buffer distance and style parameters
        - Source FID filter list (for pre-filtering optimization)
        """
        match = self.EXISTS_SPATIAL_PATTERN.search(expression)
        if not match:
            return None

        source_schema = match.group(1)
        source_table = match.group(2)
        source_alias = match.group(3)
        spatial_predicate = match.group(4)
        target_geometry = f"{match.group(5)}.{match.group(6)}"
        source_geometry_expr = match.group(7)
        additional_conditions = match.group(8) if len(match.groups()) >= 8 else None

        # Check for buffer in source geometry - extract distance and style
        buffer_expr = None
        buffer_distance = None
        buffer_style = None
        buffer_match = self.BUFFER_PATTERN.search(source_geometry_expr)
        if buffer_match:
            buffer_expr = source_geometry_expr
            try:
                buffer_distance = float(buffer_match.group(3).strip())
            except (ValueError, TypeError):
                pass
            buffer_style = buffer_match.group(4) if len(buffer_match.groups()) >= 4 else None

        # Check for FID filter in additional conditions or full expression
        source_fid_list = None
        fid_pattern = re.compile(
            rf'{re.escape(source_alias)}\s*\.\s*"?(\w+)"?\s+IN\s*\(\s*([\d\s,]+)\s*\)',
            re.IGNORECASE
        )
        fid_match = fid_pattern.search(expression)
        if fid_match:
            try:
                fid_string = fid_match.group(2)
                source_fid_list = [int(fid.strip()) for fid in fid_string.split(',') if fid.strip()]
            except ValueError:
                pass

        return ExistsClauseInfo(
            source_table=source_table,
            source_schema=source_schema,
            source_alias=source_alias,
            spatial_predicate=spatial_predicate,
            target_geometry=target_geometry,
            source_geometry=source_geometry_expr,
            buffer_expression=buffer_expr,
            full_match=match.group(0),
            source_fid_list=source_fid_list,
            buffer_distance=buffer_distance,
            buffer_style=buffer_style
        )

    def _rewrite_mv_exists_query(
        self,
        mv_info: MaterializedViewInfo,
        exists_info: ExistsClauseInfo,
        target_table: Optional[str],
        target_schema: Optional[str],
        primary_key: Optional[str]
    ) -> Optional[str]:
        """
        Rewrite query to use MV as constraint for EXISTS.

        The key insight: Instead of evaluating EXISTS for ALL features
        and then filtering by MV, we:
        1. Only evaluate EXISTS for features that are IN the MV
        2. This dramatically reduces the number of spatial comparisons

        Enhanced optimizations (v2.9.0):
        3. Pre-compute ST_Buffer in a subquery to avoid recalculation
        4. Apply source FID filter BEFORE spatial predicate
        5. Use the MV's spatial index directly

        Original (slow):
            WHERE (pk IN (SELECT pk FROM mv)) AND (EXISTS (SELECT 1 FROM source WHERE ST_Intersects(...)))

        Optimized with buffer pre-computation:
            WHERE pk IN (
                SELECT mv.pk FROM mv
                WHERE EXISTS (
                    SELECT 1 FROM (
                        SELECT geom, ST_Buffer(geom, distance, style) AS geom_buffered
                        FROM source WHERE fid IN (filtered_fids)
                    ) AS __source
                    WHERE ST_Intersects(mv.geometry, __source.geom_buffered)
                )
            )

        This approach:
        - Computes ST_Buffer only once per source feature (not per comparison)
        - Filters source features BEFORE expensive spatial operations
        - Uses MV's spatial index for the final intersection check
        """
        if not primary_key:
            primary_key = mv_info.primary_key

        # Extract geometry column from target geometry reference
        geom_column = self._extract_geometry_column(exists_info.target_geometry)

        # Determine if we can apply advanced buffer optimization
        has_buffer = exists_info.buffer_expression is not None
        has_source_filter = exists_info.source_fid_list is not None and len(exists_info.source_fid_list) > 0

        if has_buffer and has_source_filter:
            # OPTIMAL CASE: Buffer + FID filter - use subquery with pre-computed buffer
            optimized = self._build_optimized_buffer_query(
                mv_info, exists_info, geom_column, primary_key
            )
        elif has_source_filter:
            # Source filter without buffer - just reorder conditions
            optimized = self._build_filtered_source_query(
                mv_info, exists_info, geom_column, primary_key
            )
        else:
            # Standard optimization - use MV as source
            optimized = self._build_mv_source_query(
                mv_info, exists_info, geom_column, primary_key
            )

        # Clean up whitespace for logging
        optimized_clean = ' '.join(optimized.split())

        logger.debug(f"Optimized query (MV-based EXISTS): {optimized_clean[:200]}...")

        return optimized_clean

    def _build_optimized_buffer_query(
        self,
        mv_info: MaterializedViewInfo,
        exists_info: ExistsClauseInfo,
        geom_column: str,
        primary_key: str
    ) -> str:
        """
        Build query with pre-computed buffer in subquery.

        This optimization avoids computing ST_Buffer for each MV feature × source feature comparison.
        Instead, buffer is computed once per source feature.

        Estimated speedup: 5-20x depending on source and MV sizes.
        """
        # Extract geometry column from buffer expression
        buffer_match = self.BUFFER_PATTERN.search(exists_info.buffer_expression or "")
        buffer_match.group(2) if buffer_match else "geometrie"

        # Build buffer expression for subquery
        exists_info.buffer_distance or 50.0
        f", '{exists_info.buffer_style}'" if exists_info.buffer_style else ""

        # Build FID filter clause
        ', '.join(str(fid) for fid in (exists_info.source_fid_list or []))

        optimized = '''"{primary_key}" IN (
    SELECT mv."{primary_key}"
    FROM {mv_info.qualified_name} AS mv
    WHERE EXISTS (
        SELECT 1
        FROM (
            SELECT "{source_geom_col}",
                   ST_Buffer("{source_geom_col}", {buffer_distance}{buffer_style}) AS geom_buffered
            FROM "{exists_info.source_schema}"."{exists_info.source_table}"
            WHERE "fid" IN ({fid_list_str})
        ) AS {exists_info.source_alias}
        WHERE {exists_info.spatial_predicate}(
            mv."{geom_column}",
            {exists_info.source_alias}.geom_buffered
        )
    )
)'''
        return optimized.strip()

    def _build_filtered_source_query(
        self,
        mv_info: MaterializedViewInfo,
        exists_info: ExistsClauseInfo,
        geom_column: str,
        primary_key: str
    ) -> str:
        """
        Build query with source FID filter applied first.

        Ensures the FID filter is evaluated BEFORE the spatial predicate.
        """
        ', '.join(str(fid) for fid in (exists_info.source_fid_list or []))

        optimized = '''"{primary_key}" IN (
    SELECT mv."{primary_key}"
    FROM {mv_info.qualified_name} AS mv
    WHERE EXISTS (
        SELECT 1
        FROM "{exists_info.source_schema}"."{exists_info.source_table}" AS {exists_info.source_alias}
        WHERE {exists_info.source_alias}."fid" IN ({fid_list_str})
        AND {exists_info.spatial_predicate}(
            mv."{geom_column}",
            {exists_info.source_geometry}
        )
    )
)'''
        return optimized.strip()

    def _build_mv_source_query(
        self,
        mv_info: MaterializedViewInfo,
        exists_info: ExistsClauseInfo,
        geom_column: str,
        primary_key: str
    ) -> str:
        """
        Build standard MV-as-source query.

        Uses the MV directly in the EXISTS subquery.
        """
        optimized = '''"{primary_key}" IN (
    SELECT mv."{primary_key}"
    FROM {mv_info.qualified_name} AS mv
    WHERE EXISTS (
        SELECT 1
        FROM "{exists_info.source_schema}"."{exists_info.source_table}" AS {exists_info.source_alias}
        WHERE {exists_info.spatial_predicate}(
            mv."{geom_column}",
            {exists_info.source_geometry}
        )
    )
)'''
        return optimized.strip()

    # ============== Spatialite/OGR Optimization Methods ==============

    def _try_fid_list_optimization(
        self,
        old_subset: str,
        new_expression: str,
        combine_operator: str,
        primary_key: Optional[str] = None
    ) -> OptimizationResult:
        """
        Try to optimize FID list patterns (Spatialite/OGR).

        When we have:
            ("fid" IN (1, 2, 3, 45)) AND (Intersects(geometry, ...))

        We can optimize by:
        1. Converting large IN lists to range checks when possible
        2. Simplifying redundant FID constraints
        3. Moving FID check first for query planner hints
        """
        original = f"({old_subset}) {combine_operator} ({new_expression})"

        # Detect FID list in old_subset
        fid_info = self._detect_fid_list(old_subset)

        if not fid_info:
            # Try detecting range pattern
            fid_info = self._detect_fid_range(old_subset)

        if not fid_info:
            return OptimizationResult(
                success=False,
                optimized_expression=original,
                optimization_type=OptimizationType.NONE,
                original_expression=original
            )

        # Detect spatial predicate in new_expression (Spatialite style)
        spatial_info = self._detect_spatialite_spatial(new_expression)

        if spatial_info and combine_operator.upper() == 'AND':
            # Optimize the combined query for Spatialite/OGR
            optimized = self._rewrite_fid_spatial_query(fid_info, spatial_info, primary_key)

            if optimized:
                # Calculate estimated speedup based on FID list size
                fid_count = len(fid_info.fid_list) if fid_info.fid_list else 0
                if fid_info.is_range_based and fid_info.max_fid and fid_info.min_fid:
                    fid_count = fid_info.max_fid - fid_info.min_fid + 1

                # Larger FID lists benefit more from optimization
                estimated_speedup = min(5.0, 1.0 + (fid_count / 100))

                return OptimizationResult(
                    success=True,
                    optimized_expression=optimized,
                    optimization_type=OptimizationType.FID_LIST_OPTIMIZE,
                    original_expression=original,
                    performance_hint=(
                        f"FID list ({fid_count} features) combined with spatial predicate. "
                        "Restructured for optimal evaluation order."
                    ),
                    fid_info=fid_info,
                    estimated_speedup=estimated_speedup,
                    complexity_reduction=0.3
                )

        # Try range optimization for large FID lists
        if fid_info.fid_list and len(fid_info.fid_list) > 10:
            range_optimized = self._try_convert_to_range(fid_info, new_expression, combine_operator)
            if range_optimized:
                return range_optimized

        # Fallback: simple restructuring
        return self._optimize_fid_reference(fid_info, new_expression, combine_operator, original)

    def _detect_fid_list(self, expression: str) -> Optional[FidListInfo]:
        """
        Detect FID IN list pattern in expression.

        Matches patterns like:
            "fid" IN (1, 2, 3, 45, 67)
            "pk" IN (100,200,300)
        """
        match = self.FID_LIST_PATTERN.search(expression)
        if not match:
            return None

        pk_column = match.group(1)
        fid_string = match.group(2)

        # Parse FID list
        try:
            fid_list = [int(fid.strip()) for fid in fid_string.split(',')]
        except ValueError:
            return None

        return FidListInfo(
            primary_key=pk_column,
            fid_list=fid_list,
            full_match=match.group(0),
            is_range_based=False
        )

    def _detect_fid_range(self, expression: str) -> Optional[FidListInfo]:
        """
        Detect FID range pattern in expression.

        Matches patterns like:
            ("pk" >= 1 AND "pk" <= 100)
        """
        match = self.FID_RANGE_PATTERN.search(expression)
        if not match:
            return None

        pk_column = match.group(1)
        min_fid = int(match.group(2))
        max_fid = int(match.group(3))

        return FidListInfo(
            primary_key=pk_column,
            fid_list=[],  # Range-based, no explicit list
            full_match=match.group(0),
            is_range_based=True,
            min_fid=min_fid,
            max_fid=max_fid
        )

    def _detect_spatialite_spatial(self, expression: str) -> Optional[SpatialPredicateInfo]:
        """
        Detect Spatialite-style spatial predicate.

        Matches patterns like:
            Intersects(geometry, MakePoint(x, y))
            Intersects("geom", Buffer(...))
        """
        # First try EXISTS pattern
        exists_match = self.SPATIALITE_EXISTS_PATTERN.search(expression)
        if exists_match:
            return SpatialPredicateInfo(
                predicate=exists_match.group(3),
                target_geometry_col=exists_match.group(4).split(',')[0].strip().strip('"'),
                source_wkt_or_geom=exists_match.group(4).split(',', 1)[1].strip() if ',' in exists_match.group(4) else '',
                full_match=exists_match.group(0)
            )

        # Then try simple spatial predicate
        match = self.SPATIALITE_SPATIAL_PATTERN.search(expression)
        if not match:
            return None

        predicate = match.group(1)
        geometry_col = match.group(2)
        source_geom = match.group(3)

        # Check for buffer
        buffer_match = self.SPATIALITE_BUFFER_PATTERN.search(source_geom)
        buffer_distance = None
        if buffer_match:
            try:
                buffer_distance = float(buffer_match.group(2).strip())
            except ValueError:
                pass

        return SpatialPredicateInfo(
            predicate=predicate,
            target_geometry_col=geometry_col,
            source_wkt_or_geom=source_geom,
            buffer_distance=buffer_distance,
            full_match=match.group(0)
        )

    def _rewrite_fid_spatial_query(
        self,
        fid_info: FidListInfo,
        spatial_info: SpatialPredicateInfo,
        primary_key: Optional[str] = None
    ) -> Optional[str]:
        """
        Rewrite FID + spatial query for optimal evaluation.

        For Spatialite/OGR, the key insight is:
        - The FID check should be evaluated FIRST (it's fast, index-based)
        - The spatial predicate should only run on features that pass FID check

        Since SQLite/OGR evaluate conditions left-to-right with short-circuit,
        we ensure FID is on the left.

        Also, for very large FID lists, we can hint at using BETWEEN when possible.
        """
        pk_col = primary_key or fid_info.primary_key

        # Ensure FID check is first in the expression
        if fid_info.is_range_based:
            # Use the range expression
            fid_clause = f'("{pk_col}" >= {fid_info.min_fid} AND "{pk_col}" <= {fid_info.max_fid})'
        else:
            # Use IN list
            fid_clause = fid_info.full_match

        # Build optimized expression: FID first, then spatial
        optimized = f'({fid_clause}) AND ({spatial_info.full_match})'

        return optimized

    def _try_convert_to_range(
        self,
        fid_info: FidListInfo,
        new_expression: str,
        combine_operator: str
    ) -> Optional[OptimizationResult]:
        """
        Try to convert FID list to range expression for large lists.

        If FIDs are mostly consecutive, use:
            ("pk" >= min AND "pk" <= max) AND "pk" NOT IN (gaps)

        Instead of:
            "pk" IN (1,2,3,...,1000)
        """
        if not fid_info.fid_list or len(fid_info.fid_list) < 20:
            return None

        fids = sorted(fid_info.fid_list)
        min_fid = fids[0]
        max_fid = fids[-1]

        # Calculate coverage (what percentage of range is in the list)
        range_size = max_fid - min_fid + 1
        coverage = len(fids) / range_size

        # Only optimize if coverage is > 50% (mostly consecutive)
        if coverage < 0.5:
            return None

        # Find gaps in the sequence
        full_range = set(range(min_fid, max_fid + 1))
        actual_fids = set(fids)
        gaps = full_range - actual_fids

        pk_col = fid_info.primary_key

        if len(gaps) == 0:
            # Perfect consecutive range
            range_expr = f'("{pk_col}" >= {min_fid} AND "{pk_col}" <= {max_fid})'
        elif len(gaps) < len(fids) / 4:  # Gaps are less than 25% of list
            # Use range with exclusions
            gaps_str = ', '.join(str(g) for g in sorted(gaps))
            range_expr = f'("{pk_col}" >= {min_fid} AND "{pk_col}" <= {max_fid} AND "{pk_col}" NOT IN ({gaps_str}))'
        else:
            # Too many gaps, don't optimize
            return None

        original = f"({fid_info.full_match}) {combine_operator} ({new_expression})"
        optimized = f"({range_expr}) {combine_operator} ({new_expression})"

        return OptimizationResult(
            success=True,
            optimized_expression=optimized,
            optimization_type=OptimizationType.RANGE_OPTIMIZE,
            original_expression=original,
            performance_hint=(
                f"Converted {len(fids)} FIDs to range check "
                f"(coverage: {coverage * 100:.0f}%, gaps: {len(gaps)}). "
                "More efficient for index usage."
            ),
            fid_info=FidListInfo(
                primary_key=pk_col,
                fid_list=[],
                full_match=range_expr,
                is_range_based=True,
                min_fid=min_fid,
                max_fid=max_fid
            ),
            estimated_speedup=2.0 + coverage,  # Higher coverage = more benefit
            complexity_reduction=0.4
        )

    def _optimize_fid_reference(
        self,
        fid_info: FidListInfo,
        new_expression: str,
        combine_operator: str,
        original: str
    ) -> OptimizationResult:
        """
        Simple optimization: ensure FID check is evaluated first.

        SQLite and OGR evaluate conditions left-to-right with short-circuit,
        so putting the cheaper FID check first improves performance.
        """
        # Check if FID is already first in original
        if original.strip().startswith(f'({fid_info.full_match})'):
            # Already optimal
            return OptimizationResult(
                success=False,
                optimized_expression=original,
                optimization_type=OptimizationType.NONE,
                original_expression=original
            )

        # Restructure: put FID check first
        optimized = f"({fid_info.full_match}) {combine_operator} ({new_expression})"

        return OptimizationResult(
            success=True,
            optimized_expression=optimized,
            optimization_type=OptimizationType.FID_LIST_OPTIMIZE,
            original_expression=original,
            performance_hint="FID check moved to front for left-to-right evaluation benefit",
            fid_info=fid_info,
            estimated_speedup=1.3,
            complexity_reduction=0.1
        )

    def _extract_geometry_column(self, target_geometry: str) -> str:
        """Extract geometry column name from qualified reference."""
        # target_geometry is like "table.geom" or "geom"
        if '.' in target_geometry:
            return target_geometry.split('.')[-1].strip('"')
        return target_geometry.strip('"')

    def _optimize_mv_reference(
        self,
        mv_info: MaterializedViewInfo,
        new_expression: str,
        combine_operator: str,
        original: str
    ) -> OptimizationResult:
        """
        Simple optimization: ensure MV reference is evaluated first.

        PostgreSQL usually does this anyway, but we can help by restructuring.
        """
        # Check if new_expression is simple enough to optimize
        if len(new_expression) > 1000 or new_expression.count('SELECT') > 2:
            # Too complex, don't optimize
            return OptimizationResult(
                success=False,
                optimized_expression=original,
                optimization_type=OptimizationType.NONE,
                original_expression=original
            )

        # Simple restructuring: put MV check in parentheses to hint priority
        optimized = f"({mv_info.full_match}) {combine_operator} ({new_expression})"

        return OptimizationResult(
            success=True,
            optimized_expression=optimized,
            optimization_type=OptimizationType.EXPRESSION_SIMPLIFY,
            original_expression=original,
            performance_hint="Expression restructured for better query planning",
            mv_info=mv_info,
            estimated_speedup=1.5,
            complexity_reduction=0.1
        )

    def _try_expression_simplification(
        self,
        old_subset: str,
        new_expression: str,
        combine_operator: str
    ) -> OptimizationResult:
        """
        Try to simplify the combined expression structure.

        Removes redundant parentheses, normalizes spacing, etc.
        """
        original = f"({old_subset}) {combine_operator} ({new_expression})"

        # Remove double parentheses
        simplified = original
        while '((' in simplified and '))' in simplified:
            # Only remove if balanced
            new_simplified = re.sub(r'\(\(([^()]+)\)\)', r'(\1)', simplified)
            if new_simplified == simplified:
                break
            simplified = new_simplified

        # Normalize whitespace
        simplified = re.sub(r'\s+', ' ', simplified).strip()

        if simplified != original:
            return OptimizationResult(
                success=True,
                optimized_expression=simplified,
                optimization_type=OptimizationType.EXPRESSION_SIMPLIFY,
                original_expression=original,
                estimated_speedup=1.1,
                complexity_reduction=0.05
            )

        return OptimizationResult(
            success=False,
            optimized_expression=original,
            optimization_type=OptimizationType.NONE,
            original_expression=original
        )

    def _get_cache_key(self, old_subset: str, new_expression: str, operator: str) -> str:
        """Generate cache key for expression combination."""
        combined = f"{old_subset}|{operator}|{new_expression}"
        return hashlib.md5(combined.encode('utf-8', usedforsecurity=False)).hexdigest()[:16]

    def _cache_result(self, key: str, result: OptimizationResult) -> None:
        """Cache optimization result with LRU eviction."""
        if len(self._cache) >= self._cache_size:
            # Remove oldest entry
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        self._cache[key] = result

    def clear_cache(self) -> None:
        """Clear optimization cache."""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cleared CombinedQueryOptimizer cache ({count} entries)")

    def get_stats(self) -> Dict[str, Any]:
        """Get optimizer statistics."""
        total = self._optimization_count + self._cache_hits
        hit_rate = (self._cache_hits / total * 100) if total > 0 else 0.0

        return {
            'optimization_attempts': self._optimization_count,
            'cache_hits': self._cache_hits,
            'cache_hit_rate_percent': round(hit_rate, 2),
            'cache_size': len(self._cache),
            'max_cache_size': self._cache_size
        }


# Global optimizer instance
_global_optimizer: Optional[CombinedQueryOptimizer] = None


def get_combined_query_optimizer() -> CombinedQueryOptimizer:
    """Get or create global optimizer instance."""
    global _global_optimizer
    if _global_optimizer is None:
        _global_optimizer = CombinedQueryOptimizer()
    return _global_optimizer


def optimize_combined_filter(
    old_subset: str,
    new_expression: str,
    combine_operator: str = 'AND',
    layer_props: Optional[Dict[str, Any]] = None
) -> str:
    """
    Convenience function to optimize a combined filter expression.

    Args:
        old_subset: Existing subset string
        new_expression: New filter expression
        combine_operator: SQL operator
        layer_props: Layer properties

    Returns:
        Optimized expression string
    """
    optimizer = get_combined_query_optimizer()
    result = optimizer.optimize_combined_expression(
        old_subset, new_expression, combine_operator, layer_props
    )
    return result.optimized_expression


def detect_backend_type(expression: str) -> str:
    """
    Detect the likely backend type from an expression pattern.

    Args:
        expression: Filter expression to analyze

    Returns:
        'postgresql', 'spatialite', 'ogr', or 'unknown'
    """
    if not expression:
        return 'unknown'

    expr_lower = expression.lower()

    # PostgreSQL indicators
    if any(pattern in expr_lower for pattern in [
        'filtermate_mv_', 'mv_', 'st_intersects', 'st_buffer',
        'st_within', 'st_contains', '"public".', '::geometry'
    ]):
        return 'postgresql'

    # Spatialite indicators (no ST_ prefix for spatial functions)
    if any(pattern in expr_lower for pattern in [
        'intersects(', 'contains(', 'within(', 'makepoint(',
        'buffer(', 'geomfromtext(', 'setsrid('
    ]) and 'st_' not in expr_lower:
        return 'spatialite'

    # Check for FID list pattern (common in Spatialite/OGR)
    fid_pattern = re.search(r'"?\w+"?\s+IN\s*\(\s*\d+(?:\s*,\s*\d+)+\s*\)', expression)
    if fid_pattern:
        return 'spatialite'  # or OGR, but similar optimization applies

    return 'unknown'


def optimize_for_backend(
    old_subset: str,
    new_expression: str,
    combine_operator: str = 'AND',
    backend_type: Optional[str] = None,
    layer_props: Optional[Dict[str, Any]] = None
) -> OptimizationResult:
    """
    Optimize a combined filter expression with backend awareness.

    Args:
        old_subset: Existing subset string
        new_expression: New filter expression to combine
        combine_operator: SQL operator ('AND', 'OR')
        backend_type: 'postgresql', 'spatialite', 'ogr', or None (auto-detect)
        layer_props: Layer properties dict

    Returns:
        OptimizationResult with optimized expression
    """
    if backend_type is None:
        # Auto-detect from expressions
        backend_type = detect_backend_type(old_subset) or detect_backend_type(new_expression)

    optimizer = get_combined_query_optimizer()

    # Add backend hint to layer_props
    props = dict(layer_props) if layer_props else {}
    props['detected_backend'] = backend_type

    result = optimizer.optimize_combined_expression(
        old_subset, new_expression, combine_operator, props
    )

    if result.success:
        logger.debug(f"Backend '{backend_type}': Applied {result.optimization_type.name}")

    return result

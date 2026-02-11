# -*- coding: utf-8 -*-
"""
FilterMate - Filter Chain Optimizer for PostgreSQL

v4.2.10: Optimizes filter chaining using materialized views.

Problem:
    Multiple EXISTS clauses for each distant layer are expensive:
    EXISTS (SELECT 1 FROM demand_points WHERE ST_Intersects(...))
    AND EXISTS (SELECT 1 FROM zone_pop WHERE ST_Intersects(...))

    For N distant layers with M spatial filters: N × M EXISTS queries.

Solution:
    1. Create a MV of source geometries that satisfy ALL filter constraints
    2. Use single EXISTS against the MV for distant layers

Optimization Strategies:
    A. SOURCE_MV: Materialize filtered source features
       - Create MV from source layer with all spatial constraints applied
       - Distant layers use single EXISTS against MV

    B. INTERSECTION_MV: Materialize spatial intersections
       - Create MV of pre-computed intersections
       - Direct JOIN instead of EXISTS

    C. HYBRID: Combine based on cardinality analysis

Performance Impact:
    - Original: O(N × M) EXISTS queries per distant layer query
    - Optimized: O(1) EXISTS query per distant layer query
    - Trade-off: One-time MV creation cost (~0.5-2s)

Author: FilterMate Team
Date: January 2026
"""

import logging
import hashlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from ....infrastructure.database.sql_utils import sanitize_sql_identifier

logger = logging.getLogger('FilterMate.Backend.PostgreSQL.FilterChainOptimizer')


class OptimizationStrategy(Enum):
    """Filter chain optimization strategies."""
    NONE = "none"                    # No optimization (use EXISTS chain)
    SOURCE_MV = "source_mv"          # Materialize filtered source
    INTERSECTION_MV = "intersection_mv"  # Materialize intersections
    HYBRID = "hybrid"                # Combine strategies


@dataclass
class FilterChainContext:
    """Context for filter chain optimization."""
    source_schema: str
    source_table: str
    source_geom_column: str
    spatial_filters: List[Dict[str, Any]]  # List of EXISTS clauses info
    buffer_value: Optional[float] = None
    buffer_expression: Optional[str] = None  # Dynamic buffer expression (v4.3.5)
    feature_count_estimate: int = 0
    session_id: Optional[str] = None


@dataclass
class OptimizedChain:
    """Result of filter chain optimization."""
    mv_name: Optional[str]
    mv_schema: str
    expression: str
    strategy: OptimizationStrategy
    estimated_improvement: float
    creation_sql: Optional[str] = None
    cleanup_sql: Optional[str] = None


class FilterChainOptimizer:
    """
    Optimizes filter chaining using materialized views.

    Example:
        optimizer = FilterChainOptimizer(connection)

        # Analyze filter chain
        context = FilterChainContext(
            source_schema='infra',
            source_table='ducts',
            source_geom_column='geom',
            spatial_filters=[
                {'table': 'zone_pop', 'schema': 'ref', 'predicate': 'ST_Intersects'},
                {'table': 'demand_points', 'schema': 'ref', 'predicate': 'ST_Intersects', 'buffer': 5.0}
            ]
        )

        # Get optimized expression for distant layer
        result = optimizer.optimize_for_distant_layer(
            context=context,
            distant_table='subducts',
            distant_schema='infra',
            distant_geom_column='geom'
        )

        # Result.expression will be a single EXISTS against the MV
    """

    # Configuration (unified fm_temp_* prefix)
    MV_SCHEMA = "filtermate_temp"
    MV_PREFIX = "fm_temp_chain_"

    # Thresholds for optimization decisions
    MIN_FILTERS_FOR_MV = 2          # Minimum filters to justify MV creation
    MIN_DISTANT_LAYERS_FOR_MV = 3   # Minimum distant layers to justify MV
    MAX_SOURCE_FEATURES_FOR_MV = 100000  # Max features to materialize

    def __init__(
        self,
        connection=None,
        session_id: Optional[str] = None
    ):
        """
        Initialize filter chain optimizer.

        Args:
            connection: PostgreSQL connection
            session_id: Session ID for MV naming
        """
        self._connection = connection
        self._session_id = session_id or self._generate_session_id()
        self._created_mvs: Dict[str, str] = {}  # hash -> mv_name

    def analyze_chain(
        self,
        context: FilterChainContext
    ) -> OptimizationStrategy:
        """
        Analyze filter chain and recommend optimization strategy.

        Args:
            context: Filter chain context

        Returns:
            Recommended optimization strategy
        """
        num_filters = len(context.spatial_filters)

        # Not enough filters to optimize
        if num_filters < self.MIN_FILTERS_FOR_MV:
            logger.debug(f"Only {num_filters} filters, skipping MV optimization")
            return OptimizationStrategy.NONE

        # Too many source features
        if context.feature_count_estimate > self.MAX_SOURCE_FEATURES_FOR_MV:
            logger.warning(
                f"Too many source features ({context.feature_count_estimate}), "
                "skipping MV optimization"
            )
            return OptimizationStrategy.NONE

        # Has buffer expression - use SOURCE_MV
        if context.buffer_value:
            logger.info("Buffer detected, recommending SOURCE_MV strategy")
            return OptimizationStrategy.SOURCE_MV

        # Multiple spatial filters - use SOURCE_MV
        if num_filters >= 2:
            logger.info(f"{num_filters} spatial filters, recommending SOURCE_MV strategy")
            return OptimizationStrategy.SOURCE_MV

        return OptimizationStrategy.NONE

    def create_chain_mv(
        self,
        context: FilterChainContext,
        strategy: OptimizationStrategy = OptimizationStrategy.SOURCE_MV
    ) -> Optional[str]:
        """
        Create materialized view for filter chain.

        Args:
            context: Filter chain context
            strategy: Optimization strategy

        Returns:
            MV name if created, None otherwise
        """
        if strategy == OptimizationStrategy.NONE:
            return None

        if not self._connection:
            logger.error("No database connection for MV creation")
            return None

        # Generate MV name based on filter chain hash
        chain_hash = self._hash_filter_chain(context)

        # Check cache
        if chain_hash in self._created_mvs:
            mv_name = self._created_mvs[chain_hash]
            if self._mv_exists(mv_name):
                logger.info(f"Reusing existing chain MV: {mv_name}")
                return mv_name

        # Build MV SQL
        mv_name = f"{self.MV_PREFIX}{self._session_id}_{chain_hash[:8]}"

        if strategy == OptimizationStrategy.SOURCE_MV:
            create_sql = self._build_source_mv_sql(context, mv_name)
        else:
            logger.warning(f"Strategy {strategy} not yet implemented, falling back to SOURCE_MV")
            create_sql = self._build_source_mv_sql(context, mv_name)

        if not create_sql:
            return None

        # Execute MV creation
        try:
            cursor = self._connection.cursor()
            safe_schema = sanitize_sql_identifier(self.MV_SCHEMA)
            safe_mv = sanitize_sql_identifier(mv_name)

            # Ensure schema exists
            cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{safe_schema}"')

            # Drop if exists (for refresh)
            cursor.execute(
                f'DROP MATERIALIZED VIEW IF EXISTS "{safe_schema}"."{safe_mv}" CASCADE'
            )

            # Create MV
            logger.info(f"Creating chain MV: {mv_name}")
            logger.debug(f"SQL: {create_sql[:500]}...")
            cursor.execute(create_sql)

            # Create spatial index
            f"idx_{mv_name}_geom"
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS "{index_name}"
                ON "{self.MV_SCHEMA}"."{mv_name}"
                USING GIST ("{context.source_geom_column}")
            ''')

            self._connection.commit()

            # Cache MV name
            self._created_mvs[chain_hash] = mv_name

            logger.info(f"✅ Chain MV created: {self.MV_SCHEMA}.{mv_name}")
            return mv_name

        except Exception as e:
            logger.error(f"Failed to create chain MV: {e}")
            try:
                self._connection.rollback()
            except Exception:
                pass  # Rollback may fail if connection is broken
            return None

    def build_optimized_expression(
        self,
        context: FilterChainContext,
        mv_name: str,
        distant_table: str,
        distant_schema: str,
        distant_geom_column: str = "geom",
        predicate: str = "ST_Intersects"
    ) -> str:
        """
        Build optimized expression using the chain MV.

        Instead of:
            EXISTS (SELECT 1 FROM demand_points WHERE ST_Intersects(...))
            AND EXISTS (SELECT 1 FROM zone_pop WHERE ST_Intersects(...))

        Generates:
            EXISTS (SELECT 1 FROM filtermate_temp.fm_chain_xxx AS __source
                    WHERE ST_Intersects("distant"."geom", __source."geom"))

        Args:
            context: Filter chain context
            mv_name: Name of chain MV
            distant_table: Distant layer table name
            distant_schema: Distant layer schema
            distant_geom_column: Distant layer geometry column
            predicate: Spatial predicate function

        Returns:
            Optimized SQL expression
        """
        # Build source geometry reference (with buffer if needed)
        source_geom = f'__source."{context.source_geom_column}"'

        # v4.3.5: Handle dynamic buffer expression
        if context.buffer_expression:
            # Convert buffer expression to use __source alias instead of table name
            # Example: "demand_points"."homecount" -> __source."homecount"
            import re
            buffer_expr = context.buffer_expression

            # Replace table-qualified field refs with __source qualified refs
            # Pattern: "table_name"."field" -> __source."field"
            buffer_expr = re.sub(
                rf'"{context.source_table}"\."',
                '__source."',
                buffer_expr
            )

            # Also handle non-qualified field refs if they appear
            # This ensures all field references use __source
            source_geom = f"ST_Buffer({source_geom}, {buffer_expr}, 'quad_segs=5')"

        elif context.buffer_value:
            # Static buffer value
            source_geom = f"ST_Buffer({source_geom}, {context.buffer_value}, 'quad_segs=5')"

        # Build optimized EXISTS
        expression = '''EXISTS (
    SELECT 1 FROM "{self.MV_SCHEMA}"."{mv_name}" AS __source
    WHERE {predicate}("{distant_table}"."{distant_geom_column}", {source_geom})
)'''

        return expression

    def optimize_for_distant_layer(
        self,
        context: FilterChainContext,
        distant_table: str,
        distant_schema: str,
        distant_geom_column: str = "geom",
        predicate: str = "ST_Intersects"
    ) -> OptimizedChain:
        """
        Complete optimization for a distant layer.

        Args:
            context: Filter chain context
            distant_table: Distant layer table
            distant_schema: Distant layer schema
            distant_geom_column: Distant layer geometry column
            predicate: Spatial predicate

        Returns:
            OptimizedChain with expression and metadata
        """
        strategy = self.analyze_chain(context)

        if strategy == OptimizationStrategy.NONE:
            # Return original EXISTS chain
            return OptimizedChain(
                mv_name=None,
                mv_schema="",
                expression=self._build_exists_chain(context, distant_table, distant_geom_column, predicate),
                strategy=strategy,
                estimated_improvement=0.0
            )

        # Create MV
        mv_name = self.create_chain_mv(context, strategy)

        if not mv_name:
            # Fallback to EXISTS chain
            logger.warning("MV creation failed, falling back to EXISTS chain")
            return OptimizedChain(
                mv_name=None,
                mv_schema="",
                expression=self._build_exists_chain(context, distant_table, distant_geom_column, predicate),
                strategy=OptimizationStrategy.NONE,
                estimated_improvement=0.0
            )

        # Build optimized expression
        expression = self.build_optimized_expression(
            context, mv_name, distant_table, distant_schema, distant_geom_column, predicate
        )

        # Estimate improvement
        num_filters = len(context.spatial_filters)
        estimated_improvement = (num_filters - 1) / num_filters  # e.g., 2 filters = 50% reduction

        return OptimizedChain(
            mv_name=mv_name,
            mv_schema=self.MV_SCHEMA,
            expression=expression,
            strategy=strategy,
            estimated_improvement=estimated_improvement,
            cleanup_sql=f'DROP MATERIALIZED VIEW IF EXISTS "{self.MV_SCHEMA}"."{mv_name}" CASCADE'
        )

    def cleanup(self) -> int:
        """
        Cleanup all created MVs.

        Returns:
            Number of MVs dropped
        """
        if not self._connection:
            return 0

        count = 0
        try:
            cursor = self._connection.cursor()

            for chain_hash, mv_name in list(self._created_mvs.items()):
                try:
                    cursor.execute(
                        f'DROP MATERIALIZED VIEW IF EXISTS "{self.MV_SCHEMA}"."{mv_name}" CASCADE'
                    )
                    count += 1
                    del self._created_mvs[chain_hash]
                except Exception as e:
                    logger.warning(f"Failed to drop MV {mv_name}: {e}")

            self._connection.commit()

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")

        logger.info(f"Cleaned up {count} chain MVs")
        return count

    # === Private Methods ===

    def _build_source_mv_sql(
        self,
        context: FilterChainContext,
        mv_name: str
    ) -> str:
        """
        Build SQL for SOURCE_MV strategy.

        Creates MV of source features that satisfy ALL spatial filter constraints.
        """
        # Build WHERE clauses for each spatial filter
        where_clauses = []

        for filter_info in context.spatial_filters:
            filter_info.get('table')
            filter_info.get('schema', 'public')
            filter_geom = filter_info.get('geom_column', 'geom')
            filter_info.get('predicate', 'ST_Intersects')
            filter_buffer = filter_info.get('buffer')
            filter_condition = filter_info.get('condition')  # e.g., id IN (...)

            # Build source geometry reference
            f'src."{context.source_geom_column}"'

            # Build filter geometry reference
            filter_geom_ref = f'f."{filter_geom}"'
            if filter_buffer:
                filter_geom_ref = f"ST_Buffer({filter_geom_ref}, {filter_buffer}, 'quad_segs=5')"

            # Build EXISTS subquery
            exists_clause = '''EXISTS (
                SELECT 1 FROM "{filter_schema}"."{filter_table}" f
                WHERE {predicate}({src_geom}, {filter_geom_ref})'''

            if filter_condition:
                exists_clause += f' AND ({filter_condition})'

            exists_clause += ')'
            where_clauses.append(exists_clause)

        # Combine all constraints
        ' AND '.join(where_clauses)

        # Build CREATE MATERIALIZED VIEW SQL
        sql = '''
CREATE MATERIALIZED VIEW "{self.MV_SCHEMA}"."{mv_name}" AS
SELECT src.*
FROM "{context.source_schema}"."{context.source_table}" src
WHERE {where_combined}
WITH DATA
'''

        return sql.strip()

    def _build_exists_chain(
        self,
        context: FilterChainContext,
        distant_table: str,
        distant_geom_column: str,
        predicate: str
    ) -> str:
        """Build traditional EXISTS chain (fallback)."""
        exists_clauses = []

        for filter_info in context.spatial_filters:
            filter_info.get('table')
            filter_info.get('schema', 'public')
            filter_geom = filter_info.get('geom_column', 'geom')
            filter_buffer = filter_info.get('buffer')
            filter_condition = filter_info.get('condition')

            # Build source geometry in EXISTS
            src_geom = f'__source."{filter_geom}"'
            if filter_buffer:
                src_geom = f"ST_Buffer({src_geom}, {filter_buffer}, 'quad_segs=5')"

            # Build EXISTS
            exists_sql = '''EXISTS (SELECT 1 FROM "{filter_schema}"."{filter_table}" AS __source WHERE {predicate}("{distant_table}"."{distant_geom_column}", {src_geom})'''  # nosec B608

            if filter_condition:
                exists_sql += f' AND ({filter_condition})'

            exists_sql += ')'
            exists_clauses.append(exists_sql)

        return ' AND '.join(exists_clauses)

    def _hash_filter_chain(self, context: FilterChainContext) -> str:
        """Generate hash for filter chain context."""
        chain_str = f"{context.source_schema}.{context.source_table}|"

        for f in sorted(context.spatial_filters, key=lambda x: x.get('table', '')):
            chain_str += f"{f.get('schema', '')}.{f.get('table', '')}|"
            chain_str += f"{f.get('predicate', '')}|{f.get('buffer', '')}|"
            chain_str += f"{f.get('condition', '')}|"

        # v4.3.5: Include buffer_value OR buffer_expression in hash
        if context.buffer_expression:
            chain_str += f"buffer_expr={context.buffer_expression}"
        elif context.buffer_value:
            chain_str += f"buffer={context.buffer_value}"

        return hashlib.md5(chain_str.encode(), usedforsecurity=False).hexdigest()

    def _mv_exists(self, mv_name: str) -> bool:
        """Check if MV exists."""
        if not self._connection:
            return False

        try:
            cursor = self._connection.cursor()
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_matviews
                    WHERE schemaname = %s AND matviewname = %s
                )
            """, (self.MV_SCHEMA, mv_name))
            result = cursor.fetchone()
            return result[0] if result else False
        except Exception:
            return False  # Assume MV doesn't exist if query fails

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        import uuid
        return uuid.uuid4().hex[:8]


# === Factory Functions ===

def create_filter_chain_optimizer(
    connection=None,
    session_id: Optional[str] = None
) -> FilterChainOptimizer:
    """
    Factory function for FilterChainOptimizer.

    Args:
        connection: PostgreSQL connection
        session_id: Session ID

    Returns:
        Configured optimizer instance
    """
    return FilterChainOptimizer(
        connection=connection,
        session_id=session_id
    )


def optimize_filter_chain(
    connection,
    source_schema: str,
    source_table: str,
    source_geom_column: str,
    spatial_filters: List[Dict],
    distant_table: str,
    distant_schema: str,
    distant_geom_column: str = "geom",
    buffer_value: Optional[float] = None,
    buffer_expression: Optional[str] = None,  # v4.3.5: Dynamic buffer support
    session_id: Optional[str] = None
) -> OptimizedChain:
    """
    Convenience function to optimize a filter chain.

    Args:
        connection: PostgreSQL connection
        source_schema: Source layer schema
        source_table: Source layer table
        source_geom_column: Source layer geometry column
        spatial_filters: List of spatial filter definitions
        distant_table: Distant layer table
        distant_schema: Distant layer schema
        distant_geom_column: Distant layer geometry column
        buffer_value: Optional buffer value
        buffer_expression: Optional dynamic buffer expression (v4.3.5)
        session_id: Optional session ID

    Returns:
        OptimizedChain result

    Example:
        result = optimize_filter_chain(
            connection=conn,
            source_schema='infra',
            source_table='ducts',
            source_geom_column='geom',
            spatial_filters=[
                {'table': 'zone_pop', 'schema': 'ref', 'predicate': 'ST_Intersects'},
                {'table': 'demand_points', 'schema': 'ref', 'predicate': 'ST_Intersects', 'buffer': 5.0}
            ],
            distant_table='subducts',
            distant_schema='infra',
            buffer_value=None,
            buffer_expression='CASE WHEN "homecount"::numeric >= 10 THEN 50 ELSE 1 END'
        )

        # Use result.expression in setSubsetString
        layer.setSubsetString(result.expression)
    """
    optimizer = FilterChainOptimizer(connection, session_id)

    context = FilterChainContext(
        source_schema=source_schema,
        source_table=source_table,
        source_geom_column=source_geom_column,
        spatial_filters=spatial_filters,
        buffer_value=buffer_value,
        buffer_expression=buffer_expression,  # v4.3.5
        session_id=session_id
    )

    return optimizer.optimize_for_distant_layer(
        context=context,
        distant_table=distant_table,
        distant_schema=distant_schema,
        distant_geom_column=distant_geom_column
    )

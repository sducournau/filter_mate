# -*- coding: utf-8 -*-
"""
FilterMate PostgreSQL Backend Implementation - ARCH-039

Main backend class for PostgreSQL/PostGIS filtering.
Implements BackendPort interface and delegates to specialized components.

Part of Phase 4 Backend Refactoring.

Features:
- Materialized view optimization
- Query optimization and analysis
- Connection pooling support
- Automatic cleanup

Author: FilterMate Team
Date: January 2026
"""

import logging
import time
import re
from typing import Optional, List, Dict, Any

from core.ports.backend_port import BackendPort, BackendInfo, BackendCapability
from core.domain.filter_expression import FilterExpression, ProviderType
from core.domain.filter_result import FilterResult
from core.domain.layer_info import LayerInfo

from .mv_manager import MaterializedViewManager, MVConfig, create_mv_manager
from .optimizer import QueryOptimizer, create_optimizer
from .cleanup import create_cleanup_service

logger = logging.getLogger('FilterMate.Backend.PostgreSQL')


class PostgreSQLBackend(BackendPort):
    """
    PostgreSQL/PostGIS backend for filter operations.

    Features:
    - Materialized view optimization for large datasets
    - Query optimization and analysis
    - Connection pooling
    - Automatic cleanup

    Example:
        backend = PostgreSQLBackend(connection_pool)
        result = backend.execute(expression, layer_info)
    """

    def __init__(
        self,
        connection_pool=None,
        mv_config: Optional[MVConfig] = None,
        session_id: Optional[str] = None,
        use_mv_optimization: bool = True
    ):
        """
        Initialize PostgreSQL backend.

        Args:
            connection_pool: Database connection pool
            mv_config: Materialized view configuration
            session_id: Session ID for resource tracking
            use_mv_optimization: Enable MV optimization
        """
        self._pool = connection_pool
        self._session_id = session_id or self._generate_session_id()
        self._use_mv_optimization = use_mv_optimization

        # Initialize sub-components
        self._mv_manager = create_mv_manager(
            connection_pool=connection_pool,
            config=mv_config,
            session_id=self._session_id
        )
        self._optimizer = create_optimizer(connection_pool=connection_pool)
        self._cleanup_service = create_cleanup_service(
            session_id=self._session_id,
            use_circuit_breaker=True
        )

        # Ensure schema exists
        self._ensure_schema()

        # Metrics
        self._metrics = {
            'executions': 0,
            'mv_executions': 0,
            'direct_executions': 0,
            'total_time_ms': 0.0,
            'errors': 0
        }

        logger.info(f"PostgreSQL backend initialized: session={self._session_id[:8]}")

    @property
    def session_id(self) -> str:
        """Get current session ID."""
        return self._session_id

    @property
    def mv_manager(self) -> MaterializedViewManager:
        """Access to MV manager for advanced usage."""
        return self._mv_manager

    @property
    def optimizer(self) -> QueryOptimizer:
        """Access to query optimizer."""
        return self._optimizer

    @property
    def metrics(self) -> Dict[str, Any]:
        """Get backend metrics."""
        return self._metrics.copy()

    def execute(
        self,
        expression: FilterExpression,
        layer_info: LayerInfo,
        target_layer_infos: Optional[List[LayerInfo]] = None
    ) -> FilterResult:
        """
        Execute filter expression.

        Args:
            expression: Validated filter expression
            layer_info: Source layer information
            target_layer_infos: Optional target layers

        Returns:
            FilterResult with matching feature IDs
        """
        start_time = time.time()
        self._metrics['executions'] += 1

        try:
            # Get connection
            conn = self._get_connection()
            if conn is None:
                return FilterResult.error(
                    layer_id=layer_info.layer_id,
                    expression_raw=expression.raw,
                    error_message="No database connection available",
                    backend_name=self.name
                )

            # Analyze query
            analysis = self._optimizer.analyze(expression.sql)

            # Determine execution strategy
            if self._should_use_mv(layer_info, analysis):
                feature_ids = self._execute_with_mv(expression, layer_info, conn)
                self._metrics['mv_executions'] += 1
            else:
                feature_ids = self._execute_direct(expression, layer_info, conn)
                self._metrics['direct_executions'] += 1

            execution_time = (time.time() - start_time) * 1000
            self._metrics['total_time_ms'] += execution_time

            return FilterResult.success(
                feature_ids=feature_ids,
                layer_id=layer_info.layer_id,
                expression_raw=expression.raw,
                execution_time_ms=execution_time,
                backend_name=self.name
            )

        except Exception as e:
            self._metrics['errors'] += 1
            logger.exception(f"PostgreSQL filter execution failed: {e}")
            return FilterResult.error(
                layer_id=layer_info.layer_id,
                expression_raw=expression.raw,
                error_message=str(e),
                backend_name=self.name
            )

    def supports_layer(self, layer_info: LayerInfo) -> bool:
        """Check if this backend supports the layer."""
        return layer_info.provider_type == ProviderType.POSTGRESQL

    def get_info(self) -> BackendInfo:
        """Get backend information."""
        return BackendInfo(
            name="PostgreSQL",
            version="1.0.0",
            capabilities=(
                BackendCapability.SPATIAL_FILTER |
                BackendCapability.MATERIALIZED_VIEW |
                BackendCapability.SPATIAL_INDEX |
                BackendCapability.COMPLEX_EXPRESSIONS |
                BackendCapability.BUFFER_OPERATIONS |
                BackendCapability.PARALLEL_EXECUTION |
                BackendCapability.TRANSACTIONS
            ),
            priority=100,  # Highest priority
            description="PostgreSQL/PostGIS backend with MV optimization"
        )

    def cleanup(self) -> None:
        """Clean up temporary resources."""
        try:
            # Clean up session MVs
            conn = self._get_connection()
            if conn:
                mv_count = self._mv_manager.cleanup_session_mvs(connection=conn)
                view_count, _ = self._cleanup_service.cleanup_session_views(conn)
                logger.info(f"PostgreSQL cleanup: {mv_count + view_count} objects dropped")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")

    def estimate_execution_time(
        self,
        expression: FilterExpression,
        layer_info: LayerInfo
    ) -> float:
        """
        Estimate execution time in milliseconds.

        Args:
            expression: Filter expression
            layer_info: Source layer

        Returns:
            Estimated execution time in milliseconds
        """
        analysis = self._optimizer.analyze(expression.sql)

        # Base estimate on complexity and feature count
        base_time = layer_info.feature_count * 0.01  # 0.01ms per feature base
        complexity_factor = analysis.estimated_complexity * 10

        if analysis.uses_spatial_index:
            base_time *= 0.1  # 10x faster with spatial index

        if self._should_use_mv(layer_info, analysis):
            # MV adds overhead but speeds up subsequent queries
            base_time *= 0.5

        return base_time + complexity_factor

    def validate_expression(
        self,
        expression: FilterExpression,
        layer_info: LayerInfo
    ) -> List[str]:
        """
        Validate expression for PostgreSQL.

        Args:
            expression: Expression to validate
            layer_info: Target layer

        Returns:
            List of validation errors (empty if valid)
        """
        errors: List[str] = []

        if not expression.sql:
            errors.append("SQL expression is empty")

        # Check for common SQL injection patterns
        dangerous_patterns = [';', '--', '/*', '*/', 'drop ', 'delete ', 'update ', 'insert ']
        sql_lower = expression.sql.lower()
        for pattern in dangerous_patterns:
            if pattern in sql_lower:
                errors.append(f"Potentially dangerous SQL pattern detected: {pattern}")

        return errors

    def test_connection(self) -> bool:
        """Test database connection."""
        try:
            conn = self._get_connection()
            if conn is None:
                return False

            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            return cursor.fetchone() is not None

        except Exception as e:
            logger.warning(f"Connection test failed: {e}")
            return False

    # === Private Methods ===

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        import uuid
        return uuid.uuid4().hex[:8]

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
        except Exception as e:
            logger.error(f"Failed to get connection: {e}")
            return None

    def _ensure_schema(self) -> None:
        """Ensure filtermate schema exists."""
        try:
            conn = self._get_connection()
            if conn:
                self._cleanup_service.ensure_schema_exists(conn)
        except Exception as e:
            logger.warning(f"Failed to ensure schema: {e}")

    def _should_use_mv(self, layer_info: LayerInfo, analysis) -> bool:
        """Determine if MV should be used."""
        if not self._use_mv_optimization:
            return False

        return self._mv_manager.should_use_mv(
            feature_count=layer_info.feature_count,
            expression_complexity=analysis.estimated_complexity,
            is_spatial=analysis.query_type.name == 'SPATIAL'
        )

    def _execute_with_mv(
        self,
        expression: FilterExpression,
        layer_info: LayerInfo,
        connection
    ) -> List[int]:
        """Execute filter using materialized view."""
        # Build query for MV
        table_name = self._get_table_name(layer_info)
        query = f"SELECT * FROM {table_name} WHERE {expression.sql}"

        # Create MV
        mv_name = self._mv_manager.create_mv(
            query=query,
            source_table=table_name,
            geometry_column=self._get_geometry_column(layer_info),
            session_scoped=True,
            connection=connection
        )

        # Query MV for feature IDs
        pk_column = self._get_pk_column(layer_info)
        results = self._mv_manager.query_mv(
            mv_name=mv_name,
            columns=pk_column,
            connection=connection
        )

        return [row[0] for row in results]

    def _execute_direct(
        self,
        expression: FilterExpression,
        layer_info: LayerInfo,
        connection
    ) -> List[int]:
        """Execute filter directly without MV."""
        table_name = self._get_table_name(layer_info)
        pk_column = self._get_pk_column(layer_info)

        query = f"""
            SELECT "{pk_column}" FROM {table_name}
            WHERE {expression.sql}
        """

        try:
            cursor = connection.cursor()
            cursor.execute(query)
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Direct query failed: {e}")
            raise

    def _get_table_name(self, layer_info: LayerInfo) -> str:
        """Extract table name from layer source."""
        # Parse from layer source_path
        # Format: "dbname=x user=y table=schema.table" or "table=\"schema\".\"table\""
        source = layer_info.source_path

        # Try to extract table from source
        match = re.search(r'table=["\']?([^"\'"\s]+)["\']?', source)
        if match:
            return match.group(1)

        # Try schema.table format
        match = re.search(r'table="([^"]+)"\.?"([^"]+)"', source)
        if match:
            return f'"{match.group(1)}"."{match.group(2)}"'

        # Fallback to layer table_name
        if layer_info.table_name:
            if layer_info.schema_name:
                return f'"{layer_info.schema_name}"."{layer_info.table_name}"'
            return f'"{layer_info.table_name}"'

        return "unknown_table"

    def _get_geometry_column(self, layer_info: LayerInfo) -> str:
        """Get geometry column name."""
        # Default geometry column names
        return "geom"

    def _get_pk_column(self, layer_info: LayerInfo) -> str:
        """Get primary key column name."""
        # Common PK column names
        return "id"


def create_postgresql_backend(
    connection_pool=None,
    session_id: Optional[str] = None,
    mv_config: Optional[MVConfig] = None,
    use_mv_optimization: bool = True
) -> PostgreSQLBackend:
    """
    Factory function for PostgreSQLBackend.

    Args:
        connection_pool: Database connection pool
        session_id: Session ID for tracking
        mv_config: MV configuration
        use_mv_optimization: Enable MV optimization

    Returns:
        Configured PostgreSQLBackend instance
    """
    return PostgreSQLBackend(
        connection_pool=connection_pool,
        mv_config=mv_config,
        session_id=session_id,
        use_mv_optimization=use_mv_optimization
    )

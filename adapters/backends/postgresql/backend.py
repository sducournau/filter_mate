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
from typing import Optional, List, Dict, Any, Tuple

from ....core.ports.backend_port import BackendPort, BackendInfo, BackendCapability
from ....core.domain.filter_expression import FilterExpression, ProviderType
from ....core.domain.filter_result import FilterResult
from ....core.domain.layer_info import LayerInfo

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
        use_mv_optimization: bool = True,
        task_parameters: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize PostgreSQL backend.

        Args:
            connection_pool: Database connection pool
            mv_config: Materialized view configuration
            session_id: Session ID for resource tracking
            use_mv_optimization: Enable MV optimization
            task_parameters: Legacy task parameters dict (for backward compatibility)
        """
        # Handle legacy task_parameters initialization
        # Some code passes task_parameters dict instead of connection_pool
        if task_parameters is not None and connection_pool is None:
            # Try to extract connection from task_parameters
            connection_pool = task_parameters.get('connection')
            if session_id is None:
                session_id = task_parameters.get('session_id')
        
        self._pool = connection_pool
        self._task_parameters = task_parameters  # Store for later use
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

        logger.info(f"[PostgreSQL] PostgreSQL backend initialized: session={self._session_id[:8]}")

    @property
    def name(self) -> str:
        """Get backend name for internal use (must be 'PostgreSQL' for TaskBridge compatibility)."""
        return "PostgreSQL"

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

    def get_statistics(self) -> Dict[str, Any]:
        """Get backend execution statistics."""
        stats = self.metrics
        # Add MV manager statistics
        if self._mv_manager:
            stats['mv_stats'] = self._mv_manager.get_stats() if hasattr(self._mv_manager, 'get_stats') else {}
        return stats

    def reset_statistics(self) -> None:
        """Reset backend execution statistics."""
        self._metrics = {
            'executions': 0,
            'mv_executions': 0,
            'direct_executions': 0,
            'total_time_ms': 0.0,
            'errors': 0
        }

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

        # DEBUG: Log execution details
        logger.debug(f"[PostgreSQL] [PostgreSQL v4.0] EXECUTE START:")
        logger.debug(f"[PostgreSQL]   Layer: {layer_info.layer_id}")
        logger.debug(f"[PostgreSQL]   Table: {layer_info.table_name} (schema: {layer_info.schema_name})")
        logger.debug(f"[PostgreSQL]   PK: {layer_info.pk_attr}")
        logger.debug(f"[PostgreSQL]   Geometry: {layer_info.geometry_column}")
        logger.debug(f"[PostgreSQL]   Features: {layer_info.feature_count}")
        logger.debug(f"[PostgreSQL]   Expression SQL: {expression.sql[:200]}...")

        try:
            # Get connection - first from pool, then from layer
            conn = self._get_connection()
            if conn is None:
                # Try to get connection from QGIS layer
                conn = self._get_connection_from_layer(layer_info.layer_id)
            if conn is None:
                logger.error(f"[PostgreSQL] [PostgreSQL v4.0] No connection available for {layer_info.layer_id}")
                return FilterResult.error(
                    layer_id=layer_info.layer_id,
                    expression_raw=expression.raw,
                    error_message="No database connection available",
                    backend_name=self.name
                )
            logger.debug(f"[PostgreSQL] [PostgreSQL v4.0] Connection obtained: {type(conn).__name__}")

            # Analyze query
            analysis = self._optimizer.analyze(expression.sql)
            logger.debug(f"[PostgreSQL] [PostgreSQL v4.0] Query complexity: {analysis.estimated_complexity}")

            # Determine execution strategy
            use_mv = self._should_use_mv(layer_info, analysis)
            logger.debug(f"[PostgreSQL] [PostgreSQL v4.0] Strategy: {'MV' if use_mv else 'DIRECT'}")
            
            if use_mv:
                feature_ids = self._execute_with_mv(expression, layer_info, conn)
                self._metrics['mv_executions'] += 1
            else:
                feature_ids = self._execute_direct(expression, layer_info, conn)
                self._metrics['direct_executions'] += 1
            
            logger.debug(f"[PostgreSQL] [PostgreSQL v4.0] Execution successful: {len(feature_ids)} features matched")

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

    def create_source_selection_mv(
        self,
        layer,
        fids: List[Any],
        pk_field: str,
        geom_field: str = "geom"
    ) -> Optional[str]:
        """
        Create a materialized view for large source feature selection.
        
        This method creates a temporary MV containing the selected features,
        which can then be used in EXISTS queries instead of massive IN clauses.
        
        CRITICAL FIX for 212KB expressions with 2862+ UUIDs!
        Instead of: pk IN ('uuid1', 'uuid2', ..., 'uuid2862')  → 212KB
        We get:     pk IN (SELECT pk FROM fm_temp_src_xxx)   → ~60 bytes
        
        Args:
            layer: QgsVectorLayer source layer
            fids: List of feature IDs to include
            pk_field: Primary key field name
            geom_field: Geometry field name (for spatial index)
            
        Returns:
            Optional[str]: MV name if successful, None on failure
            
        Example:
            mv_name = backend.create_source_selection_mv(
                layer=ducts_layer,
                fids=['uuid1', 'uuid2', ...],  # 2862 UUIDs
                pk_field='pk',
                geom_field='geom'
            )
            # Returns: "fm_temp_src_abc123"
            # Use in query: pk IN (SELECT pk FROM filtermate_temp.fm_temp_src_abc123)
        """
        if not fids:
            logger.warning("[PostgreSQL] create_source_selection_mv: No FIDs provided")
            return None
        
        logger.info(f"[PostgreSQL] 🗄️ Creating source selection MV for {len(fids)} features")
        
        try:
            # Get connection - try multiple sources
            conn = None
            conn_source = "none"
            
            # Source 1: Connection pool
            conn = self._get_connection()
            if conn:
                conn_source = "pool"
                logger.debug(f"[PostgreSQL] MV: Connection from pool: OK")
            
            # Source 2: Task parameters (passed by ExpressionBuilder)
            if conn is None and self._task_parameters:
                conn = self._task_parameters.get('connection')
                if conn:
                    conn_source = "task_parameters"
                    logger.debug(f"[PostgreSQL] MV: Connection from task_parameters: OK")
            
            # Source 3: Layer fallback
            if conn is None and layer:
                try:
                    conn = self._get_connection_from_layer(layer.id())
                    if conn:
                        conn_source = "layer"
                        logger.debug(f"[PostgreSQL] MV: Connection from layer: OK")
                except Exception as layer_conn_err:
                    logger.debug(f"[PostgreSQL] MV: Layer connection failed: {layer_conn_err}")
            
            if conn is None:
                logger.error("[PostgreSQL] No connection available for MV creation")
                logger.error("[PostgreSQL] → Tried: pool, task_parameters, layer - all failed")
                logger.error(f"[PostgreSQL] → Layer: {layer.name() if layer else 'None'}")
                logger.error(f"[PostgreSQL] → Pool: {self._pool is not None}")
                logger.error(f"[PostgreSQL] → task_parameters keys: {list(self._task_parameters.keys()) if self._task_parameters else 'None'}")
                return None
            
            logger.info(f"[PostgreSQL] MV: Using connection from '{conn_source}'")
            
            # Extract table info from layer
            schema_name, table_name = self._extract_table_info(layer)
            if not table_name:
                logger.error("[PostgreSQL] Could not extract table name from layer")
                return None
            
            full_table = f'"{schema_name}"."{table_name}"' if schema_name else f'"{table_name}"'
            
            # Format FIDs for SQL (handle UUIDs vs integers)
            formatted_fids = self._format_fids_for_sql(fids)
            
            # Build SELECT query for MV
            # Include pk and geometry for spatial indexing
            # FIX v4.3.1 (2026-01-22): Ensure pk_field and geom_field are simple field names
            # Strip any table prefixes if present (should be just field names)
            clean_pk_field = pk_field.split('.')[-1].strip('"')
            clean_geom_field = geom_field.split('.')[-1].strip('"')
            
            query = f"""
                SELECT "{clean_pk_field}" as pk, "{clean_geom_field}" as geom
                FROM {full_table}
                WHERE "{clean_pk_field}" IN ({formatted_fids})
            """
            
            logger.debug(f"[PostgreSQL] MV query: {query[:200]}...")
            
            # Generate unique MV name (unified fm_temp_src_ prefix)
            import hashlib
            fid_hash = hashlib.md5(','.join(str(f) for f in fids[:10]).encode()).hexdigest()[:8]
            mv_name = f"fm_temp_src_{self._session_id[:6]}_{fid_hash}"
            
            # Create MV using mv_manager
            try:
                created_name = self._mv_manager.create_mv(
                    query=query,
                    source_table=table_name,
                    geometry_column=geom_field,
                    indexes=[pk_field],  # Index on PK for fast lookups
                    session_scoped=True,
                    connection=conn
                )
                
                # Verify MV was created
                if created_name and self._mv_manager.mv_exists(created_name, connection=conn):
                    # Get row count for logging
                    cursor = conn.cursor()
                    cursor.execute(f'SELECT COUNT(*) FROM "filtermate_temp"."{created_name}"')
                    row_count = cursor.fetchone()[0]
                    
                    logger.info(
                        f"[PostgreSQL] ✅ Source selection MV created: {created_name} "
                        f"({row_count} rows, was {len(fids)} FIDs)"
                    )
                    
                    # Return full reference for use in queries
                    return f'"filtermate_temp"."{created_name}"'
                else:
                    logger.error(f"[PostgreSQL] MV creation reported success but MV not found")
                    return None
                    
            except Exception as mv_error:
                logger.error(f"[PostgreSQL] MV creation failed: {mv_error}")
                logger.error(f"[PostgreSQL] Query was: {query[:300]}...")
                logger.error(f"[PostgreSQL] pk_field='{pk_field}', geom_field='{geom_field}'")
                logger.error(f"[PostgreSQL] Cleaned: pk='{clean_pk_field}', geom='{clean_geom_field}'")
                import traceback
                logger.debug(traceback.format_exc())
                # Try fallback: create temporary table instead
                return self._create_source_selection_temp_table(
                    conn, table_name, clean_pk_field, clean_geom_field, fids, formatted_fids
                )
                
        except Exception as e:
            logger.error(f"[PostgreSQL] create_source_selection_mv failed: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def _extract_table_info(self, layer) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract schema and table name from QGIS layer.
        
        Args:
            layer: QgsVectorLayer
            
        Returns:
            Tuple of (schema_name, table_name)
        """
        if not layer:
            return None, None
        
        try:
            source = layer.source()
            
            # Parse PostgreSQL connection string
            # Format: "dbname='x' host='y' port='z' sslmode='prefer' ... table=\"schema\".\"table\" ..."
            
            # Try table="schema"."table" format
            import re
            match = re.search(r'table="([^"]+)"\.?"([^"]+)"', source)
            if match:
                return match.group(1), match.group(2)
            
            # Try table=schema.table format (no quotes)
            match = re.search(r'table=([^\s"]+)\.([^\s"]+)', source)
            if match:
                return match.group(1), match.group(2)
            
            # Try just table name
            match = re.search(r'table=["\']?([^"\'\s]+)["\']?', source)
            if match:
                # Assume public schema if not specified
                return 'public', match.group(1)
            
            logger.warning(f"[PostgreSQL] Could not parse table from source: {source[:200]}")
            return None, None
            
        except Exception as e:
            logger.error(f"[PostgreSQL] Error extracting table info: {e}")
            return None, None
    
    def _format_fids_for_sql(self, fids: List[Any]) -> str:
        """
        Format FID list for SQL IN clause.
        
        Handles both UUIDs (strings) and integers.
        
        Args:
            fids: List of feature IDs
            
        Returns:
            Formatted string for SQL IN clause
        """
        if not fids:
            return ""
        
        # Check if UUIDs (strings) or integers
        sample = fids[0]
        
        if isinstance(sample, str):
            # Quote strings/UUIDs
            return ', '.join(f"'{str(fid)}'" for fid in fids)
        else:
            # Integers don't need quotes
            return ', '.join(str(fid) for fid in fids)
    
    def _create_source_selection_temp_table(
        self,
        conn,
        table_name: str,
        pk_field: str,
        geom_field: str,
        fids: List[Any],
        formatted_fids: str
    ) -> Optional[str]:
        """
        Fallback: Create persistent temp table instead of MV.
        
        This is used when MV creation fails (e.g., due to permissions).
        
        FIX v4.3.2 (2026-01-25): Use persistent table in filtermate_temp schema
        instead of TEMPORARY table. TEMPORARY tables are session-scoped and 
        not visible to QGIS's PostgreSQL connection (different session).
        
        Args:
            conn: Database connection
            table_name: Source table name
            pk_field: Primary key field
            geom_field: Geometry field
            fids: List of FIDs
            formatted_fids: Pre-formatted FID string
            
        Returns:
            Optional[str]: Full qualified table name or None
        """
        try:
            import hashlib
            from ....infrastructure.constants import DEFAULT_TEMP_SCHEMA
            
            fid_hash = hashlib.md5(','.join(str(f) for f in fids[:10]).encode()).hexdigest()[:8]
            temp_name = f"fm_temp_src_sel_{fid_hash}"
            
            # FIX v4.3.1 (2026-01-22): Clean field names (remove table prefixes if present)
            clean_pk_field = pk_field.split('.')[-1].strip('"')
            clean_geom_field = geom_field.split('.')[-1].strip('"')
            
            cursor = conn.cursor()
            
            # FIX v4.3.2: Ensure filtermate_temp schema exists
            cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{DEFAULT_TEMP_SCHEMA}"')
            
            # FIX v4.3.2: Create persistent table in filtermate_temp schema
            # (NOT TEMPORARY - QGIS uses a different PostgreSQL session)
            # Drop existing table first to avoid conflicts
            cursor.execute(f'DROP TABLE IF EXISTS "{DEFAULT_TEMP_SCHEMA}"."{temp_name}"')
            
            create_sql = f"""
                CREATE TABLE "{DEFAULT_TEMP_SCHEMA}"."{temp_name}" AS
                SELECT "{clean_pk_field}" as pk
                FROM "{table_name}"
                WHERE "{clean_pk_field}" IN ({formatted_fids})
            """
            cursor.execute(create_sql)
            
            # Create index for fast lookups
            cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{temp_name}_pk ON "{DEFAULT_TEMP_SCHEMA}"."{temp_name}" (pk)')
            
            conn.commit()
            
            full_name = f'"{DEFAULT_TEMP_SCHEMA}"."{temp_name}"'
            logger.info(f"[PostgreSQL] ✅ Fallback temp table created: {full_name}")
            return full_name
            
        except Exception as e:
            logger.error(f"[PostgreSQL] Temp table fallback failed: {e}")
            return None

    def cleanup(self) -> None:
        """Clean up temporary resources."""
        try:
            # Clean up session MVs
            conn = self._get_connection()
            if conn:
                mv_count = self._mv_manager.cleanup_session_mvs(connection=conn)
                view_count, _ = self._cleanup_service.cleanup_session_views(conn)
                logger.info(f"[PostgreSQL] PostgreSQL cleanup: {mv_count + view_count} objects dropped")
        except Exception as e:
            logger.error(f"[PostgreSQL] Cleanup failed: {e}")

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
        layer_info: LayerInfo = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate expression for PostgreSQL.

        Args:
            expression: Expression to validate
            layer_info: Target layer (optional, for backwards compatibility)

        Returns:
            Tuple of (is_valid, error_message)
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

        if errors:
            return False, "; ".join(errors)
        return True, None

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
            logger.warning(f"[PostgreSQL] Connection test failed: {e}")
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
            logger.error(f"[PostgreSQL] Failed to get connection: {e}")
            return None

    def _get_connection_from_layer(self, layer_id: str):
        """
        Get connection from QGIS layer when pool is not available.
        
        Args:
            layer_id: QGIS layer ID
            
        Returns:
            psycopg2 connection or None
        """
        try:
            from qgis.core import QgsProject
            from ....infrastructure.utils.layer_utils import get_datasource_connexion_from_layer
            
            # Get layer from QGIS project
            layer = QgsProject.instance().mapLayer(layer_id)
            if not layer:
                logger.warning(f"[PostgreSQL] Layer not found in project: {layer_id}")
                return None
            
            # Get connection from layer
            conn, _ = get_datasource_connexion_from_layer(layer)
            if conn:
                logger.debug(f"[PostgreSQL] Connection obtained from layer {layer_id}")
            else:
                logger.warning(f"[PostgreSQL] Could not get connection from layer {layer_id}")
            return conn
            
        except Exception as e:
            logger.error(f"[PostgreSQL] Failed to get connection from layer: {e}")
            return None

    def _ensure_schema(self) -> None:
        """Ensure filtermate schema exists."""
        try:
            conn = self._get_connection()
            if conn:
                self._cleanup_service.ensure_schema_exists(conn)
        except Exception as e:
            logger.warning(f"[PostgreSQL] Failed to ensure schema: {e}")

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

        logger.debug(f"[PostgreSQL] [PostgreSQL v4.0] DIRECT Query: {query[:500]}...")

        try:
            cursor = connection.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            logger.debug(f"[PostgreSQL] [PostgreSQL v4.0] DIRECT Results: {len(results)} rows")
            return [row[0] for row in results]
        except Exception as e:
            logger.error(f"[PostgreSQL] [PostgreSQL v4.0] Direct query FAILED: {e}")
            logger.error(f"[PostgreSQL] [PostgreSQL v4.0] Failed query: {query[:1000]}")
            raise

    def _get_table_name(self, layer_info: LayerInfo) -> str:
        """Extract table name from layer source."""
        # Parse from layer source_path
        # Format: "dbname=x user=y table=schema.table" or "table=\"schema\".\"table\""
        source = layer_info.source_path

        logger.debug(f"[PostgreSQL] [PostgreSQL v4.0] Extracting table from source: {source[:200]}...")

        # Try to extract table from source
        match = re.search(r'table=["\']?([^"\'"\s]+)["\']?', source)
        if match:
            table = match.group(1)
            logger.debug(f"[PostgreSQL] [PostgreSQL v4.0] Table extracted (method 1): {table}")
            return table

        # Try schema.table format
        match = re.search(r'table="([^"]+)"\.?"([^"]+)"', source)
        if match:
            table = f'"{match.group(1)}"."{match.group(2)}"'
            logger.debug(f"[PostgreSQL] [PostgreSQL v4.0] Table extracted (method 2): {table}")
            return table

        # Fallback to layer table_name
        if layer_info.table_name:
            if layer_info.schema_name:
                table = f'"{layer_info.schema_name}"."{layer_info.table_name}"'
            else:
                table = f'"{layer_info.table_name}"'
            logger.debug(f"[PostgreSQL] [PostgreSQL v4.0] Table from LayerInfo: {table}")
            return table

        logger.warning(f"[PostgreSQL] [PostgreSQL v4.0] Could not extract table name - using 'unknown_table'")
        return "unknown_table"

    def _get_geometry_column(self, layer_info: LayerInfo) -> str:
        """Get geometry column name."""
        # Use LayerInfo geometry_column attribute (fallback to common names)
        if layer_info.geometry_column:
            return layer_info.geometry_column
        # Common PostGIS geometry column names
        return "geom"

    def _get_pk_column(self, layer_info: LayerInfo) -> str:
        """Get primary key column name."""
        # Use LayerInfo pk_attr attribute (fallback to common names)
        if layer_info.pk_attr:
            return layer_info.pk_attr
        # Common PostgreSQL PK column names
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

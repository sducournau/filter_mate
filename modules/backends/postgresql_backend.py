# -*- coding: utf-8 -*-
"""
PostgreSQL Backend for FilterMate

Optimized backend for PostgreSQL/PostGIS databases.
Uses native PostGIS spatial functions and SQL queries for maximum performance.

Performance Strategy:
- Small datasets (< 10k features): Direct setSubsetString for simplicity
- Large datasets (≥ 10k features): Materialized views with GIST spatial indexes
- Custom buffers: Always use materialized views for geometry operations
"""

from typing import Dict, Optional
from qgis.core import QgsVectorLayer, QgsDataSourceUri
from .base_backend import GeometricFilterBackend
from ..logging_config import get_tasks_logger
from ..appUtils import safe_set_subset_string, get_datasource_connexion_from_layer, POSTGRESQL_AVAILABLE
import time
import uuid

logger = get_tasks_logger()


class PostgreSQLGeometricFilter(GeometricFilterBackend):
    """
    PostgreSQL/PostGIS backend for geometric filtering.
    
    This backend provides optimized filtering for PostgreSQL layers using:
    - Native PostGIS spatial functions (ST_Intersects, ST_Contains, etc.)
    - Efficient spatial indexes
    - SQL-based filtering for maximum performance
    """
    
    # Performance thresholds
    MATERIALIZED_VIEW_THRESHOLD = 10000  # Features count threshold for MV strategy
    LARGE_DATASET_THRESHOLD = 100000     # Features count for additional logging
    
    def __init__(self, task_params: Dict):
        """
        Initialize PostgreSQL backend.
        
        Args:
            task_params: Task parameters dictionary
        """
        super().__init__(task_params)
        self.logger = logger
        self.mv_schema = "public"  # Default schema for materialized views
        self.mv_prefix = "filtermate_mv_"  # Prefix for MV names
    
    def supports_layer(self, layer: QgsVectorLayer) -> bool:
        """
        Check if this backend supports the given layer.
        
        Args:
            layer: QGIS vector layer to check
        
        Returns:
            True if layer is from PostgreSQL provider
        """
        if not POSTGRESQL_AVAILABLE:
            self.log_warning("psycopg2 not available, PostgreSQL backend disabled")
            return False
        
        return layer.providerType() == 'postgres'
    
    def build_expression(
        self,
        layer_props: Dict,
        predicates: Dict,
        source_geom: Optional[str] = None,
        buffer_value: Optional[float] = None,
        buffer_expression: Optional[str] = None
    ) -> str:
        """
        Build PostGIS filter expression.
        
        Args:
            layer_props: Layer properties (schema, table, geometry field, etc.)
            predicates: Spatial predicates to apply
            source_geom: Source geometry expression
            buffer_value: Buffer distance
            buffer_expression: Expression for dynamic buffer
        
        Returns:
            PostGIS SQL expression string
        """
        self.log_debug(f"Building PostgreSQL expression for {layer_props.get('layer_name', 'unknown')}")
        
        # Extract layer properties
        schema = layer_props.get("layer_schema", "public")
        # Use layer_table_name (actual source table) if available, fallback to layer_name (display name)
        table = layer_props.get("layer_table_name") or layer_props.get("layer_name")
        geom_field = layer_props.get("layer_geometry_field", "geom")
        layer = layer_props.get("layer")  # QgsVectorLayer instance
        
        # CRITICAL FIX: Get actual geometry column name using QGIS API
        if layer:
            try:
                from qgis.core import QgsDataSourceUri
                
                provider = layer.dataProvider()
                uri_string = provider.dataSourceUri()
                
                # Parse the URI to get geometry column
                uri_obj = QgsDataSourceUri(uri_string)
                geom_col_from_uri = uri_obj.geometryColumn()
                
                if geom_col_from_uri:
                    geom_field = geom_col_from_uri
                    self.log_debug(f"Found geometry column from QgsDataSourceUri: '{geom_field}'")
                else:
                    self.log_debug(f"QgsDataSourceUri.geometryColumn() returned empty, using fallback")
                    
            except Exception as e:
                self.log_warning(f"Error detecting PostgreSQL geometry column: {e}")
        
        self.log_debug(f"Using geometry field: '{geom_field}'")
        
        # Build geometry expression
        geom_expr = f'"{table}"."{geom_field}"'
        
        # Apply buffer if specified
        if buffer_value and buffer_value > 0:
            geom_expr = f"ST_Buffer({geom_expr}, {buffer_value})"
        elif buffer_expression:
            geom_expr = f"ST_Buffer({geom_expr}, {buffer_expression})"
        
        # Build predicate expressions
        predicate_expressions = []
        for predicate_name, predicate_func in predicates.items():
            if source_geom:
                # Apply spatial predicate
                expr = f"{predicate_func}({geom_expr}, {source_geom})"
                predicate_expressions.append(expr)
        
        # Combine predicates with OR
        if predicate_expressions:
            combined = " OR ".join(predicate_expressions)
            self.log_debug(f"Built expression: {combined[:100]}...")
            return combined
        
        return ""
    
    def apply_filter(
        self,
        layer: QgsVectorLayer,
        expression: str,
        old_subset: Optional[str] = None,
        combine_operator: Optional[str] = None
    ) -> bool:
        """
        Apply filter to PostgreSQL layer.
        
        Strategy adapts based on dataset size:
        - Small datasets (< 10k features): Direct setSubsetString for simplicity
        - Large datasets (≥ 10k features): Materialized views with spatial indexes
        
        Args:
            layer: PostgreSQL layer to filter
            expression: PostGIS SQL expression
            old_subset: Existing subset string
            combine_operator: Operator to combine filters (AND/OR)
        
        Returns:
            True if filter applied successfully
        """
        start_time = time.time()
        
        try:
            if not expression:
                self.log_warning("Empty expression, skipping filter")
                return False
            
            # Get feature count to determine strategy
            feature_count = layer.featureCount()
            
            # Combine with existing filter if specified
            if old_subset:
                if not combine_operator:
                    combine_operator = 'AND'
                    self.log_info(f"🔗 Préservation du filtre existant avec {combine_operator}")
                self.log_info(f"  → Ancien subset: '{old_subset[:80]}...' (longueur: {len(old_subset)})")
                self.log_info(f"  → Nouveau filtre: '{expression[:80]}...' (longueur: {len(expression)})")
                final_expression = f"({old_subset}) {combine_operator} ({expression})"
                self.log_info(f"  → Expression combinée: longueur {len(final_expression)} chars")
            else:
                final_expression = expression
            
            # Decide strategy based on dataset size
            if feature_count >= self.MATERIALIZED_VIEW_THRESHOLD:
                # Large dataset - use materialized views
                if feature_count >= self.LARGE_DATASET_THRESHOLD:
                    self.log_info(
                        f"PostgreSQL: Very large dataset ({feature_count:,} features). "
                        f"Using materialized views with spatial index for optimal performance."
                    )
                else:
                    self.log_info(
                        f"PostgreSQL: Large dataset ({feature_count:,} features ≥ {self.MATERIALIZED_VIEW_THRESHOLD:,}). "
                        f"Using materialized views for better performance."
                    )
                
                return self._apply_with_materialized_view(layer, final_expression)
            else:
                # Small dataset - use direct setSubsetString
                self.log_info(
                    f"PostgreSQL: Small dataset ({feature_count:,} features < {self.MATERIALIZED_VIEW_THRESHOLD:,}). "
                    f"Using direct setSubsetString for simplicity."
                )
                
                return self._apply_direct(layer, final_expression)
            
        except Exception as e:
            self.log_error(f"Error applying filter: {str(e)}")
            import traceback
            self.log_debug(f"Traceback: {traceback.format_exc()}")
            return False
    
    def _apply_direct(self, layer: QgsVectorLayer, expression: str) -> bool:
        """
        Apply filter directly using setSubsetString (for small datasets).
        
        Simpler and faster for small datasets because it:
        - Avoids creating/dropping materialized views
        - Avoids creating spatial indexes
        - Uses PostgreSQL's query optimizer directly
        
        Args:
            layer: PostgreSQL layer to filter
            expression: PostGIS SQL expression
        
        Returns:
            True if successful
        """
        start_time = time.time()
        
        try:
            self.log_debug(f"Applying direct filter to {layer.name()}")
            self.log_debug(f"Expression: {expression[:200]}...")
            
            # Apply the filter (thread-safe)
            result = safe_set_subset_string(layer, expression)
            
            elapsed = time.time() - start_time
            
            if result:
                new_feature_count = layer.featureCount()
                self.log_info(
                    f"✓ Direct filter applied in {elapsed:.3f}s. "
                    f"{new_feature_count} features match."
                )
            else:
                self.log_error(f"Failed to apply direct filter to {layer.name()}")
            
            return result
            
        except Exception as e:
            self.log_error(f"Error applying direct filter: {str(e)}")
            return False
    
    def _apply_with_materialized_view(self, layer: QgsVectorLayer, expression: str) -> bool:
        """
        Apply filter using materialized views (for large datasets).
        
        Provides optimal performance for large datasets by:
        - Creating indexed materialized views on the server
        - Using GIST spatial indexes for fast spatial queries
        - Clustering data for sequential read optimization
        
        Args:
            layer: PostgreSQL layer to filter
            expression: PostGIS SQL expression
        
        Returns:
            True if successful
        """
        start_time = time.time()
        
        try:
            # Get database connection
            conn, source_uri = get_datasource_connexion_from_layer(layer)
            if not conn:
                self.log_error("Cannot get PostgreSQL connection, falling back to direct method")
                return self._apply_direct(layer, expression)
            
            cursor = conn.cursor()
            
            # Get layer properties
            schema = source_uri.schema() or "public"
            table = source_uri.table()
            geom_column = source_uri.geometryColumn()
            key_column = source_uri.keyColumn()
            
            if not key_column:
                # Try to find primary key
                from ..appUtils import get_primary_key_name
                key_column = get_primary_key_name(layer)
            
            if not key_column:
                self.log_warning("Cannot determine primary key, falling back to direct method")
                conn.close()
                return self._apply_direct(layer, expression)
            
            # Generate unique MV name
            mv_name = f"{self.mv_prefix}{uuid.uuid4().hex[:8]}"
            full_mv_name = f'"{schema}"."{mv_name}"'
            
            self.log_debug(f"Creating materialized view: {full_mv_name}")
            
            # Build SQL commands
            sql_drop = f'DROP MATERIALIZED VIEW IF EXISTS {full_mv_name} CASCADE;'
            
            # Build CREATE MATERIALIZED VIEW with WHERE clause
            sql_create = f'''
                CREATE MATERIALIZED VIEW {full_mv_name} AS
                SELECT * FROM "{schema}"."{table}"
                WHERE {expression}
                WITH DATA;
            '''
            
            # Create spatial index
            index_name = f"{mv_name}_gist_idx"
            sql_create_index = f'CREATE INDEX "{index_name}" ON {full_mv_name} USING GIST ("{geom_column}");'
            
            # Cluster on spatial index for better sequential read performance
            sql_cluster = f'CLUSTER {full_mv_name} USING "{index_name}";'
            
            # Analyze for query optimizer
            sql_analyze = f'ANALYZE {full_mv_name};'
            
            # Execute commands
            commands = [sql_drop, sql_create, sql_create_index, sql_cluster, sql_analyze]
            
            for i, cmd in enumerate(commands):
                self.log_debug(f"Executing PostgreSQL command {i+1}/{len(commands)}")
                cursor.execute(cmd)
                conn.commit()
            
            # Update layer to use materialized view
            layer_subset = f'"{key_column}" IN (SELECT "{key_column}" FROM {full_mv_name})'
            self.log_debug(f"Setting subset string: {layer_subset[:200]}...")
            
            result = safe_set_subset_string(layer, layer_subset)
            
            cursor.close()
            conn.close()
            
            elapsed = time.time() - start_time
            
            if result:
                new_feature_count = layer.featureCount()
                self.log_info(
                    f"✓ Materialized view created and filter applied in {elapsed:.2f}s. "
                    f"{new_feature_count} features match."
                )
            else:
                self.log_error(f"Failed to set subset string on layer")
            
            return result
            
        except Exception as e:
            self.log_error(f"Error creating materialized view: {str(e)}")
            import traceback
            self.log_debug(f"Traceback: {traceback.format_exc()}")
            
            # Cleanup and fallback
            try:
                if 'cursor' in locals():
                    cursor.close()
                if 'conn' in locals():
                    conn.close()
            except:
                pass
            
            self.log_info("Falling back to direct filter method")
            return self._apply_direct(layer, expression)
    
    def cleanup_materialized_views(self, layer: QgsVectorLayer) -> bool:
        """
        Cleanup materialized views created by this backend.
        
        Args:
            layer: PostgreSQL layer
        
        Returns:
            True if cleanup successful
        """
        try:
            conn, source_uri = get_datasource_connexion_from_layer(layer)
            if not conn:
                self.log_warning("Cannot get PostgreSQL connection for cleanup")
                return False
            
            cursor = conn.cursor()
            schema = source_uri.schema() or "public"
            
            # Find all FilterMate materialized views
            cursor.execute(f"""
                SELECT matviewname FROM pg_matviews 
                WHERE schemaname = '{schema}' 
                AND matviewname LIKE '{self.mv_prefix}%'
            """)
            
            views = cursor.fetchall()
            
            for (view_name,) in views:
                try:
                    cursor.execute(f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."{view_name}" CASCADE;')
                    conn.commit()
                    self.log_debug(f"Dropped materialized view: {view_name}")
                except Exception as e:
                    self.log_warning(f"Error dropping view {view_name}: {e}")
            
            cursor.close()
            conn.close()
            
            if views:
                self.log_info(f"Cleaned up {len(views)} materialized view(s)")
            
            return True
            
        except Exception as e:
            self.log_error(f"Error during cleanup: {str(e)}")
            return False
    
    def get_backend_name(self) -> str:
        """Get backend name"""
        return "PostgreSQL"

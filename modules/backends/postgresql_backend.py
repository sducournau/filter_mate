# -*- coding: utf-8 -*-
"""
PostgreSQL Backend for FilterMate

Optimized backend for PostgreSQL/PostGIS databases.
Uses native PostGIS spatial functions and SQL queries for maximum performance.

Performance Strategy:
- Small datasets (< 10k features): Direct setSubsetString for simplicity
- Large datasets (≥ 10k features): Materialized views with GIST spatial indexes
- Custom buffers: Always use materialized views for geometry operations

v2.4.0 Performance Improvements:
- Connection pooling to avoid ~50-100ms connection overhead per query
- Batch metadata loading for multiple layers
- Server-side cursors for streaming large result sets
"""

from typing import Dict, Optional
from qgis.core import QgsVectorLayer, QgsDataSourceUri
from .base_backend import GeometricFilterBackend
from ..logging_config import get_tasks_logger
from ..appUtils import safe_set_subset_string, get_datasource_connexion_from_layer, POSTGRESQL_AVAILABLE
import time
import uuid

logger = get_tasks_logger()

# Import MV Registry for cleanup management (v2.4.0)
try:
    from .mv_registry import get_mv_registry, MVRegistry
    MV_REGISTRY_AVAILABLE = True
except ImportError:
    MV_REGISTRY_AVAILABLE = False
    get_mv_registry = None
    MVRegistry = None

# Import connection pooling for optimized PostgreSQL operations
try:
    from ..connection_pool import (
        get_pool_manager,
        pooled_connection_from_layer,
        POSTGRESQL_AVAILABLE as POOL_AVAILABLE
    )
    CONNECTION_POOL_AVAILABLE = POOL_AVAILABLE
except ImportError:
    CONNECTION_POOL_AVAILABLE = False
    get_pool_manager = None
    pooled_connection_from_layer = None


class PostgreSQLGeometricFilter(GeometricFilterBackend):
    """
    PostgreSQL/PostGIS backend for geometric filtering.
    
    This backend provides optimized filtering for PostgreSQL layers using:
    - Native PostGIS spatial functions (ST_Intersects, ST_Contains, etc.)
    - Efficient spatial indexes
    - SQL-based filtering for maximum performance
    
    Strategy by source feature count:
    - Tiny (< 50): Direct WKT geometry literal (simplest, no subquery)
    - Small (< 10k): EXISTS subquery with source filter
    - Large (≥ 10k): Materialized views with spatial indexes
    """
    
    # Performance thresholds
    SIMPLE_WKT_THRESHOLD = 50            # Use direct WKT for very small source datasets
    MATERIALIZED_VIEW_THRESHOLD = 10000  # Features count threshold for MV strategy
    LARGE_DATASET_THRESHOLD = 100000     # Features count for additional logging
    
    # Predicate ordering for performance optimization
    # Most selective/fastest predicates first = better query plans
    # disjoint is fastest (eliminates most), equals is slowest (most expensive comparison)
    PREDICATE_ORDER = {
        'disjoint': 1,     # ST_Disjoint - fastest, eliminates most features
        'intersects': 2,   # ST_Intersects - fast with spatial index
        'touches': 3,      # ST_Touches - fast boundary check
        'crosses': 4,      # ST_Crosses - moderate
        'within': 5,       # ST_Within - moderate, uses index
        'contains': 6,     # ST_Contains - expensive
        'overlaps': 7,     # ST_Overlaps - expensive
        'equals': 8,       # ST_Equals - most expensive comparison
    }
    
    # MV optimization flags
    ENABLE_MV_CLUSTER = True       # CLUSTER operation (improves seq scans but slow to create)
    ENABLE_MV_ANALYZE = True       # ANALYZE for query optimizer statistics
    ENABLE_MV_UNLOGGED = True      # UNLOGGED MV (30-50% faster, no crash recovery)
    MV_INDEX_FILLFACTOR = 90       # Index fill factor (90 = good for read-heavy, 70 = for updates)
    
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

    def _get_buffer_endcap_style(self) -> str:
        """
        Get the PostGIS buffer endcap style from task_params.
        
        PostGIS ST_Buffer supports 'endcap' parameter:
        - 'round' (default)
        - 'flat' 
        - 'square'
        
        Returns:
            PostGIS endcap style string
        """
        if not self.task_params:
            return 'round'
        
        filtering_params = self.task_params.get("filtering", {})
        if not filtering_params.get("has_buffer_type", False):
            return 'round'
        
        buffer_type_str = filtering_params.get("buffer_type", "Round")
        
        # Map FilterMate buffer types to PostGIS endcap styles
        buffer_type_mapping = {
            "Round": "round",
            "Flat": "flat", 
            "Square": "square"
        }
        
        endcap_style = buffer_type_mapping.get(buffer_type_str, "round")
        self.log_debug(f"Using buffer endcap style: {endcap_style}")
        return endcap_style
    
    def _build_st_buffer_with_style(self, geom_expr: str, buffer_value: float) -> str:
        """
        Build ST_Buffer expression with endcap style from task_params.
        
        Args:
            geom_expr: Geometry expression to buffer
            buffer_value: Buffer distance
            
        Returns:
            PostGIS ST_Buffer expression with style parameter
        """
        endcap_style = self._get_buffer_endcap_style()
        
        if endcap_style == 'round':
            # Default style - no need to specify
            return f"ST_Buffer({geom_expr}, {buffer_value})"
        else:
            # Use optional style parameter
            return f"ST_Buffer({geom_expr}, {buffer_value}, 'endcap={endcap_style}')"
    
    def supports_layer(self, layer: QgsVectorLayer) -> bool:
        """
        Check if this backend supports the given layer.
        
        Tests both provider type AND connection availability. If the layer
        is PostgreSQL but connection fails (wrong credentials, server down, etc.),
        returns False to allow fallback to OGR backend.
        
        Args:
            layer: QGIS vector layer to check
        
        Returns:
            True if layer is from PostgreSQL provider AND connection works
        """
        if not POSTGRESQL_AVAILABLE:
            self.log_warning("psycopg2 not available, PostgreSQL backend disabled")
            return False
        
        if layer.providerType() != 'postgres':
            return False
        
        # CRITICAL: Test actual connection - may fail with authcfg or network issues
        # PERFORMANCE v2.4.0: Use connection pooling if available
        try:
            if CONNECTION_POOL_AVAILABLE and pooled_connection_from_layer:
                # Use pooled connection (more efficient for repeated checks)
                with pooled_connection_from_layer(layer) as (conn, source_uri):
                    if conn is None:
                        self.log_warning(f"PostgreSQL connection failed for layer {layer.name()} (pooled), will use OGR fallback")
                        return False
                    # Test connection with simple query
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT 1")
                    return True
            else:
                # Fallback to non-pooled connection
                conn, source_uri = get_datasource_connexion_from_layer(layer)
                if conn is None:
                    self.log_warning(f"PostgreSQL connection failed for layer {layer.name()}, will use OGR fallback")
                    return False
                # Test connection with simple query
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                conn.close()
                return True
        except Exception as e:
            self.log_warning(f"PostgreSQL connection test failed for layer {layer.name()}: {e}, will use OGR fallback")
            return False

    def _parse_source_table_reference(self, source_geom: str) -> Optional[Dict]:
        """
        Parse source geometry expression to detect table references.
        
        PostgreSQL source_geom can have several formats:
        1. "schema"."table"."geom" - direct table reference
        2. "mv_xxx_dump"."geom" - materialized view reference
        3. ST_Buffer("schema"."table"."geom", value) - with buffer
        4. "table"."geom" - table reference without schema (uses default "public")
        5. ST_Buffer("table"."geom", value) - buffer without schema
        
        For formats 1, 3, 4, 5 we need to use EXISTS subquery in setSubsetString.
        For format 2 (materialized view), it's OK to use direct reference.
        
        Args:
            source_geom: Source geometry SQL expression
        
        Returns:
            Dict with schema, table, geom_field, and optional buffer_expr, or None if not a table reference
        """
        import re
        
        # Get buffer endcap style for use in buffer expressions
        endcap_style = self._get_buffer_endcap_style()
        
        def build_buffer_expr(geom_ref: str, buffer_value: str) -> str:
            """Build ST_Buffer expression with appropriate endcap style."""
            if endcap_style == 'round':
                return f'ST_Buffer({geom_ref}, {buffer_value})'
            else:
                return f"ST_Buffer({geom_ref}, {buffer_value}, 'endcap={endcap_style}')"
        
        # Pattern 1: ST_Buffer("schema"."table"."geom", value) - 3-part with buffer
        buffer_pattern_3part = r'ST_Buffer\s*\(\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*,\s*([^)]+)\)'
        match = re.match(buffer_pattern_3part, source_geom, re.IGNORECASE)
        if match:
            schema, table, geom_field, buffer_value = match.groups()
            return {
                'schema': schema,
                'table': table,
                'geom_field': geom_field,
                'buffer_expr': build_buffer_expr(f'__source."{geom_field}"', buffer_value)
            }
        
        # Pattern 2: ST_Buffer("table"."geom", value) - 2-part with buffer (no schema)
        buffer_pattern_2part = r'ST_Buffer\s*\(\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*,\s*([^)]+)\)'
        match = re.match(buffer_pattern_2part, source_geom, re.IGNORECASE)
        if match:
            table, geom_field, buffer_value = match.groups()
            # Skip materialized views - they're safe to reference directly
            if table.startswith('mv_') and table.endswith('_dump'):
                self.log_debug(f"Source is materialized view '{table}' with buffer - using direct reference")
                return None
            self.log_debug(f"Detected 2-part buffer reference: table='{table}', geom='{geom_field}', using schema='public'")
            return {
                'schema': 'public',
                'table': table,
                'geom_field': geom_field,
                'buffer_expr': build_buffer_expr(f'__source."{geom_field}"', buffer_value)
            }
        
        # Pattern 3: "schema"."table"."geom" (3-part identifier)
        three_part_pattern = r'\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"'
        match = re.match(three_part_pattern, source_geom)
        if match:
            schema, table, geom_field = match.groups()
            # Skip materialized views - they're safe to reference directly
            if table.startswith('mv_') and table.endswith('_dump'):
                self.log_debug(f"Source is materialized view '{table}' - using direct reference")
                return None
            return {
                'schema': schema,
                'table': table,
                'geom_field': geom_field
            }
        
        # Pattern 4: "table"."geom" (2-part, table reference without schema)
        # CRITICAL FIX: Handle 2-part table references for regular tables, not just MVs
        two_part_pattern = r'\"([^\"]+)\"\s*\.\s*\"([^\"]+)\"'
        match = re.match(two_part_pattern, source_geom)
        if match:
            table, geom_field = match.groups()
            # Skip materialized views - they're safe to reference directly
            if table.startswith('mv_') and table.endswith('_dump'):
                self.log_debug(f"Source is materialized view '{table}' - using direct reference")
                return None
            # CRITICAL FIX: For regular tables without schema, use default schema "public"
            # This ensures EXISTS subquery is used to avoid "missing FROM-clause entry" error
            self.log_debug(f"Detected 2-part table reference: table='{table}', geom='{geom_field}', using schema='public'")
            return {
                'schema': 'public',
                'table': table,
                'geom_field': geom_field
            }
        
        # Not a table reference (could be WKT, ST_GeomFromText, etc.)
        self.log_debug(f"Source geometry is not a table reference - using direct expression")
        return None

    def _adapt_filter_for_subquery(self, filter_expr: str, schema: str, table: str) -> str:
        """
        Adapt a filter expression to work inside an EXISTS subquery.
        
        Replaces qualified table references like "schema"."table"."column" or "table"."column"
        with the subquery alias __source."column".
        
        Also strips outer parentheses to avoid syntax errors when combining with AND.
        
        Examples:
            Input:  "Distribution Cluster"."id" = 1
            Output: __source."id" = 1
            
            Input:  ("public"."Distribution Cluster"."id" = 1)
            Output: __source."id" = 1
            
            Input:  (("Structures"."SUB_TYPE" = 'Facade Point'))
            Output: __source."SUB_TYPE" = 'Facade Point'
        
        Args:
            filter_expr: Original filter expression with qualified table names
            schema: Schema name to replace
            table: Table name to replace
        
        Returns:
            Adapted filter expression using __source alias
        """
        import re
        
        def strip_balanced_outer_parens(expr: str) -> str:
            """
            Strip balanced outer parentheses from expression.
            
            Only strips if the opening '(' at position 0 matches the closing ')' at the end.
            Uses a proper parenthesis counting algorithm to verify balance.
            """
            expr = expr.strip()
            while expr.startswith('(') and expr.endswith(')'):
                # Check if these are matching outer parentheses
                # by ensuring the closing paren matches the opening one
                depth = 0
                is_outer = True
                for i, char in enumerate(expr):
                    if char == '(':
                        depth += 1
                    elif char == ')':
                        depth -= 1
                        if depth == 0 and i < len(expr) - 1:
                            # Found a closing paren before the end - not outer parens
                            is_outer = False
                            break
                if is_outer and depth == 0:
                    expr = expr[1:-1].strip()
                else:
                    break
            return expr
        
        # Step 1: Strip outer parentheses BEFORE regex substitution
        filter_expr = strip_balanced_outer_parens(filter_expr)
        
        # Step 2: Apply regex substitutions for table references
        # Pattern 1: "schema"."table"."column" -> __source."column"
        three_part_pattern = rf'"{re.escape(schema)}"\s*\.\s*"{re.escape(table)}"\s*\.\s*"([^"]+)"'
        adapted = re.sub(three_part_pattern, r'__source."\1"', filter_expr)
        
        # Pattern 2: "table"."column" -> __source."column"
        two_part_pattern = rf'"{re.escape(table)}"\s*\.\s*"([^"]+)"'
        adapted = re.sub(two_part_pattern, r'__source."\1"', adapted)
        
        # Step 3: CRITICAL FIX - Strip outer parentheses AFTER regex substitution
        # The regex may have changed the structure, leaving orphan parentheses
        # Example: (("Structures"."col" = 'val')) -> ((__source."col" = 'val')) -> __source."col" = 'val'
        adapted = strip_balanced_outer_parens(adapted)
        
        # Step 4: Validate parentheses balance to catch any edge cases
        open_count = adapted.count('(')
        close_count = adapted.count(')')
        if open_count != close_count:
            self.log_warning(f"⚠️ Unbalanced parentheses in adapted filter: {open_count} open vs {close_count} close")
            self.log_warning(f"  → Original: '{filter_expr[:100]}'...")
            self.log_warning(f"  → Adapted: '{adapted[:100]}'...")
            
            # CRITICAL FIX: Remove trailing unmatched parentheses more aggressively
            # This handles cases where multiple closing parens are orphaned
            while adapted.count(')') > adapted.count('('):
                # Find and remove the last closing paren
                last_close_idx = adapted.rfind(')')
                if last_close_idx != -1:
                    adapted = adapted[:last_close_idx] + adapted[last_close_idx+1:]
                    adapted = adapted.strip()
                    self.log_info(f"  → Removed trailing ')': '{adapted[:100]}'...")
                else:
                    break
            
            # Also remove leading unmatched opening parentheses if any
            while adapted.count('(') > adapted.count(')'):
                first_open_idx = adapted.find('(')
                if first_open_idx != -1:
                    adapted = adapted[:first_open_idx] + adapted[first_open_idx+1:]
                    adapted = adapted.strip()
                    self.log_info(f"  → Removed leading '(': '{adapted[:100]}'...")
                else:
                    break
        
        return adapted

    def _normalize_column_case(self, expression: str, layer: QgsVectorLayer) -> str:
        """
        Normalize column names in expression to match actual PostgreSQL column case.
        
        PostgreSQL is case-sensitive for quoted identifiers. If columns were created
        without quotes (standard practice), they are stored in lowercase.
        QGIS may display or store field names with different case, causing
        "column X does not exist" errors.
        
        This function corrects column names in filter expressions to match the
        actual column names from the layer's field list.
        
        Example: "SUB_TYPE" → "sub_type" if the actual column is "sub_type"
        
        Args:
            expression: SQL expression string with potentially incorrect column case
            layer: QgsVectorLayer to get actual field names from
        
        Returns:
            Expression with corrected column names
        """
        import re
        
        if not expression or not layer:
            return expression
        
        # Get actual field names from layer
        field_names = [field.name() for field in layer.fields()]
        if not field_names:
            return expression
        
        result_expression = expression
        
        # Build case-insensitive lookup map: lowercase → actual name
        field_lookup = {name.lower(): name for name in field_names}
        
        # Find all quoted column names in expression (e.g., "SUB_TYPE")
        # This regex finds quoted identifiers: "something"
        quoted_cols = re.findall(r'"([^"]+)"', result_expression)
        
        corrections_made = []
        for col_name in quoted_cols:
            # Skip if column exists with exact case (no correction needed)
            if col_name in field_names:
                continue
            
            # Skip known non-column identifiers (schemas, tables, aliases)
            # These are typically lowercase already or are special identifiers
            if col_name in ['__source', 'public', 'geometry', 'geom']:
                continue
            
            # Check for case-insensitive match
            col_lower = col_name.lower()
            if col_lower in field_lookup:
                correct_name = field_lookup[col_lower]
                if col_name != correct_name:  # Only replace if actually different
                    # Replace the incorrectly cased column name with correct one
                    result_expression = result_expression.replace(
                        f'"{col_name}"',
                        f'"{correct_name}"'
                    )
                    corrections_made.append(f'"{col_name}" → "{correct_name}"')
        
        if corrections_made:
            self.log_info(f"🔧 PostgreSQL column case normalization: {', '.join(corrections_made)}")
        
        return result_expression

    def _build_simple_wkt_expression(
        self,
        geom_expr: str,
        predicate_func: str,
        source_wkt: str,
        source_srid: int,
        buffer_value: Optional[float] = None
    ) -> str:
        """
        Build a simple PostGIS expression using direct WKT geometry literal.
        
        This is the simplest and most efficient method for small source datasets.
        Instead of using EXISTS subquery, we embed the source geometry directly.
        
        Args:
            geom_expr: Target layer geometry expression (e.g., "table"."geom")
            predicate_func: PostGIS predicate (e.g., "ST_Intersects")
            source_wkt: WKT string of source geometry (already merged/unioned)
            source_srid: SRID of the source geometry
            buffer_value: Optional buffer to apply to source geometry
        
        Returns:
            Simple PostGIS expression like:
            ST_Intersects("table"."geom", ST_GeomFromText('POLYGON(...)', 31370))
        """
        # Build source geometry from WKT
        source_geom_sql = f"ST_GeomFromText('{source_wkt}', {source_srid})"
        
        # Apply buffer if specified (with endcap style)
        if buffer_value and buffer_value > 0:
            source_geom_sql = self._build_st_buffer_with_style(source_geom_sql, buffer_value)
        
        return f"{predicate_func}({geom_expr}, {source_geom_sql})"

    def build_expression(
        self,
        layer_props: Dict,
        predicates: Dict,
        source_geom: Optional[str] = None,
        buffer_value: Optional[float] = None,
        buffer_expression: Optional[str] = None,
        source_filter: Optional[str] = None,
        source_wkt: Optional[str] = None,
        source_srid: Optional[int] = None,
        source_feature_count: Optional[int] = None
    ) -> str:
        """
        Build PostGIS filter expression.
        
        Strategy based on source feature count:
        - Tiny (< SIMPLE_WKT_THRESHOLD): Use direct WKT geometry literal (simplest)
        - Larger: Use EXISTS subquery with source filter
        
        Args:
            layer_props: Layer properties (schema, table, geometry field, etc.)
            predicates: Spatial predicates to apply
            source_geom: Source geometry expression (table reference for EXISTS)
            buffer_value: Buffer distance
            buffer_expression: Expression for dynamic buffer
            source_filter: Optional filter expression for source layer (for EXISTS subqueries)
            source_wkt: Optional WKT string for simple mode (when few source features)
            source_srid: SRID for the source WKT geometry
            source_feature_count: Number of source features (to choose strategy)
        
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
        
        # Apply buffer if specified (with endcap style from task_params)
        if buffer_value and buffer_value > 0:
            geom_expr = self._build_st_buffer_with_style(geom_expr, buffer_value)
        elif buffer_expression:
            # Dynamic buffer expression - use endcap style
            endcap_style = self._get_buffer_endcap_style()
            if endcap_style == 'round':
                geom_expr = f"ST_Buffer({geom_expr}, {buffer_expression})"
            else:
                geom_expr = f"ST_Buffer({geom_expr}, {buffer_expression}, 'endcap={endcap_style}')"
        
        # Determine strategy based on source feature count
        use_simple_wkt = (
            source_wkt is not None and 
            source_srid is not None and
            source_feature_count is not None and
            source_feature_count <= self.SIMPLE_WKT_THRESHOLD
        )
        
        if use_simple_wkt:
            self.log_info(f"📝 Using SIMPLE WKT mode for {layer_props.get('layer_name', 'unknown')}")
            self.log_info(f"  - Source features: {source_feature_count} (≤ {self.SIMPLE_WKT_THRESHOLD} threshold)")
            self.log_info(f"  - WKT length: {len(source_wkt)} chars, SRID: {source_srid}")
        
        # Build predicate expressions with OPTIMIZED order
        # Sort predicates for better query performance:
        # - Most selective predicates first = faster short-circuit evaluation
        # - PostgreSQL query planner benefits from predicate ordering
        predicate_expressions = []
        
        # Extract and sort predicates by optimal order
        predicate_items = []
        for key, func in predicates.items():
            # Extract predicate name from function name (e.g., 'ST_Intersects' -> 'intersects')
            predicate_lower = key.lower().replace('st_', '')
            order = self.PREDICATE_ORDER.get(predicate_lower, 99)
            predicate_items.append((key, func, order))
        
        # Sort by order (most selective first)
        predicate_items.sort(key=lambda x: x[2])
        
        if len(predicate_items) > 1:
            self.log_debug(f"Predicates reordered for performance: {[p[0] for p in predicate_items]}")
        
        for predicate_name, predicate_func, _ in predicate_items:
            # STRATEGY 1: Simple WKT mode (few source features)
            # Use direct ST_GeomFromText() - simplest and most efficient for small datasets
            if use_simple_wkt:
                expr = self._build_simple_wkt_expression(
                    geom_expr=geom_expr,
                    predicate_func=predicate_func,
                    source_wkt=source_wkt,
                    source_srid=source_srid,
                    buffer_value=None  # Buffer already applied to geom_expr if needed
                )
                self.log_debug(f"  ✓ Simple WKT expression: {expr[:100]}...")
                predicate_expressions.append(expr)
                continue
            
            # STRATEGY 2: EXISTS subquery mode (many source features or no WKT available)
            if source_geom:
                # CRITICAL FIX: Detect if source_geom references another table
                # Pattern: "schema"."table"."column" or ST_Buffer("schema"."table"."column", value)
                # In these cases, we MUST use EXISTS subquery because setSubsetString 
                # cannot reference other tables directly (would cause "missing FROM-clause entry" error)
                
                # Parse source_geom to extract table reference
                source_table_ref = self._parse_source_table_reference(source_geom)
                
                if source_table_ref:
                    # Use EXISTS subquery to avoid "missing FROM-clause entry" error
                    source_schema_name = source_table_ref['schema']
                    source_table_name = source_table_ref['table']
                    source_geom_field = source_table_ref['geom_field']
                    source_has_buffer = source_table_ref.get('buffer_expr')
                    
                    # Build source geometry expression within subquery
                    if source_has_buffer:
                        source_geom_in_subquery = source_has_buffer
                    else:
                        source_geom_in_subquery = f'__source."{source_geom_field}"'
                    
                    # CRITICAL FIX: Include source layer filter in EXISTS subquery
                    # When source layer is filtered (via setSubsetString), we must
                    # only match against the filtered features, not the entire table
                    where_clauses = [f'{predicate_func}({geom_expr}, {source_geom_in_subquery})']
                    
                    self.log_info(f"🔧 Building EXISTS subquery for {layer_props.get('layer_name', 'unknown')}")
                    self.log_info(f"  - Source filter provided: {source_filter is not None}")
                    
                    if source_filter:
                        # CRITICAL FIX: Validate source_filter before using
                        # If source_filter already contains spatial predicates or __source alias,
                        # it's from a previous geometric filter and should NOT be included
                        # This prevents SQL duplication errors like:
                        # EXISTS(...WHERE ST_Intersects(...)) AND (ST_Intersects(...))
                        source_filter_upper = source_filter.upper()
                        is_spatial_filter = any(pred in source_filter_upper for pred in [
                            'ST_INTERSECTS', 'ST_CONTAINS', 'ST_WITHIN', 'ST_TOUCHES',
                            'ST_OVERLAPS', 'ST_CROSSES', 'ST_DISJOINT', 'ST_EQUALS',
                            '__SOURCE', 'EXISTS(', 'EXISTS ('
                        ])
                        
                        if is_spatial_filter:
                            self.log_warning(f"  ⚠️ Source filter contains spatial predicates or __source alias - SKIPPING")
                            self.log_warning(f"  → Filter: '{source_filter[:100]}'...")
                            self.log_warning(f"  → This is likely from a previous geometric filter operation")
                            self.log_warning(f"  → Only the spatial predicate will be used (no attribute filter)")
                        else:
                            # CRITICAL: Replace table references with __source alias
                            # The source_filter comes from setSubsetString and contains qualified table names
                            # like "Distribution Cluster"."id" which must become __source."id"
                            self.log_info(f"  - Original source filter: '{source_filter[:100]}'...")
                            adapted_filter = self._adapt_filter_for_subquery(
                                source_filter, 
                                source_schema_name, 
                                source_table_name
                            )
                            # Add the adapted filter without extra parentheses
                            # The filter is already properly formatted by _adapt_filter_for_subquery
                            where_clauses.append(adapted_filter)
                            self.log_info(f"  - Adapted filter: '{adapted_filter[:100]}'...")
                            self.log_info(f"  - WHERE clause will be: predicate AND adapted_filter")
                    
                    where_clause = ' AND '.join(where_clauses)
                    
                    # Build EXISTS subquery
                    expr = (
                        f'EXISTS ('
                        f'SELECT 1 FROM "{source_schema_name}"."{source_table_name}" AS __source '
                        f'WHERE {where_clause}'
                        f')'
                    )
                    self.log_info(f"  ✓ Built EXISTS expression: '{expr[:150]}'...")
                    self.log_debug(f"Using EXISTS subquery to avoid missing FROM-clause error")
                else:
                    # Simple expression (WKT, geometry literal, etc.) - can use directly
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
            
            # CRITICAL FIX: Normalize column names in expression and old_subset
            # PostgreSQL is case-sensitive for quoted identifiers. Columns created without
            # quotes are stored lowercase, but QGIS may use uppercase (e.g., "SUB_TYPE").
            # This causes "column X does not exist" errors.
            expression = self._normalize_column_case(expression, layer)
            if old_subset:
                old_subset = self._normalize_column_case(old_subset, layer)
            
            # Get feature count to determine strategy
            feature_count = layer.featureCount()
            
            # Check if layer uses ctid (no primary key)
            from ..appUtils import get_primary_key_name
            key_column = get_primary_key_name(layer)
            uses_ctid = (key_column == 'ctid')
            
            # CRITICAL FIX: Clean invalid old_subset from previous failed operations
            # Invalid old_subset patterns that MUST be cleared:
            # 1. Contains __source alias (only valid inside EXISTS subqueries)
            # 2. Contains EXISTS subquery (would create nested EXISTS = complex/slow)
            # 3. Contains spatial predicates referencing other tables (cross-table filter)
            #
            # When these patterns are detected in old_subset, it means:
            # - A previous geometric filter operation left a corrupted/incompatible subset
            # - Combining with such subset would create invalid SQL syntax
            # - The new filter should completely replace the old one
            if old_subset:
                old_subset_upper = old_subset.upper()
                
                # Pattern 1: __source alias (invalid outside EXISTS)
                has_source_alias = '__source' in old_subset.lower()
                
                # Pattern 2: EXISTS subquery (avoid nested EXISTS)
                has_exists = 'EXISTS (' in old_subset_upper or 'EXISTS(' in old_subset_upper
                
                # Pattern 3: Spatial predicates that reference external tables
                # These indicate a cross-table spatial filter that should not be combined
                spatial_predicates = [
                    'ST_INTERSECTS', 'ST_CONTAINS', 'ST_WITHIN', 'ST_TOUCHES',
                    'ST_OVERLAPS', 'ST_CROSSES', 'ST_DISJOINT', 'ST_EQUALS',
                    'ST_DWITHIN', 'ST_COVERS', 'ST_COVEREDBY'
                ]
                has_spatial_predicate = any(pred in old_subset_upper for pred in spatial_predicates)
                
                # Determine if old_subset is invalid
                should_clear_old_subset = has_source_alias or has_exists or has_spatial_predicate
                
                if should_clear_old_subset:
                    reason = []
                    if has_source_alias:
                        reason.append("contains __source alias")
                    if has_exists:
                        reason.append("contains EXISTS subquery")
                    if has_spatial_predicate:
                        reason.append("contains spatial predicate (likely cross-table filter)")
                    
                    self.log_warning(f"⚠️ CRITICAL: Invalid old_subset detected - {', '.join(reason)}")
                    self.log_warning(f"  → Corrupted subset: '{old_subset[:150]}'...")
                    self.log_warning(f"  → This is from a previous geometric filtering operation")
                    self.log_warning(f"  → Clearing invalid subset to prevent SQL syntax errors")
                    # FORCE clear the invalid subset - DO NOT combine with it
                    old_subset = None
                    self.log_info(f"  ✓ Invalid subset cleared - will apply fresh filter")
            
            # Combine with existing filter if specified
            # CRITICAL: Don't combine in these cases:
            # 1. Expression already contains EXISTS subquery (source filter already integrated)
            # 2. old_subset was just cleared (was invalid)
            # 3. No explicit combine operator with EXISTS
            has_exists_subquery = 'EXISTS (' in expression.upper()
            
            # DIAGNOSTIC: Log detection results
            self.log_info(f"🔍 Filter combination check:")
            self.log_info(f"  - Expression contains EXISTS: {has_exists_subquery}")
            self.log_info(f"  - old_subset exists after cleanup: {old_subset is not None}")
            if old_subset:
                self.log_info(f"  - old_subset (valid): '{old_subset[:80]}'...")
            self.log_info(f"  - combine_operator: {combine_operator}")
            
            # CRITICAL FIX: When EXISTS subquery contains the source filter adapted inside it,
            # DO NOT combine with old_subset again (would create duplicate conditions with syntax error)
            # The source filter is already integrated in the WHERE clause of the EXISTS subquery
            # Example: EXISTS (SELECT 1 FROM ... WHERE ST_Intersects(...) AND __source."id" = '17')
            # If we combine with old_subset containing the same filter, we get:
            # (old_filter) AND (EXISTS(...AND adapted_filter)) which creates an invalid double condition
            should_skip_combination = (
                has_exists_subquery or 
                (old_subset and combine_operator is None)  # Don't auto-combine if no explicit operator
            )
            
            self.log_info(f"  → should_skip_combination: {should_skip_combination}")
            
            if old_subset and not should_skip_combination:
                if not combine_operator:
                    combine_operator = 'AND'
                    self.log_info(f"🔗 Préservation du filtre existant avec {combine_operator}")
                self.log_info(f"  → Ancien subset: '{old_subset[:80]}...' (longueur: {len(old_subset)})")
                self.log_info(f"  → Nouveau filtre: '{expression[:80]}...' (longueur: {len(expression)})")
                final_expression = f"({old_subset}) {combine_operator} ({expression})"
                self.log_info(f"  → Expression combinée: longueur {len(final_expression)} chars")
            else:
                if has_exists_subquery and old_subset:
                    self.log_info(f"✓ EXISTS subquery detected - source filter already integrated in WHERE clause, skipping combination")
                    self.log_info(f"  → Expression already contains source filter adapted for __source alias")
                if old_subset and combine_operator is None and has_exists_subquery:
                    self.log_info(f"✓ No explicit combine operator with EXISTS subquery - using expression as-is")
                final_expression = expression
            
            # Decide strategy based on dataset size and primary key availability
            if uses_ctid:
                # No primary key (using ctid) - MUST use direct method
                self.log_info(
                    f"PostgreSQL: Layer without PRIMARY KEY (using ctid). "
                    f"Using direct filtering (materialized views disabled)."
                )
                return self._apply_direct(layer, final_expression)
            
            elif feature_count >= self.MATERIALIZED_VIEW_THRESHOLD:
                # Large dataset with PK - use materialized views
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
    
    def _get_fast_feature_count(self, layer: QgsVectorLayer, conn) -> int:
        """
        Get fast feature count estimation using PostgreSQL statistics.
        
        This avoids expensive COUNT(*) queries by using pg_stat_user_tables.
        Falls back to layer.featureCount() if statistics unavailable.
        
        Args:
            layer: PostgreSQL layer
            conn: Database connection
            
        Returns:
            Estimated feature count
        """
        try:
            cursor = conn.cursor()
            source_uri = QgsDataSourceUri(layer.source())
            schema = source_uri.schema() or "public"
            table = source_uri.table()
            
            # Try to get estimated count from PostgreSQL statistics
            # This is MUCH faster than COUNT(*) for large tables
            cursor.execute(f"""
                SELECT n_live_tup 
                FROM pg_stat_user_tables 
                WHERE schemaname = '{schema}' 
                AND tablename = '{table}'
            """)
            
            result = cursor.fetchone()
            cursor.close()
            
            if result and result[0] is not None:
                estimated_count = result[0]
                self.log_debug(f"Using PostgreSQL statistics: ~{estimated_count:,} features")
                return estimated_count
            else:
                # Fallback: use QGIS feature count (slower but accurate)
                self.log_debug("PostgreSQL statistics unavailable, using layer.featureCount()")
                return layer.featureCount()
                
        except Exception as e:
            self.log_debug(f"Error getting fast count: {e}, falling back to featureCount()")
            return layer.featureCount()
    
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
        - Optional clustering for sequential read optimization (configurable)
        
        Performance optimizations:
        - Index FILLFACTOR tuning for read-heavy workloads
        - Optional CLUSTER (can be slow, disabled for very large datasets)
        - ANALYZE for query optimizer statistics
        - Batch transaction for faster execution
        
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
            
            # CRITICAL: ctid cannot be used in materialized views
            # ctid is PostgreSQL's internal row identifier, not a real column
            if not key_column or key_column == 'ctid':
                if key_column == 'ctid':
                    self.log_warning(
                        f"Layer '{layer.name()}' uses 'ctid' (no PRIMARY KEY). "
                        f"Materialized views disabled, using direct filtering."
                    )
                else:
                    self.log_warning("Cannot determine primary key, falling back to direct method")
                conn.close()
                return self._apply_direct(layer, expression)
            
            # Generate unique MV name
            mv_name = f"{self.mv_prefix}{uuid.uuid4().hex[:8]}"
            full_mv_name = f'"{schema}"."{mv_name}"'
            
            self.log_debug(f"Creating materialized view: {full_mv_name}")
            
            # Get estimated row count for optimization decisions
            # Use fast estimation to avoid expensive COUNT(*)
            feature_count = self._get_fast_feature_count(layer, conn)
            
            # Build SQL commands
            commands = []
            command_names = []
            
            # 1. Drop existing MV if any
            sql_drop = f'DROP MATERIALIZED VIEW IF EXISTS {full_mv_name} CASCADE;'
            commands.append(sql_drop)
            command_names.append("DROP MV")
            
            # 2. Create MV with optimized settings
            # UNLOGGED: 30-50% faster creation, no WAL overhead
            # Perfect for temporary filtering views (no durability needed)
            unlogged_clause = "UNLOGGED" if self.ENABLE_MV_UNLOGGED else ""
            sql_create = f'''
                CREATE {unlogged_clause} MATERIALIZED VIEW {full_mv_name} AS
                SELECT * FROM "{schema}"."{table}"
                WHERE {expression}
                WITH DATA;
            '''
            commands.append(sql_create)
            command_names.append("CREATE MV" + (" (UNLOGGED)" if self.ENABLE_MV_UNLOGGED else ""))
            
            # 3. Create spatial index with FILLFACTOR optimization
            index_name = f"{mv_name}_gist_idx"
            sql_create_index = (
                f'CREATE INDEX "{index_name}" ON {full_mv_name} '
                f'USING GIST ("{geom_column}") '
                f'WITH (FILLFACTOR = {self.MV_INDEX_FILLFACTOR});'
            )
            commands.append(sql_create_index)
            command_names.append("CREATE INDEX")
            
            # 4. Create index on primary key for fast lookups
            pk_index_name = f"{mv_name}_pk_idx"
            sql_create_pk_index = f'CREATE INDEX "{pk_index_name}" ON {full_mv_name} ("{key_column}");'
            commands.append(sql_create_pk_index)
            command_names.append("CREATE PK INDEX")
            
            # 5. CLUSTER - optional, can be slow for large datasets (> 100k features)
            # CLUSTER reorganizes data on disk for better sequential reads
            # Skip for very large datasets as it can take a long time
            if self.ENABLE_MV_CLUSTER and feature_count < self.LARGE_DATASET_THRESHOLD:
                sql_cluster = f'CLUSTER {full_mv_name} USING "{index_name}";'
                commands.append(sql_cluster)
                command_names.append("CLUSTER")
            elif feature_count >= self.LARGE_DATASET_THRESHOLD:
                self.log_info(f"⚡ Skipping CLUSTER for performance (dataset > {self.LARGE_DATASET_THRESHOLD:,} features)")
            
            # 6. ANALYZE for query optimizer
            if self.ENABLE_MV_ANALYZE:
                sql_analyze = f'ANALYZE {full_mv_name};'
                commands.append(sql_analyze)
                command_names.append("ANALYZE")
            
            # Execute commands with timing
            total_steps = len(commands)
            step_times = []
            
            for i, (cmd, cmd_name) in enumerate(zip(commands, command_names)):
                step_start = time.time()
                self.log_debug(f"Executing {cmd_name} ({i+1}/{total_steps})")
                cursor.execute(cmd)
                conn.commit()
                step_time = time.time() - step_start
                step_times.append((cmd_name, step_time))
                
                # Log slow operations
                if step_time > 1.0:
                    self.log_debug(f"  ⏱️ {cmd_name} took {step_time:.2f}s")
            
            # Update layer to use materialized view
            layer_subset = f'"{key_column}" IN (SELECT "{key_column}" FROM {full_mv_name})'
            self.log_debug(f"Setting subset string: {layer_subset[:200]}...")
            
            result = safe_set_subset_string(layer, layer_subset)
            
            # Register MV for cleanup tracking (v2.4.0)
            if MV_REGISTRY_AVAILABLE and result:
                try:
                    registry = get_mv_registry()
                    registry.register(
                        mv_name=mv_name,
                        schema=schema,
                        layer_id=layer.id(),
                        layer_name=layer.name(),
                        feature_count=feature_count
                    )
                    self.log_debug(f"📝 MV registered for cleanup: {mv_name}")
                except Exception as reg_error:
                    self.log_warning(f"Failed to register MV for cleanup: {reg_error}")
            
            cursor.close()
            conn.close()
            
            elapsed = time.time() - start_time
            
            if result:
                # Use cached feature_count to avoid expensive second COUNT(*)
                new_feature_count = layer.featureCount()  # Only if needed for exact count
                self.log_info(
                    f"✓ Materialized view created and filter applied in {elapsed:.2f}s. "
                    f"{new_feature_count} features match."
                )
                
                # Log performance breakdown for debugging
                if elapsed > 2.0:
                    breakdown = ", ".join([f"{name}: {t:.2f}s" for name, t in step_times])
                    self.log_debug(f"  Performance breakdown: {breakdown}")
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
            except (OSError, AttributeError, Exception) as cleanup_err:
                self.log_debug(f"Cleanup error (non-fatal): {cleanup_err}")
            
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

# -*- coding: utf-8 -*-
"""
PostgreSQL Expression Builder.

v4.1.0: Migrated from before_migration/modules/backends/postgresql_backend.py

This module contains the SQL expression building logic for PostGIS spatial filters.
It implements the GeometricFilterPort interface for PostgreSQL backends.

Architecture:
- PostgreSQLExpressionBuilder: Implements GeometricFilterPort for expression building
- PostgreSQLBackend: Uses the new BackendPort interface (execute())

The ExpressionBuilder is used by LegacyAdapter to maintain backward compatibility
with FilterEngineTask while the codebase transitions to the new architecture.

Author: FilterMate Team  
Date: January 2026
"""

import logging
import re
import time
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger('FilterMate.Backend.PostgreSQL.ExpressionBuilder')

# Import the port interface
try:
    from ....core.ports.geometric_filter_port import GeometricFilterPort
except ImportError:
    # Fallback for direct import
    from core.ports.geometric_filter_port import GeometricFilterPort

# Import safe_set_subset_string from infrastructure
try:
    from ....infrastructure.database.sql_utils import safe_set_subset_string
except ImportError:
    def safe_set_subset_string(layer, expression):
        """Fallback implementation."""
        if layer is None:
            return False
        try:
            return layer.setSubsetString(expression)
        except Exception:
            return False

# v4.2.10: Import filter chain optimizer for MV-based optimization
try:
    from .filter_chain_optimizer import (
        FilterChainOptimizer,
        FilterChainContext,
        OptimizationStrategy,
        OptimizedChain
    )
    CHAIN_OPTIMIZER_AVAILABLE = True
except ImportError:
    CHAIN_OPTIMIZER_AVAILABLE = False
    logger.debug("Filter chain optimizer not available")


class PostgreSQLExpressionBuilder(GeometricFilterPort):
    """
    PostgreSQL/PostGIS expression builder.
    
    Generates PostGIS SQL expressions for spatial filtering.
    Implements the legacy GeometricFilterPort interface for backward compatibility.
    
    Features:
    - Simple WKT mode for small datasets
    - EXISTS subquery mode for large datasets  
    - Buffer support with endcap styles
    - Centroid optimization for complex geometries
    - Geographic CRS handling (EPSG:4326 -> 3857 reprojection)
    - Column case normalization
    - Numeric type casting for varchar fields
    
    Example:
        builder = PostgreSQLExpressionBuilder(task_params)
        expr = builder.build_expression(
            layer_props={'layer_schema': 'public', 'layer_table_name': 'buildings'},
            predicates={'intersects': True},
            source_wkt='POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))',
            source_srid=4326,
            buffer_value=100
        )
    """
    
    # Strategy thresholds
    SIMPLE_WKT_THRESHOLD = 100  # Use simple WKT for <= 100 source features
    MAX_WKT_LENGTH = 100000     # Max WKT length before switching to EXISTS
    WKT_SIMPLIFY_THRESHOLD = 500000  # Warn about very large geometries
    
    # Predicate optimization order (most selective first)
    PREDICATE_ORDER = {
        'within': 1,       # Most selective - target fully inside source
        'contains': 2,     # Target fully contains source
        'disjoint': 3,     # Inverse of intersects
        'equals': 4,       # Exact match
        'touches': 5,      # Border contact only
        'crosses': 6,      # Lines crossing
        'overlaps': 7,     # Partial overlap
        'intersects': 8,   # Least selective - any overlap
    }
    
    # PostGIS predicate mapping
    PREDICATE_FUNCTIONS = {
        'intersects': 'ST_Intersects',
        'contains': 'ST_Contains',
        'within': 'ST_Within',
        'touches': 'ST_Touches',
        'overlaps': 'ST_Overlaps',
        'crosses': 'ST_Crosses',
        'disjoint': 'ST_Disjoint',
        'equals': 'ST_Equals',
        'covers': 'ST_Covers',
        'coveredby': 'ST_CoveredBy',
    }
    
    def __init__(self, task_params: Dict[str, Any]):
        """
        Initialize PostgreSQL expression builder.
        
        Args:
            task_params: Task configuration parameters
        """
        super().__init__(task_params)
        self._logger = logger
    
    def get_backend_name(self) -> str:
        """Get backend name."""
        return "PostgreSQL"
    
    def supports_layer(self, layer: 'QgsVectorLayer') -> bool:
        """
        Check if this backend supports the given layer.
        
        Args:
            layer: QGIS vector layer to check
            
        Returns:
            True if layer is PostgreSQL
        """
        if layer is None:
            return False
        return layer.providerType() == 'postgres'
    
    def build_expression(
        self,
        layer_props: Dict[str, Any],
        predicates: Dict[str, bool],
        source_geom: Optional[str] = None,
        buffer_value: Optional[float] = None,
        buffer_expression: Optional[str] = None,
        source_filter: Optional[str] = None,
        use_centroids: bool = False,
        **kwargs
    ) -> str:
        """
        Build PostGIS filter expression.
        
        Strategy based on source feature count:
        - Tiny (< SIMPLE_WKT_THRESHOLD): Use direct WKT geometry literal
        - Larger: Use EXISTS subquery with source filter
        
        FIX v4.2.12 (2026-01-21): Detects complex query scenarios (buffer expression + filter chaining)
        and warns user about potential performance impact. Sets 2-minute timeout for protection.
        
        Args:
            layer_props: Layer properties (schema, table, geometry field, etc.)
            predicates: Spatial predicates to apply (intersects, contains, etc.)
            source_geom: Source geometry expression
            buffer_value: Buffer distance in layer units
            buffer_expression: Dynamic buffer expression
            source_filter: Source layer filter (for EXISTS)
            use_centroids: Use centroid optimization
            **kwargs: source_wkt, source_srid, source_feature_count
            
        Returns:
            PostGIS SQL expression string
        """
        self.log_debug(f"Building PostgreSQL expression for {layer_props.get('layer_name', 'unknown')}")
        
        # FIX v4.2.12: Detect complex query scenarios EARLY
        self._detect_and_warn_complex_query(
            buffer_expression=buffer_expression,
            source_filter=source_filter,
            layer_name=layer_props.get('layer_name', 'unknown')
        )
        
        # Extract kwargs
        source_wkt = kwargs.get('source_wkt')
        source_srid = kwargs.get('source_srid')
        source_feature_count = kwargs.get('source_feature_count')
        
        # Extract layer properties
        layer = layer_props.get("layer")
        
        # FIX 2026-01-19: Extract schema/table/geom from layer's URI (most reliable source)
        schema = None
        table = None
        geom_field = None
        
        if layer:
            try:
                from qgis.core import QgsDataSourceUri
                uri = QgsDataSourceUri(layer.dataProvider().dataSourceUri())
                schema = uri.schema() or "public"
                table = uri.table()
                geom_field = uri.geometryColumn() or "geom"
                self.log_debug(f"Extracted from URI: schema={schema}, table={table}, geom={geom_field}")
            except Exception as e:
                self.log_warning(f"Failed to extract from URI: {e}")
        
        # Fallback to layer_props if URI extraction failed
        if not schema:
            schema = layer_props.get("layer_schema") or "public"
        if not table:
            table = layer_props.get("layer_table_name") or layer_props.get("layer_name")
        if not geom_field:
            geom_field = self._detect_geometry_column(layer_props)
        
        # DIAGNOSTIC: Print extracted values
        # print(f"📋 Layer props extraction:")  # DEBUG REMOVED
        # print(f"   schema: {schema}")  # DEBUG REMOVED
        # print(f"   table: {table}")  # DEBUG REMOVED
        # print(f"   geom_field: {geom_field}")  # DEBUG REMOVED
        
        # FIX 2026-01-19: Build geometry expression with TABLE.GEOM (not schema)
        # For PostgreSQL setSubsetString, the schema is implicit in the layer context
        # Format: "table"."geom" - NOT "schema"."table"."geom"
        geom_expr = f'"{table}"."{geom_field}"'
        
        # Apply centroid optimization if enabled
        if use_centroids:
            geom_expr = self._apply_centroid_transform(geom_expr, layer_props)
        
        # FIX v4.2.7: DO NOT apply buffer_expression to distant layer geometry!
        # The buffer_expression is for the SOURCE layer and is already applied in the MV.
        # When source_geom points to a buffer_expr MV (mv_xxx_buffer_expr_dump), the buffer
        # is already baked into that MV's geometries. Applying it again to the distant layer
        # would double-buffer and also fail because the CASE WHEN fields belong to the source.
        #
        # REMOVED: The buffer_expression should NOT be applied here for distant layers.
        # if buffer_expression:
        #     geom_expr = self._apply_dynamic_buffer(geom_expr, buffer_expression)
        
        # DIAGNOSTIC 2026-01-19: Log the fully qualified geom_expr
        # print(f"🎯 PostgreSQL geom_expr (fully qualified): {geom_expr}")  # DEBUG REMOVED
        
        # Determine strategy
        wkt_length = len(source_wkt) if source_wkt else 0
        use_simple_wkt = (
            source_wkt is not None and
            source_srid is not None and
            source_feature_count is not None and
            source_feature_count <= self.SIMPLE_WKT_THRESHOLD and
            wkt_length <= self.MAX_WKT_LENGTH
        )
        
        if use_simple_wkt:
            self.log_info(f"📝 Using SIMPLE WKT mode ({source_feature_count} features, {wkt_length} chars)")
        else:
            self.log_info(f"📝 Using EXISTS subquery mode")
        
        # FIX v4.2.7: Get original source table name for proper aliasing
        original_source_table = kwargs.get('source_table_name')
        
        # v4.2.10: Check for filter chain MV optimization
        filter_chain_mv_name = kwargs.get('filter_chain_mv_name')
        if filter_chain_mv_name:
            self.log_info(f"🚀 FILTER CHAIN MV OPTIMIZATION: Using {filter_chain_mv_name}")
            # The MV already contains pre-filtered source features satisfying all spatial constraints
            # Generate a simple EXISTS against the MV instead of multiple chained EXISTS
            return self._build_optimized_mv_expression(
                geom_expr=geom_expr,
                predicates=predicates,
                mv_name=filter_chain_mv_name,
                buffer_value=buffer_value
            )
        
        # Build predicate expressions
        predicate_expressions = []
        
        # Sort predicates for optimal performance
        sorted_predicates = self._sort_predicates(predicates)
        
        # FIX v4.2.9: Separate EXISTS clauses from simple filters
        # EXISTS clauses should be ANDed at the TOP LEVEL, not inside the new EXISTS
        exists_clauses_to_combine = []
        simple_source_filter = source_filter
        
        if source_filter and 'EXISTS' in source_filter.upper():
            # Extract EXISTS clauses to combine at the top level
            try:
                from ....core.filter.expression_combiner import extract_exists_clauses, adapt_exists_for_nested_context
            except ImportError:
                from core.filter.expression_combiner import extract_exists_clauses, adapt_exists_for_nested_context
            extracted = extract_exists_clauses(source_filter)
            if extracted:
                # FIX v4.2.12 (2026-01-21): Adapt EXISTS clauses for distant layer context
                # 
                # Problem: EXISTS clauses extracted from source layer (e.g., demand_points) contain
                # references to that source table (e.g., "demand_points"."geom"). When these
                # EXISTS are applied to a distant layer (e.g., ducts), the table reference is invalid
                # because "demand_points" is not in the FROM clause of the distant layer query.
                #
                # Solution: Replace source table references with the distant (target) table name.
                # Example: ST_PointOnSurface("demand_points"."geom") → ST_PointOnSurface("ducts"."geom")
                #
                # The `table` variable contains the distant layer's table name (e.g., "ducts")
                # The `original_source_table` contains the source layer's table name (e.g., "demand_points")
                
                adapted_exists = []
                for clause_info in extracted:
                    clause_sql = clause_info['sql']
                    
                    # Adapt the EXISTS clause for the distant layer context
                    if original_source_table and table:
                        adapted_sql = adapt_exists_for_nested_context(
                            exists_sql=clause_sql,
                            original_table=original_source_table,
                            new_alias=f'"{table}"',  # Replace with target table reference
                            original_schema=None  # Schema is handled by pattern matching
                        )
                        if adapted_sql != clause_sql:
                            self.log_info(f"🔄 Adapted EXISTS for distant layer: '{original_source_table}' → '{table}'")
                        adapted_exists.append(adapted_sql)
                    else:
                        # No adaptation needed or possible
                        adapted_exists.append(clause_sql)
                
                exists_clauses_to_combine = adapted_exists
                self.log_info(f"🔗 Filter chaining: Found {len(exists_clauses_to_combine)} EXISTS clause(s) to chain at top level")
                # Don't pass EXISTS to _build_exists_expression (they go at top level)
                simple_source_filter = None
        
        for predicate_name, predicate_func in sorted_predicates:
            if use_simple_wkt:
                expr = self._build_simple_wkt_expression(
                    geom_expr=geom_expr,
                    predicate_func=predicate_func,
                    source_wkt=source_wkt,
                    source_srid=source_srid,
                    buffer_value=buffer_value
                )
            else:
                # CRITICAL: Use unqualified geom_expr for EXISTS subquery
                # setSubsetString applies to the main table, so no table prefix needed
                # Format: EXISTS (SELECT 1 FROM source AS __source WHERE ST_Intersects("geom", __source."geom"))
                expr = self._build_exists_expression(
                    geom_expr=geom_expr,  # Unqualified - no table prefix!
                    predicate_func=predicate_func,
                    source_geom=source_geom,
                    source_filter=simple_source_filter,  # FIX: Only simple filters, not EXISTS
                    buffer_value=buffer_value,
                    layer_props=layer_props,
                    original_source_table=original_source_table,
                    buffer_expression=buffer_expression  # FIX v4.2.11: Pass dynamic buffer expression
                )
            
            if expr:
                predicate_expressions.append(expr)
        
        # Combine predicates with OR (any predicate match)
        if not predicate_expressions:
            self.log_warning("No predicate expressions generated")
            return "1 = 0"  # No results
        
        if len(predicate_expressions) == 1:
            final_expr = predicate_expressions[0]
        else:
            final_expr = f"({' OR '.join(predicate_expressions)})"
        
        # FIX v4.2.9: Combine extracted EXISTS clauses at top level
        # Result: EXISTS(new_source) AND EXISTS(zone_pop) AND EXISTS(other...)
        if exists_clauses_to_combine:
            all_exists = [final_expr] + exists_clauses_to_combine
            final_expr = ' AND '.join(all_exists)
            self.log_info(f"🔗 Filter chaining: Combined {len(all_exists)} EXISTS clauses at top level")
            self.log_debug(f"   Final chained expression preview: {final_expr[:300]}...")
        
        # DIAGNOSTIC: Log the final expression
        # print("=" * 80)  # DEBUG REMOVED
        # print(f"🔍 PostgreSQLExpressionBuilder.build_expression() RESULT:")  # DEBUG REMOVED
        # print(f"   Expression length: {len(final_expr)} chars")  # DEBUG REMOVED
        # print(f"   Expression preview: {final_expr[:300]}...")  # DEBUG REMOVED
        # print("=" * 80)  # DEBUG REMOVED
        self.log_info(f"✅ PostgreSQL expression built: {final_expr[:200]}...")
        
        # FIX v4.2.12: Set query timeout if complex query detected
        if hasattr(self, '_is_complex_query') and self._is_complex_query:
            self._set_query_timeout(layer_props.get('layer'))
        
        return final_expr
    
    def build_expression_optimized(
        self,
        layer_props: Dict[str, Any],
        predicates: Dict[str, bool],
        spatial_filters: List[Dict[str, Any]],
        source_geom: Optional[str] = None,
        buffer_value: Optional[float] = None,
        connection=None,
        session_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Build optimized expression using materialized views for filter chaining.
        
        v4.2.10: Uses MV-based optimization when multiple spatial filters are present.
        
        Instead of multiple EXISTS clauses:
            EXISTS (SELECT 1 FROM demand_points WHERE ST_Intersects(...))
            AND EXISTS (SELECT 1 FROM zone_pop WHERE ST_Intersects(...))
        
        Creates a single MV with pre-filtered source features and uses:
            EXISTS (SELECT 1 FROM filtermate_temp.fm_chain_xxx AS __source
                    WHERE ST_Intersects("distant"."geom", __source."geom"))
        
        Args:
            layer_props: Layer properties (schema, table, geometry field)
            predicates: Spatial predicates to apply
            spatial_filters: List of spatial filter definitions:
                [
                    {'table': 'zone_pop', 'schema': 'ref', 'predicate': 'ST_Intersects'},
                    {'table': 'demand_points', 'schema': 'ref', 'predicate': 'ST_Intersects', 'buffer': 5.0}
                ]
            source_geom: Source geometry expression
            buffer_value: Buffer distance for source
            connection: PostgreSQL connection (required for MV creation)
            session_id: Session ID for MV naming
            **kwargs: Additional parameters
            
        Returns:
            Optimized PostGIS SQL expression
        """
        if not CHAIN_OPTIMIZER_AVAILABLE:
            self.log_warning("Filter chain optimizer not available, using standard expression")
            return self.build_expression(
                layer_props=layer_props,
                predicates=predicates,
                source_geom=source_geom,
                buffer_value=buffer_value,
                **kwargs
            )
        
        if not connection:
            self.log_warning("No connection provided for MV optimization, using standard expression")
            return self.build_expression(
                layer_props=layer_props,
                predicates=predicates,
                source_geom=source_geom,
                buffer_value=buffer_value,
                **kwargs
            )
        
        if len(spatial_filters) < 2:
            self.log_debug("Less than 2 spatial filters, MV optimization not beneficial")
            return self.build_expression(
                layer_props=layer_props,
                predicates=predicates,
                source_geom=source_geom,
                buffer_value=buffer_value,
                **kwargs
            )
        
        # Extract distant layer info
        layer = layer_props.get("layer")
        distant_table = layer_props.get("layer_table_name") or layer_props.get("layer_name")
        distant_schema = layer_props.get("layer_schema") or "public"
        distant_geom = self._detect_geometry_column(layer_props)
        
        if layer:
            try:
                from qgis.core import QgsDataSourceUri
                uri = QgsDataSourceUri(layer.dataProvider().dataSourceUri())
                distant_schema = uri.schema() or distant_schema
                distant_table = uri.table() or distant_table
                distant_geom = uri.geometryColumn() or distant_geom
            except:
                pass
        
        # Extract source layer info from source_geom
        source_info = self._parse_source_table_reference(source_geom) if source_geom else {}
        source_schema = source_info.get('schema', 'public')
        source_table = source_info.get('table', '')
        source_geom_column = source_info.get('geom_field', 'geom')
        
        if not source_table:
            self.log_warning("Could not determine source table from source_geom, using standard expression")
            return self.build_expression(
                layer_props=layer_props,
                predicates=predicates,
                source_geom=source_geom,
                buffer_value=buffer_value,
                **kwargs
            )
        
        # Build filter chain context
        context = FilterChainContext(
            source_schema=source_schema,
            source_table=source_table,
            source_geom_column=source_geom_column,
            spatial_filters=spatial_filters,
            buffer_value=buffer_value,
            session_id=session_id
        )
        
        # Get predicate function
        predicate_func = "ST_Intersects"  # Default
        for pred_name, enabled in predicates.items():
            if enabled and pred_name in self.PREDICATE_FUNCTIONS:
                predicate_func = self.PREDICATE_FUNCTIONS[pred_name]
                break
        
        # Create optimizer and get optimized expression
        optimizer = FilterChainOptimizer(connection, session_id)
        
        try:
            result = optimizer.optimize_for_distant_layer(
                context=context,
                distant_table=distant_table,
                distant_schema=distant_schema,
                distant_geom_column=distant_geom,
                predicate=predicate_func
            )
            
            if result.strategy != OptimizationStrategy.NONE:
                self.log_info(f"🚀 MV optimization applied: {result.strategy.value}")
                self.log_info(f"   MV name: {result.mv_name}")
                self.log_info(f"   Estimated improvement: {result.estimated_improvement:.0%}")
                self.log_debug(f"   Expression: {result.expression[:200]}...")
                
                # Store cleanup SQL for later
                if hasattr(self, '_mv_cleanup_sql'):
                    self._mv_cleanup_sql.append(result.cleanup_sql)
                else:
                    self._mv_cleanup_sql = [result.cleanup_sql]
                
                return result.expression
            else:
                self.log_debug("MV optimization not applied, using standard expression")
                
        except Exception as e:
            self.log_error(f"MV optimization failed: {e}")
        
        # Fallback to standard expression
        return self.build_expression(
            layer_props=layer_props,
            predicates=predicates,
            source_geom=source_geom,
            buffer_value=buffer_value,
            **kwargs
        )
    
    def apply_filter(
        self,
        layer: 'QgsVectorLayer',
        expression: str,
        old_subset: Optional[str] = None,
        combine_operator: Optional[str] = None
    ) -> bool:
        """
        Apply filter to PostgreSQL layer.
        
        Args:
            layer: PostgreSQL layer to filter
            expression: PostGIS SQL expression
            old_subset: Existing subset string
            combine_operator: Operator to combine (AND/OR)
            
        Returns:
            True if filter applied successfully
        """
        # DIAGNOSTIC 2026-01-19: Trace apply_filter execution
        # print("=" * 80)  # DEBUG REMOVED
        # print(f"🎯 PostgreSQLExpressionBuilder.apply_filter() CALLED!")  # DEBUG REMOVED
        # print(f"   layer: {layer.name() if layer else 'None'}")  # DEBUG REMOVED
        # print(f"   expression length: {len(expression) if expression else 0}")  # DEBUG REMOVED
        # print(f"   expression preview: {expression[:150] if expression else 'None'}...")  # DEBUG REMOVED
        # print(f"   old_subset: {old_subset[:100] if old_subset else 'None'}...")  # DEBUG REMOVED
        # print(f"   combine_operator: {combine_operator}")  # DEBUG REMOVED
        # print("=" * 80)  # DEBUG REMOVED
        
        try:
            if not expression:
                self.log_warning("Empty expression, skipping filter")
                # print("⚠️ Empty expression - returning False")  # DEBUG REMOVED
                return False
            
            # Normalize column case and apply type casting
            expression = self._normalize_column_case(expression, layer)
            expression = self._apply_numeric_type_casting(expression, layer)
            
            if old_subset:
                old_subset = self._normalize_column_case(old_subset, layer)
                old_subset = self._apply_numeric_type_casting(old_subset, layer)
            
            # Handle existing subset
            if old_subset and combine_operator:
                # Check if old subset contains geometric filter (should be replaced)
                if self._is_geometric_filter(old_subset):
                    self.log_info("🔄 Replacing geometric filter in old_subset")
                    final_expression = expression
                else:
                    # Combine with attribute filter
                    final_expression = f"({old_subset}) {combine_operator} ({expression})"
                    self.log_info(f"✅ Combined with existing filter using {combine_operator}")
            else:
                final_expression = expression
            
            # DIAGNOSTIC: Print final expression before applying
            # print(f"📝 Final expression to apply: {final_expression[:200]}...")  # DEBUG REMOVED
            # print(f"   Calling safe_set_subset_string(layer={layer.name()}, expr_len={len(final_expression)})...")  # DEBUG REMOVED
            
            # Apply filter
            # FIX v4.2.13: Enhanced logging for debugging failures
            self.log_info(f"📝 Applying PostgreSQL filter to {layer.name()}:")
            self.log_info(f"   Expression length: {len(final_expression)} chars")
            self.log_debug(f"   Expression preview: {final_expression[:300]}...")
            
            success = safe_set_subset_string(layer, final_expression)
            
            if success:
                self.log_info(f"✓ Filter applied successfully to {layer.name()}")
                self.log_info(f"   → Feature count after filter: {layer.featureCount()}")
            else:
                self.log_error(f"✗ FAILED to apply filter to {layer.name()}!")
                self.log_error(f"   → This triggers OGR fallback")
                # Log the FULL expression for debugging (not truncated)
                self.log_error(f"   Expression that FAILED:\n{final_expression}")
            
            return success
            
        except Exception as e:
            self.log_error(f"Error applying filter: {e}")
            return False
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _detect_geometry_column(self, layer_props: Dict) -> str:
        """Detect geometry column from layer properties."""
        geom_field = layer_props.get("layer_geometry_field", "geom")
        layer = layer_props.get("layer")
        
        if layer:
            try:
                from qgis.core import QgsDataSourceUri
                provider = layer.dataProvider()
                uri_string = provider.dataSourceUri()
                uri_obj = QgsDataSourceUri(uri_string)
                geom_col = uri_obj.geometryColumn()
                if geom_col:
                    geom_field = geom_col
                    self.log_debug(f"Detected geometry column: '{geom_field}'")
            except Exception as e:
                self.log_warning(f"Error detecting geometry column: {e}")
        
        return geom_field
    
    def _apply_centroid_transform(self, geom_expr: str, layer_props: Dict) -> str:
        """Apply centroid transformation for performance."""
        centroid_mode = self.task_params.get('centroid_mode', 'point_on_surface')
        geometry_type = layer_props.get("layer_geometry_type")
        
        if centroid_mode == 'point_on_surface':
            self.log_info("✓ Using ST_PointOnSurface for centroid")
            return f"ST_PointOnSurface({geom_expr})"
        else:
            self.log_info("✓ Using ST_Centroid for centroid")
            return f"ST_Centroid({geom_expr})"
    
    def _apply_dynamic_buffer(self, geom_expr: str, buffer_expression: str) -> str:
        """Apply dynamic buffer expression."""
        endcap_style = self._get_buffer_endcap_style()
        if endcap_style == 'round':
            return f"ST_Buffer({geom_expr}, {buffer_expression})"
        else:
            return f"ST_Buffer({geom_expr}, {buffer_expression}, 'endcap={endcap_style}')"
    
    def _sort_predicates(self, predicates: Dict) -> List[Tuple[str, str]]:
        """Sort predicates by selectivity for optimal performance."""
        sorted_items = []
        
        for key, value in predicates.items():
            # Extract predicate name from value
            if isinstance(value, str):
                predicate_func = value
            else:
                predicate_func = self.PREDICATE_FUNCTIONS.get(key.lower(), 'ST_Intersects')
            
            predicate_lower = predicate_func.lower().replace('st_', '')
            order = self.PREDICATE_ORDER.get(predicate_lower, 99)
            sorted_items.append((key, predicate_func, order))
        
        sorted_items.sort(key=lambda x: x[2])
        return [(item[0], item[1]) for item in sorted_items]
    
    def _detect_and_warn_complex_query(
        self,
        buffer_expression: Optional[str],
        source_filter: Optional[str],
        layer_name: str
    ) -> None:
        """
        Detect complex query scenarios and warn user about performance impact.
        
        FIX v4.2.12 (2026-01-21): Prevents freeze by warning users when combining:
        - Dynamic buffer expressions (if("field" > X, Y, Z))
        - Filter chaining (multiple EXISTS subqueries)
        
        Complex queries can cause PostgreSQL to hang due to:
        - Per-feature buffer calculations (CASE WHEN evaluated for each feature)
        - Nested EXISTS subqueries (cartesian product)
        - Missing spatial indexes
        
        Sets self._is_complex_query flag for timeout enforcement.
        """
        self._is_complex_query = False
        
        # Check for complex scenario: buffer expression + filter chaining
        has_buffer_expr = buffer_expression is not None and buffer_expression.strip() != ''
        has_chained_filter = source_filter and 'EXISTS' in source_filter.upper()
        
        if has_buffer_expr and has_chained_filter:
            self._is_complex_query = True
            self.log_warning("🚨 COMPLEX QUERY DETECTED")
            self.log_warning(f"   Layer: {layer_name}")
            self.log_warning(f"   → Dynamic buffer expression: {buffer_expression[:50]}...")
            self.log_warning(f"   → Filter chaining (multiple EXISTS)")
            self.log_warning(f"   ⚠️  This may cause slow performance or timeout")
            
            # Warn user via QGIS message bar
            try:
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"⚠️ FilterMate: Complex query on '{layer_name}'\n"
                    f"Combining dynamic buffer ({buffer_expression[:30]}...) with filter chaining.\n"
                    f"Query may take 10-60 seconds. A 2-minute timeout is set for protection.\n"
                    f"Consider using static buffer values for better performance.",
                    "FilterMate",
                    Qgis.Warning
                )
            except Exception as e:
                self.log_debug(f"Could not display warning in QGIS UI: {e}")
    
    def _set_query_timeout(self, layer) -> None:
        """
        Set PostgreSQL statement timeout for complex queries.
        
        FIX v4.2.12 (2026-01-21): Protection against infinite queries.
        Sets timeout to 120 seconds (2 minutes) for complex buffer+chaining scenarios.
        
        Args:
            layer: QGIS layer with PostgreSQL provider
        """
        if not layer:
            return
        
        try:
            # Get PostgreSQL connection from layer
            from ....infrastructure.utils import get_datasource_connexion_from_layer
            connexion, _ = get_datasource_connexion_from_layer(layer)
            
            if not connexion:
                self.log_warning("No PostgreSQL connection available for timeout")
                return
            
            # Set statement timeout (120 seconds = 2 minutes)
            timeout_ms = 120000  # 120 seconds in milliseconds
            
            with connexion.cursor() as cursor:
                cursor.execute(f"SET statement_timeout = {timeout_ms}")
            
            self.log_info(f"✅ Query timeout set: {timeout_ms/1000:.0f} seconds")
            self.log_info("   → Protection against infinite queries enabled")
            
        except Exception as e:
            self.log_warning(f"Could not set query timeout: {e}")
            # Non-critical - continue anyway
    
    def _build_exists_with_buffer_table(
        self,
        geom_expr: str,
        predicate_func: str,
        source_schema: str,
        source_table: str,
        source_geom_field: str,
        buffer_expression: str,
        source_filter: Optional[str],
        layer_props: Dict
    ) -> str:
        """
        Build EXISTS expression using pre-calculated buffer temporary table.
        
        FIX v4.2.13 (2026-01-21): Performance optimization for complex queries.
        Instead of calculating ST_Buffer(CASE WHEN...) for EVERY feature in EVERY distant layer,
        we pre-calculate buffers ONCE and store in a temporary table with spatial index.
        
        Performance improvement:
        - Before: O(N×M) - N source features × M distant features × buffer calculation
        - After: O(N + M) - N buffer calculations + M indexed lookups
        
        Example: 1000 source × 50000 distant × 6 layers = 300M buffer calculations
                 vs 1000 calculations + 300k indexed lookups
        
        Args:
            geom_expr: Target geometry expression
            predicate_func: PostGIS predicate (ST_Intersects, etc.)
            source_schema: Source schema name
            source_table: Source table name
            source_geom_field: Source geometry field name
            buffer_expression: Dynamic buffer expression (QGIS syntax)
            source_filter: Source filter with EXISTS clauses
            layer_props: Layer properties for connection
            
        Returns:
            EXISTS expression using temp buffer table
        """
        import time
        from .filter_executor import qgis_expression_to_postgis
        from ....infrastructure.utils import get_datasource_connexion_from_layer
        
        start_time = time.time()
        
        layer = layer_props.get('layer')
        if not layer:
            self.log_warning("No layer available for buffer table creation")
            return None
        
        # Get PostgreSQL connection
        connexion, _ = get_datasource_connexion_from_layer(layer)
        if not connexion:
            self.log_warning("No PostgreSQL connection for buffer table")
            return None
        
        # Generate unique temp table name
        session_id = getattr(self, 'session_id', None) or self.task_params.get('task', {}).get('session_id', 'default')
        temp_table_name = f"temp_buffered_{source_table}_{session_id}"
        
        # FIX v4.2.16 (2026-01-21): Use filtermate_temp schema instead of pg_temp
        # Problem: pg_temp tables are session-local and not visible to QGIS's own PostgreSQL connection
        # QGIS uses a separate connection for setSubsetString(), which can't see pg_temp tables
        # Solution: Use persistent filtermate_temp schema (same as MVs) so QGIS can access the table
        temp_schema = "filtermate_temp"
        
        # Convert QGIS buffer expression to PostGIS SQL
        buffer_expr_sql = qgis_expression_to_postgis(buffer_expression)
        
        # FIX v4.2.15 (2026-01-21): Prefix field references with table name
        # The buffer expression contains field names like "homecount" that must be qualified
        # with the source table name in the CREATE TEMP TABLE context
        # Pattern: "field" -> "{source_table}"."field"
        buffer_expr_sql = re.sub(
            r'(?<![.\w])"([^"]+)"(?!\s*\.)',
            rf'"{source_table}"."\1"',
            buffer_expr_sql
        )
        
        # FIX v4.2.16: Create filtermate_temp schema if needed
        # This schema persists across sessions so QGIS can access the buffer table
        try:
            with connexion.cursor() as cursor:
                cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{temp_schema}"')
                connexion.commit()
                self.log_debug(f"Schema {temp_schema} ready")
        except Exception as schema_err:
            self.log_warning(f"Could not create schema {temp_schema}: {schema_err}")
            # Continue anyway - schema might already exist
        
        # Build CREATE TABLE statement (NOT TEMP - must be visible to QGIS connection)
        # Note: Table will be cleaned up by FilterMate's cleanup mechanism (same as MVs)
        sql_create = f"""
            CREATE TABLE IF NOT EXISTS "{temp_schema}"."{temp_table_name}" AS
            SELECT 
                "{source_table}"."id" as source_id,
                ST_Buffer(
                    "{source_table}"."{source_geom_field}",
                    {buffer_expr_sql},
                    'quad_segs=5'
                ) as buffered_geom
            FROM "{source_schema}"."{source_table}"
            {f"WHERE {source_filter}" if source_filter else ""}
        """
        
        # Create spatial index
        sql_index = f'CREATE INDEX IF NOT EXISTS "idx_{temp_table_name}_geom" ON "{temp_schema}"."{temp_table_name}" USING GIST (buffered_geom)'
        
        # Analyze for query planner
        sql_analyze = f'ANALYZE "{temp_schema}"."{temp_table_name}"'
        
        try:
            with connexion.cursor() as cursor:
                self.log_info(f"📦 Creating buffer table: {temp_schema}.{temp_table_name}")
                cursor.execute(sql_create)
                self.log_debug("✓ Buffer table created")
                
                cursor.execute(sql_index)
                self.log_debug("✓ Spatial index created")
                
                cursor.execute(sql_analyze)
                self.log_debug("✓ Statistics updated")
                
                # Get row count for logging
                cursor.execute(f'SELECT COUNT(*) FROM "{temp_schema}"."{temp_table_name}"')
                row_count = cursor.fetchone()[0]
                
            elapsed = time.time() - start_time
            self.log_info(f"✅ Buffer table created: {row_count} features in {elapsed:.2f}s")
            self.log_info(f"   → Buffers pre-calculated, will be reused across all distant layers")
            
            # Build EXISTS using buffer table (with schema prefix for QGIS visibility)
            exists_expr = f"""EXISTS (
                SELECT 1 
                FROM "{temp_schema}"."{temp_table_name}" AS __buffer
                WHERE {predicate_func}({geom_expr}, __buffer.buffered_geom)
            )"""
            
            return exists_expr
            
        except Exception as e:
            self.log_error(f"Failed to create buffer table: {e}")
            self.log_warning("Falling back to inline buffer expression")
            # Return None to trigger fallback in caller
            return None
    
    def _build_optimized_mv_expression(
        self,
        geom_expr: str,
        predicates: Dict,
        mv_name: str,
        buffer_value: Optional[float] = None
    ) -> str:
        """
        Build optimized expression using filter chain materialized view.
        
        v4.2.10: Instead of multiple chained EXISTS clauses like:
            EXISTS(source + zone_pop) AND EXISTS(source + demand_points)
            
        We generate a single EXISTS against the pre-computed MV:
            EXISTS (SELECT 1 FROM filtermate_temp.mv_chain_xxx AS __chain
                    WHERE ST_Intersects("distant"."geom", __chain."geom"))
        
        Performance: O(N×M) → O(1) EXISTS per distant layer
        
        Args:
            geom_expr: Target geometry expression (e.g., '"table"."geom"')
            predicates: Spatial predicates to apply (intersects, contains, etc.)
            mv_name: Fully qualified MV name (e.g., "filtermate_temp"."fm_chain_xxx")
            buffer_value: Optional buffer distance (already baked into MV typically)
            
        Returns:
            Optimized EXISTS expression against MV
        """
        self.log_info(f"🚀 Building OPTIMIZED MV expression")
        self.log_info(f"   MV: {mv_name}")
        self.log_info(f"   Target geom: {geom_expr}")
        
        # Get primary predicate (usually intersects)
        sorted_predicates = self._sort_predicates(predicates)
        if sorted_predicates:
            predicate_func = sorted_predicates[0][1]
        else:
            predicate_func = "ST_Intersects"
        
        # Build EXISTS against the MV
        # The MV contains pre-filtered source features that satisfy all spatial constraints
        # Each distant layer only needs ONE EXISTS query against this MV
        
        # Source geometry in MV (use standard geom column)
        source_geom_in_mv = '__chain."geom"'
        
        # Apply buffer if specified (though usually already baked into MV)
        if buffer_value is not None and buffer_value != 0:
            source_geom_in_mv = self._build_st_buffer_with_style(
                source_geom_in_mv, buffer_value
            )
        
        # Build the optimized EXISTS
        # Format: EXISTS (SELECT 1 FROM mv AS __chain WHERE ST_Intersects(target, __chain.geom))
        exists_expr = (
            f"EXISTS (SELECT 1 FROM {mv_name} AS __chain "
            f"WHERE {predicate_func}({geom_expr}, {source_geom_in_mv}))"
        )
        
        self.log_info(f"✅ Optimized MV expression: {exists_expr[:150]}...")
        return exists_expr
    
    def _build_simple_wkt_expression(
        self,
        geom_expr: str,
        predicate_func: str,
        source_wkt: str,
        source_srid: int,
        buffer_value: Optional[float] = None
    ) -> str:
        """
        Build simple PostGIS expression using direct WKT.
        
        Args:
            geom_expr: Target geometry expression
            predicate_func: PostGIS predicate (ST_Intersects, etc.)
            source_wkt: Source geometry WKT
            source_srid: Source SRID
            buffer_value: Optional buffer distance
            
        Returns:
            PostGIS SQL expression
        """
        # Build source geometry with ST_MakeValid
        source_geom_sql = f"ST_MakeValid(ST_GeomFromText('{source_wkt}', {source_srid}))"
        
        # Apply buffer if specified
        if buffer_value is not None and buffer_value != 0:
            is_geographic = source_srid == 4326
            
            if is_geographic:
                # Transform to EPSG:3857 for metric buffer
                source_geom_sql = self._build_geographic_buffer(
                    source_geom_sql, buffer_value, source_srid
                )
            else:
                # Direct buffer in native units
                source_geom_sql = self._build_st_buffer_with_style(
                    source_geom_sql, buffer_value
                )
        
        return f"{predicate_func}({geom_expr}, {source_geom_sql})"
    
    def _build_exists_expression(
        self,
        geom_expr: str,
        predicate_func: str,
        source_geom: str,
        source_filter: Optional[str],
        buffer_value: Optional[float],
        layer_props: Dict,
        original_source_table: Optional[str] = None,
        buffer_expression: Optional[str] = None
    ) -> str:
        """
        Build EXISTS subquery expression.
        
        Format: EXISTS (SELECT 1 FROM "schema"."source_table" AS __source 
                        WHERE ST_Predicate("target_geom", __source."source_geom"))
        
        Args:
            geom_expr: Target geometry expression (UNQUALIFIED - e.g., "geom")
            predicate_func: PostGIS predicate (ST_Intersects, etc.)
            source_geom: Source geometry reference ("schema"."table"."geom")
            source_filter: Optional source filter (e.g., id IN (...) or "field" = 'value')
            buffer_value: Optional buffer distance (static)
            layer_props: Layer properties
            original_source_table: Original source table name for aliasing (v4.2.7)
            buffer_expression: Optional dynamic buffer expression (QGIS syntax)
            
        Returns:
            EXISTS subquery expression
        """
        if not source_geom:
            self.log_warning("No source_geom for EXISTS expression")
            return None
        
        # Parse source table reference
        source_ref = self._parse_source_table_reference(source_geom)
        
        if not source_ref:
            self.log_warning("Could not parse source table reference")
            return None
        
        source_schema = source_ref.get('schema', 'public')
        source_table = source_ref['table']
        source_geom_field = source_ref['geom_field']
        
        # Build source geometry in subquery
        source_geom_in_subquery = f'__source."{source_geom_field}"'
        
        # FIX v4.2.17 (2026-01-21): Don't apply buffer_expression in filter chaining context
        # When source_filter contains EXISTS (filter chaining: zone_pop → demand_points → ducts → sheaths),
        # the buffer_expression references fields from the ORIGINAL source (demand_points.homecount)
        # but is being applied to INTERMEDIATE sources (ducts, sheaths) that don't have those fields!
        # 
        # Example error: "ducts → sheaths" tries to use CASE WHEN ducts.homecount > 100
        # but "homecount" only exists in demand_points, not ducts!
        #
        # Solution: In filter chaining, the buffer was ALREADY applied when creating the temp table
        # for the original source (demand_points). Intermediate layers should use plain geometry.
        is_filter_chaining = source_filter and 'EXISTS' in source_filter.upper()
        
        if is_filter_chaining and buffer_expression:
            self.log_info(f"⚙️  Filter chaining detected - ignoring buffer_expression for {source_table}")
            self.log_info(f"   → Buffer was already applied to original source layer")
            self.log_info(f"   → Using plain geometry from {source_table} (no additional buffer)")
            buffer_expression = None  # Clear it to avoid applying to wrong table
        
        # FIX v4.2.14 (2026-01-21): ALWAYS use temp table for dynamic buffer expressions
        # Dynamic buffers (CASE WHEN) recalculate for EVERY feature pair - causes freeze on mapCanvas.refresh()
        # Problem: With 7 distant layers × 974 source features × 50k distant features each = 340M calculations!
        # Solution: Pre-calculate buffers ONCE in temp table, reuse across all EXISTS queries
        # Priority: temp_table (ALWAYS for dynamic) > buffer_value (static)
        if buffer_expression and buffer_expression.strip():
            # CRITICAL: Use temp table for ALL dynamic buffer expressions
            # The freeze happens during mapCanvas.refresh() when QGIS renders all 7 layers simultaneously
            # Each layer's setSubsetString contains inline ST_Buffer(CASE WHEN...) that recalculates
            # for every feature during rendering - causes multi-minute freeze even with timeout protection
            self.log_info("🚀 Using pre-calculated buffer table (prevents freeze on canvas refresh)")
            temp_table_expr = self._build_exists_with_buffer_table(
                geom_expr=geom_expr,
                predicate_func=predicate_func,
                source_schema=source_schema,
                source_table=source_table,
                source_geom_field=source_geom_field,
                buffer_expression=buffer_expression,
                source_filter=source_filter,
                layer_props=layer_props
            )
            
            # If temp table creation succeeded, return it
            if temp_table_expr:
                return temp_table_expr
            
            # Fallback to inline if temp table failed (logged in _build_exists_with_buffer_table)
            self.log_warning("⚠️  Temp table creation failed - falling back to inline buffer (may cause freeze)")
            
            # Non-complex: Use inline buffer (existing code)
            from .filter_executor import qgis_expression_to_postgis
            buffer_expr_sql = qgis_expression_to_postgis(buffer_expression)
            
            # Prefix field references with __source. for subquery context
            # Pattern: "field" -> __source."field"
            # Note: 're' module is already imported at module level (line 22)
            # Only prefix unqualified field references (not already prefixed with table/alias)
            buffer_expr_sql = re.sub(
                r'(?<![.\w])"([^"]+)"(?!\s*\.)',
                r'__source."\1"',
                buffer_expr_sql
            )
            
            self.log_info(f"🔧 Using dynamic buffer expression: {buffer_expr_sql[:100]}...")
            source_geom_in_subquery = self._build_st_buffer_with_dynamic_expr(
                source_geom_in_subquery, buffer_expr_sql
            )
        # Apply static buffer
        elif buffer_value is not None and buffer_value != 0:
            source_geom_in_subquery = self._build_st_buffer_with_style(
                source_geom_in_subquery, buffer_value
            )
        
        # Build WHERE clause
        # CRITICAL: The spatial predicate checks intersection between target and source
        where_clauses = [f"{predicate_func}({geom_expr}, {source_geom_in_subquery})"]
        
        if source_filter:
            # CRITICAL FIX v4.2.8 (2026-01-21): Handle combined EXISTS filters properly
            # 
            # Problem: When source_filter contains combined EXISTS subqueries (zone_pop + buffer),
            # we need to apply BOTH the spatial intersection AND the source filters.
            #
            # Before: Only added source_filter with aliasing (wrong for EXISTS patterns)
            # After: Detect if source_filter contains EXISTS - if yes, apply AS-IS (no aliasing needed)
            #        because EXISTS subqueries are ALREADY self-contained with their own aliases.
            #
            # Example source_filter from zone_pop + buffer optimization:
            #   (EXISTS (SELECT 1 FROM zone_pop AS __source WHERE ...)) AND
            #   (EXISTS (SELECT 1 FROM buffer AS __source WHERE ...))
            #
            # This filter should be applied DIRECTLY to verify the source geometry satisfies both constraints!
            
            # Check if source_filter contains EXISTS subqueries (combined filters from optimization)
            contains_exists = 'EXISTS' in source_filter.upper()
            
            if contains_exists:
                # FIX v4.2.8: EXISTS subqueries are self-contained - apply as-is
                # These are the combined zone_pop + buffer filters from Path 3A optimization
                # They MUST be applied to ensure source geometry passes all filter constraints
                self.log_info(f"🎯 source_filter contains EXISTS subqueries (combined filters)")
                self.log_info(f"   → Applying combined filter directly (no aliasing needed)")
                self.log_debug(f"   Combined filter preview: {source_filter[:200]}...")
                
                # CRITICAL: Add the combined EXISTS filters to WHERE clause
                # This ensures the source geometry satisfies zone_pop AND buffer constraints
                where_clauses.append(f"({source_filter})")
                
            else:
                # Original aliasing logic for simple filters (FID IN, field = value, etc.)
                # CRITICAL FIX v4.2.7 (2026-01-22): Proper aliasing of source_filter
                # 
                # Problem: When using buffer_expression (MV), source_table is the MV name
                # (mv_xxx_table_buffer_expr_dump) but source_filter contains the ORIGINAL 
                # table name ("ducts"."id" IN ...) or a simple filter ("nom" = 'value').
                #
                # Solution: Use original_source_table (passed from task_parameters) for aliasing.
                # This ensures we replace the correct table name with __source.
                #
                # Patterns handled:
                # 1. "table"."pk" IN (...) → __source."pk" IN (...)
                # 2. "field" = 'value' → __source."field" = 'value' (when table name known)
                
                aliased_source_filter = source_filter
                
                # Priority 1: Use original_source_table if provided
                if original_source_table:
                    self.log_debug(f"Using original_source_table for aliasing: {original_source_table}")
                    aliased_source_filter = source_filter.replace(
                        f'"{original_source_table}".',
                        '__source.'
                    )
                else:
                    # Priority 2: Extract table name from source_filter pattern: "table"."column" IN (...)
                    filter_table_match = re.search(r'^"([^"]+)"\."([^"]+)"\s*IN', source_filter)
                    if filter_table_match:
                        filter_table_name = filter_table_match.group(1)
                        self.log_debug(f"Extracted table name from source_filter: {filter_table_name}")
                        aliased_source_filter = source_filter.replace(
                            f'"{filter_table_name}".',
                            '__source.'
                        )
                    else:
                        # Priority 3: Fallback to source_table from parsed source_geom
                        # This works when source_geom points to original table (no MV)
                        self.log_debug(f"Fallback: using source_table from source_geom: {source_table}")
                        aliased_source_filter = source_filter.replace(
                            f'"{source_table}".',
                            '__source.'
                        )
                
                self.log_debug(f"Aliased source_filter: {aliased_source_filter[:100]}...")
                where_clauses.append(f"({aliased_source_filter})")
        
        where_clause = " AND ".join(where_clauses)
        
        # Build EXISTS subquery
        exists_expr = (
            f'EXISTS ('
            f'SELECT 1 FROM "{source_schema}"."{source_table}" AS __source '
            f'WHERE {where_clause}'
            f')'
        )
        
        # FIX v4.2.13: Enhanced diagnostics for EXISTS expression
        self.log_info(f"📝 EXISTS expression built:")
        self.log_info(f"   Source: \"{source_schema}\".\"{source_table}\"")
        self.log_info(f"   Predicate: {predicate_func}")
        self.log_info(f"   Has buffer: {bool(buffer_expression or buffer_value)}")
        if buffer_expression:
            self.log_info(f"   Buffer expression: {buffer_expression[:80]}...")
        elif buffer_value:
            self.log_info(f"   Buffer value: {buffer_value}m")
        self.log_debug(f"   Full EXISTS: {exists_expr[:500]}...")
        
        return exists_expr
    
    def _parse_source_table_reference(self, source_geom: str) -> Optional[Dict]:
        """Parse source table reference from geometry expression.
        
        Handles formats:
        - "schema"."table"."column"
        - ST_Buffer("schema"."table"."column", value)
        - ST_Centroid("schema"."table"."column")
        - CASE WHEN ... "schema"."table"."column" ...
        """
        self.log_debug(f"Parsing source_geom: '{source_geom[:100]}...' " if len(source_geom) > 100 else f"Parsing source_geom: '{source_geom}'")
        
        # Pattern 1: "schema"."table"."column" (3 parts with dots)
        pattern = r'"([^"]+)"\."([^"]+)"\."([^"]+)"'
        match = re.search(pattern, source_geom)
        
        if match:
            result = {
                'schema': match.group(1),
                'table': match.group(2),
                'geom_field': match.group(3)
            }
            self.log_debug(f"Matched 3-part pattern: {result}")
            return result
        
        # Pattern 2: "table"."column" (2 parts, assume public schema)
        pattern2 = r'"([^"]+)"\."([^"]+)"'
        match2 = re.search(pattern2, source_geom)
        
        if match2:
            result = {
                'schema': 'public',
                'table': match2.group(1),
                'geom_field': match2.group(2)
            }
            self.log_debug(f"Matched 2-part pattern: {result}")
            return result
        
        self.log_warning(f"Could not parse source_geom: {source_geom[:200]}")
        return None
    
    def _build_st_buffer_with_style(self, geom_expr: str, buffer_value: float) -> str:
        """Build ST_Buffer expression with endcap style."""
        endcap_style = self._get_buffer_endcap_style()
        quad_segs = self.task_params.get('buffer_segments', 5)
        
        style_params = f"quad_segs={quad_segs}"
        if endcap_style != 'round':
            style_params += f" endcap={endcap_style}"
        
        buffer_expr = f"ST_Buffer({geom_expr}, {buffer_value}, '{style_params}')"
        
        # Wrap negative buffers in ST_MakeValid with empty check
        if buffer_value < 0:
            validated = f"ST_MakeValid({buffer_expr})"
            return f"CASE WHEN ST_IsEmpty({validated}) THEN NULL ELSE {validated} END"
        
        return buffer_expr
    
    def _build_st_buffer_with_dynamic_expr(self, geom_expr: str, buffer_expr_sql: str) -> str:
        """
        Build ST_Buffer expression with dynamic buffer expression (SQL).
        
        FIX v4.2.11 (2026-01-21): Support QGIS expressions converted to SQL.
        Example: if("homecount" > 100, 50, 1) -> CASE WHEN "homecount" > 100 THEN 50 ELSE 1 END
        
        Args:
            geom_expr: Geometry expression (e.g., __source."geom")
            buffer_expr_sql: SQL expression for buffer distance (already converted from QGIS)
            
        Returns:
            ST_Buffer expression with dynamic buffer
        """
        endcap_style = self._get_buffer_endcap_style()
        quad_segs = self.task_params.get('buffer_segments', 5)
        
        style_params = f"quad_segs={quad_segs}"
        if endcap_style != 'round':
            style_params += f" endcap={endcap_style}"
        
        # For dynamic expressions, we can't know if it's negative at build time
        # PostgreSQL will handle empty geometries gracefully with ST_IsEmpty check
        return f"ST_Buffer({geom_expr}, {buffer_expr_sql}, '{style_params}')"
    
    def _build_geographic_buffer(
        self,
        geom_expr: str,
        buffer_value: float,
        source_srid: int
    ) -> str:
        """Build buffer for geographic CRS via EPSG:3857."""
        endcap_style = self._get_buffer_endcap_style()
        style_param = "" if endcap_style == 'round' else f", 'endcap={endcap_style}'"
        
        buffer_expr = (
            f"ST_Transform("
            f"ST_Buffer("
            f"ST_Transform({geom_expr}, 3857), "
            f"{buffer_value}{style_param}), "
            f"{source_srid})"
        )
        
        if buffer_value < 0:
            validated = f"ST_MakeValid({buffer_expr})"
            return f"CASE WHEN ST_IsEmpty({validated}) THEN NULL ELSE {validated} END"
        
        return buffer_expr
    
    def _normalize_column_case(self, expression: str, layer) -> str:
        """Normalize column names to match actual database case."""
        if not expression or not layer:
            return expression
        
        # Get actual column names from layer
        actual_columns = {}
        for field in layer.fields():
            actual_columns[field.name().lower()] = field.name()
        
        result = expression
        
        # Find quoted identifiers
        quoted_pattern = re.compile(r'"([^"]+)"')
        
        def normalize_match(match):
            col_name = match.group(1)
            col_lower = col_name.lower()
            if col_lower in actual_columns:
                return f'"{actual_columns[col_lower]}"'
            return match.group(0)
        
        result = quoted_pattern.sub(normalize_match, result)
        
        return result
    
    def _apply_numeric_type_casting(self, expression: str, layer) -> str:
        """Apply ::numeric casting for varchar field comparisons."""
        if not expression or not layer:
            return expression
        
        # Get varchar fields
        varchar_fields = set()
        for field in layer.fields():
            type_name = field.typeName().lower()
            if type_name in ('varchar', 'text', 'character varying', 'char'):
                varchar_fields.add(field.name().lower())
        
        if not varchar_fields:
            return expression
        
        # Pattern: "field" operator number
        pattern = re.compile(
            r'"([^"]+)"(\s*)(<|>|<=|>=)(\s*)(\d+(?:\.\d+)?)',
            re.IGNORECASE
        )
        
        def add_cast(match):
            field = match.group(1)
            if field.lower() in varchar_fields:
                return f'"{field}"::numeric{match.group(2)}{match.group(3)}{match.group(4)}{match.group(5)}'
            return match.group(0)
        
        if '::numeric' not in expression:
            expression = pattern.sub(add_cast, expression)
        
        return expression
    
    def _is_geometric_filter(self, subset: str) -> bool:
        """Check if subset contains geometric filter patterns."""
        subset_upper = subset.upper()
        
        geometric_patterns = [
            '__source',
            'EXISTS (',
            'EXISTS(',
            'ST_INTERSECTS',
            'ST_CONTAINS',
            'ST_WITHIN',
            'ST_TOUCHES',
            'ST_OVERLAPS',
            'ST_CROSSES',
            'ST_DISJOINT',
            'ST_BUFFER'
        ]
        
        return any(p in subset_upper or p.lower() in subset.lower() for p in geometric_patterns)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'PostgreSQLExpressionBuilder',
]

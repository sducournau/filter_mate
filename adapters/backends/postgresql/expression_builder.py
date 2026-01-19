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
        
        # Extract kwargs
        source_wkt = kwargs.get('source_wkt')
        source_srid = kwargs.get('source_srid')
        source_feature_count = kwargs.get('source_feature_count')
        
        # Extract layer properties
        schema = layer_props.get("layer_schema", "public")
        table = layer_props.get("layer_table_name") or layer_props.get("layer_name")
        geom_field = self._detect_geometry_column(layer_props)
        layer = layer_props.get("layer")
        
        # Build geometry expression for target layer (unqualified for setSubsetString)
        geom_expr = f'"{geom_field}"'
        
        # Apply centroid optimization if enabled
        if use_centroids:
            geom_expr = self._apply_centroid_transform(geom_expr, layer_props)
        
        # Apply dynamic buffer expression if specified
        if buffer_expression:
            geom_expr = self._apply_dynamic_buffer(geom_expr, buffer_expression)
        
        # NOTE: geom_expr stays UNQUALIFIED (e.g., "geom" not "table"."geom")
        # because setSubsetString is applied to a single table context
        # EXISTS subqueries reference the main table implicitly
        
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
        
        # Build predicate expressions
        predicate_expressions = []
        
        # Sort predicates for optimal performance
        sorted_predicates = self._sort_predicates(predicates)
        
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
                    source_filter=source_filter,
                    buffer_value=buffer_value,
                    layer_props=layer_props
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
        
        # DIAGNOSTIC: Log the final expression
        print("=" * 80)
        print(f"🔍 PostgreSQLExpressionBuilder.build_expression() RESULT:")
        print(f"   Expression length: {len(final_expr)} chars")
        print(f"   Expression preview: {final_expr[:300]}...")
        print("=" * 80)
        self.log_info(f"✅ PostgreSQL expression built: {final_expr[:200]}...")
        
        return final_expr
    
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
        try:
            if not expression:
                self.log_warning("Empty expression, skipping filter")
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
            
            # Apply filter
            success = safe_set_subset_string(layer, final_expression)
            
            if success:
                self.log_info(f"✓ Filter applied successfully")
            else:
                self.log_error(f"✗ Failed to apply filter")
            
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
        layer_props: Dict
    ) -> str:
        """
        Build EXISTS subquery expression.
        
        Format: EXISTS (SELECT 1 FROM "schema"."source_table" AS __source 
                        WHERE ST_Predicate("target_geom", __source."source_geom"))
        
        Args:
            geom_expr: Target geometry expression (UNQUALIFIED - e.g., "geom")
            predicate_func: PostGIS predicate (ST_Intersects, etc.)
            source_geom: Source geometry reference ("schema"."table"."geom")
            source_filter: Optional source filter (e.g., id IN (...))
            buffer_value: Optional buffer distance
            layer_props: Layer properties
            
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
        
        # Apply buffer
        if buffer_value is not None and buffer_value != 0:
            source_geom_in_subquery = self._build_st_buffer_with_style(
                source_geom_in_subquery, buffer_value
            )
        
        # Build WHERE clause
        where_clauses = [f"{predicate_func}({geom_expr}, {source_geom_in_subquery})"]
        
        if source_filter:
            where_clauses.append(f"({source_filter})")
        
        where_clause = " AND ".join(where_clauses)
        
        # Build EXISTS subquery
        exists_expr = (
            f'EXISTS ('
            f'SELECT 1 FROM "{source_schema}"."{source_table}" AS __source '
            f'WHERE {where_clause}'
            f')'
        )
        
        # DIAGNOSTIC: Log EXISTS expression details
        print(f"🔍 _build_exists_expression() GENERATED:")
        print(f"   source_schema: {source_schema}")
        print(f"   source_table: {source_table}")
        print(f"   source_geom_field: {source_geom_field}")
        print(f"   predicate_func: {predicate_func}")
        print(f"   geom_expr: {geom_expr}")
        print(f"   source_filter: {source_filter[:100] if source_filter else 'None'}...")
        print(f"   EXISTS expression: {exists_expr[:300]}...")
        
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
        quad_segs = self.task_params.get('buffer_segments', 8)
        
        style_params = f"quad_segs={quad_segs}"
        if endcap_style != 'round':
            style_params += f" endcap={endcap_style}"
        
        buffer_expr = f"ST_Buffer({geom_expr}, {buffer_value}, '{style_params}')"
        
        # Wrap negative buffers in ST_MakeValid with empty check
        if buffer_value < 0:
            validated = f"ST_MakeValid({buffer_expr})"
            return f"CASE WHEN ST_IsEmpty({validated}) THEN NULL ELSE {validated} END"
        
        return buffer_expr
    
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

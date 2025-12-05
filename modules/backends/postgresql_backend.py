# -*- coding: utf-8 -*-
"""
PostgreSQL Backend for FilterMate

Optimized backend for PostgreSQL/PostGIS databases.
Uses native PostGIS spatial functions and SQL queries for maximum performance.
"""

from typing import Dict, Optional
from qgis.core import QgsVectorLayer
from .base_backend import GeometricFilterBackend
from ..logging_config import get_tasks_logger
from ..appUtils import safe_set_subset_string

try:
    import psycopg2
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False

logger = get_tasks_logger()


class PostgreSQLGeometricFilter(GeometricFilterBackend):
    """
    PostgreSQL/PostGIS backend for geometric filtering.
    
    This backend provides optimized filtering for PostgreSQL layers using:
    - Native PostGIS spatial functions (ST_Intersects, ST_Contains, etc.)
    - Efficient spatial indexes
    - SQL-based filtering for maximum performance
    """
    
    def __init__(self, task_params: Dict):
        """
        Initialize PostgreSQL backend.
        
        Args:
            task_params: Task parameters dictionary
        """
        super().__init__(task_params)
        self.logger = logger
    
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
        table = layer_props.get("layer_name")
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
        Apply filter to PostgreSQL layer using setSubsetString.
        
        Args:
            layer: PostgreSQL layer to filter
            expression: PostGIS SQL expression
            old_subset: Existing subset string
            combine_operator: Operator to combine filters (AND/OR)
        
        Returns:
            True if filter applied successfully
        """
        import time
        start_time = time.time()
        
        try:
            if not expression:
                self.log_warning("Empty expression, skipping filter")
                return False
            
            # Combine with existing filter if specified
            if old_subset and combine_operator:
                final_expression = f"({old_subset}) {combine_operator} ({expression})"
            else:
                final_expression = expression
            
            self.log_info(f"Applying filter to {layer.name()}")
            self.log_debug(f"Expression: {final_expression[:200]}...")
            
            # Apply the filter (thread-safe)
            result = safe_set_subset_string(layer, final_expression)
            
            elapsed = time.time() - start_time
            
            if result:
                feature_count = layer.featureCount()
                self.log_info(f"Filter applied successfully in {elapsed:.2f}s. {feature_count} features match.")
                
                if elapsed > 5.0:
                    self.log_warning(f"Slow filter operation ({elapsed:.2f}s) - consider optimizing query or adding spatial indexes")
            else:
                self.log_error(f"Failed to apply filter to {layer.name()}")
            
            return result
            
        except Exception as e:
            self.log_error(f"Error applying filter: {str(e)}")
            return False
    
    def get_backend_name(self) -> str:
        """Get backend name"""
        return "PostgreSQL"

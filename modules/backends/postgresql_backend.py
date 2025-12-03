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
        geom_field = layer_props.get("geometry_field", "geometry")
        
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
            
            # Apply the filter
            result = layer.setSubsetString(final_expression)
            
            if result:
                feature_count = layer.featureCount()
                self.log_info(f"Filter applied successfully. {feature_count} features match.")
            else:
                self.log_error(f"Failed to apply filter to {layer.name()}")
            
            return result
            
        except Exception as e:
            self.log_error(f"Error applying filter: {str(e)}")
            return False
    
    def get_backend_name(self) -> str:
        """Get backend name"""
        return "PostgreSQL"

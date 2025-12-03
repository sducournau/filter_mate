# -*- coding: utf-8 -*-
"""
Spatialite Backend for FilterMate

Backend for Spatialite databases.
Uses Spatialite spatial functions which are largely compatible with PostGIS.
"""

from typing import Dict, Optional
import sqlite3
from qgis.core import QgsVectorLayer
from .base_backend import GeometricFilterBackend
from ..logging_config import get_tasks_logger

logger = get_tasks_logger()


class SpatialiteGeometricFilter(GeometricFilterBackend):
    """
    Spatialite backend for geometric filtering.
    
    This backend provides filtering for Spatialite layers using:
    - Spatialite spatial functions (similar to PostGIS)
    - SQL-based filtering
    - Good performance for small to medium datasets
    """
    
    def __init__(self, task_params: Dict):
        """
        Initialize Spatialite backend.
        
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
            True if layer is from Spatialite provider
        """
        return layer.providerType() == 'spatialite'
    
    def build_expression(
        self,
        layer_props: Dict,
        predicates: Dict,
        source_geom: Optional[str] = None,
        buffer_value: Optional[float] = None,
        buffer_expression: Optional[str] = None
    ) -> str:
        """
        Build Spatialite filter expression.
        
        Spatialite uses ~90% compatible syntax with PostGIS, so we can reuse
        most of the PostGIS logic.
        
        Args:
            layer_props: Layer properties
            predicates: Spatial predicates to apply
            source_geom: Source geometry (WKT string)
            buffer_value: Buffer distance
            buffer_expression: Expression for dynamic buffer
        
        Returns:
            Spatialite SQL expression string
        """
        self.log_debug(f"Building Spatialite expression for {layer_props.get('layer_name', 'unknown')}")
        
        # Extract layer properties
        table = layer_props.get("layer_name")
        geom_field = layer_props.get("geometry_field", "geometry")
        primary_key = layer_props.get("primary_key_name")
        
        # Source geometry should be WKT string from prepare_spatialite_source_geom
        if not source_geom:
            self.log_error("No source geometry provided for Spatialite filter")
            return ""
        
        if not isinstance(source_geom, str):
            self.log_error(f"Invalid source geometry type for Spatialite: {type(source_geom)}")
            return ""
        
        self.log_debug(f"Source WKT length: {len(source_geom)} chars")
        
        # Build geometry expression for target layer
        # For Spatialite subset strings, we typically don't need table prefix
        # Just the field name in quotes
        geom_expr = f'"{geom_field}"'
        
        # However, if there's a schema or the expression is complex, we might need it
        # Check if we need table prefix (usually not needed for simple subset strings)
        if table and '.' in str(table):
            # Has schema prefix, keep it
            geom_expr = f'"{table}"."{geom_field}"'
        
        self.log_debug(f"Geometry expression: {geom_expr}")
        
        # Convert WKT to Spatialite geometry using GeomFromText
        # Note: For better compatibility, try to get SRID from layer_props
        # Spatialite uses SRID in GeomFromText(wkt, srid)
        source_geom_expr = f"GeomFromText('{source_geom}')"
        
        # If we have CRS info, add SRID (not always needed but more robust)
        # Uncomment if SRID issues occur:
        # if 'layer_crs' in layer_props:
        #     srid = layer_props['layer_crs'].split(':')[-1] if ':' in layer_props.get('layer_crs', '') else None
        #     if srid:
        #         source_geom_expr = f"GeomFromText('{source_geom}', {srid})"
        
        # NOTE: Buffer is already applied in prepare_spatialite_source_geom()
        # Do NOT apply it again here to avoid double-buffering
        # The WKT already contains the buffered geometry
        
        if buffer_expression:
            self.log_warning("Dynamic buffer expressions not yet fully supported for Spatialite")
            self.log_info("Note: Static buffer values are already applied in geometry preparation")
        
        # Build predicate expressions  
        predicate_expressions = []
        for predicate_name, predicate_func in predicates.items():
            # Apply spatial predicate
            # Format: ST_Intersects("geometry", GeomFromText('...'))
            expr = f"{predicate_func}({geom_expr}, {source_geom_expr})"
            predicate_expressions.append(expr)
            self.log_debug(f"Added predicate: {predicate_func}")
        
        # Combine predicates with OR
        if predicate_expressions:
            combined = " OR ".join(predicate_expressions)
            self.log_info(f"Built Spatialite expression with {len(predicate_expressions)} predicate(s)")
            self.log_debug(f"Expression preview: {combined[:150]}...")
            return combined
        
        self.log_warning("No predicates to apply")
        return ""
    
    def apply_filter(
        self,
        layer: QgsVectorLayer,
        expression: str,
        old_subset: Optional[str] = None,
        combine_operator: Optional[str] = None
    ) -> bool:
        """
        Apply filter to Spatialite layer using setSubsetString.
        
        Args:
            layer: Spatialite layer to filter
            expression: Spatialite SQL expression
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
            
            # Log layer information
            self.log_debug(f"Layer provider: {layer.providerType()}")
            self.log_debug(f"Layer source: {layer.source()[:100]}...")
            self.log_debug(f"Current feature count: {layer.featureCount()}")
            
            # Combine with existing filter if specified
            if old_subset and combine_operator:
                final_expression = f"({old_subset}) {combine_operator} ({expression})"
                self.log_debug(f"Combining with existing subset using {combine_operator}")
            else:
                final_expression = expression
            
            self.log_info(f"Applying Spatialite filter to {layer.name()}")
            self.log_info(f"Expression length: {len(final_expression)} chars")
            
            # Log full expression for debugging (first 500 chars)
            if len(final_expression) <= 500:
                self.log_debug(f"Full expression: {final_expression}")
            else:
                self.log_debug(f"Expression start: {final_expression[:250]}...")
                self.log_debug(f"Expression end: ...{final_expression[-250:]}")
            
            # Apply the filter
            self.log_debug("Calling layer.setSubsetString()...")
            result = layer.setSubsetString(final_expression)
            
            elapsed = time.time() - start_time
            
            if result:
                feature_count = layer.featureCount()
                self.log_info(f"✓ Filter applied successfully in {elapsed:.2f}s. {feature_count} features match.")
                
                if feature_count == 0:
                    self.log_warning("Filter resulted in 0 features - check if expression is correct")
                
                if elapsed > 5.0:
                    self.log_warning(f"Slow filter operation ({elapsed:.2f}s) - consider using PostgreSQL for better performance")
                
                # Warn if dataset is large
                if feature_count > 50000:
                    self.log_warning(
                        f"Large dataset ({feature_count} features) with Spatialite. "
                        "Consider using PostgreSQL for better performance."
                    )
            else:
                self.log_error(f"✗ setSubsetString() returned False - filter expression may be invalid")
                self.log_error("Common issues:")
                self.log_error("  1. Spatial functions not available (mod_spatialite not loaded)")
                self.log_error("  2. Invalid WKT geometry")
                self.log_error("  3. Wrong geometry column name")
                self.log_error("  4. Syntax error in SQL expression")
                
                # Try a simple test to see if spatial functions work
                try:
                    test_expr = f'"{layer.geometryColumn()}" IS NOT NULL'
                    self.log_debug(f"Testing simple expression: {test_expr}")
                    test_result = layer.setSubsetString(test_expr)
                    if test_result:
                        self.log_info("Simple geometry test passed - issue is with spatial expression")
                        # Restore no filter
                        layer.setSubsetString("")
                    else:
                        self.log_error("Even simple geometry expression failed")
                except Exception as test_error:
                    self.log_debug(f"Test expression error: {test_error}")
            
            return result
            
        except Exception as e:
            self.log_error(f"Exception while applying filter: {str(e)}")
            import traceback
            self.log_debug(f"Traceback: {traceback.format_exc()}")
            return False
    
    def get_backend_name(self) -> str:
        """Get backend name"""
        return "Spatialite"

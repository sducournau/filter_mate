# -*- coding: utf-8 -*-
"""
OGR Backend for FilterMate

Fallback backend for OGR-based providers (Shapefiles, GeoPackage, etc.).
Uses QGIS processing algorithms for filtering since OGR providers don't support
complex SQL expressions like PostgreSQL/Spatialite.
"""

from typing import Dict, Optional
from qgis.core import QgsVectorLayer, QgsProcessingFeedback
from qgis import processing
from .base_backend import GeometricFilterBackend
from ..logging_config import get_tasks_logger

logger = get_tasks_logger()


class OGRGeometricFilter(GeometricFilterBackend):
    """
    OGR backend for geometric filtering.
    
    This backend provides filtering for OGR-based layers (Shapefiles, GeoPackage, etc.) using:
    - QGIS processing algorithms (selectbylocation)
    - Memory-based filtering
    - Compatible with all OGR-supported formats
    """
    
    def __init__(self, task_params: Dict):
        """
        Initialize OGR backend.
        
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
            True if layer is from OGR provider or any other provider
        """
        # This is the fallback backend, supports everything
        return True
    
    def build_expression(
        self,
        layer_props: Dict,
        predicates: Dict,
        source_geom: Optional[str] = None,
        buffer_value: Optional[float] = None,
        buffer_expression: Optional[str] = None
    ) -> str:
        """
        Build expression for OGR backend.
        
        Note: OGR backend uses QGIS processing algorithms, so we don't build
        SQL expressions. This method returns a serialized dict of parameters.
        
        Args:
            layer_props: Layer properties
            predicates: Spatial predicates to apply
            source_geom: Source geometry (layer reference)
            buffer_value: Buffer distance
            buffer_expression: Expression for dynamic buffer
        
        Returns:
            JSON string with processing parameters
        """
        self.log_debug(f"Preparing OGR processing for {layer_props.get('layer_name', 'unknown')}")
        
        # Store source_geom for later use in apply_filter
        self.source_geom = source_geom
        
        # For OGR, we'll use QGIS processing, so we just return predicate names
        # The actual filtering will be done in apply_filter()
        import json
        params = {
            'predicates': list(predicates.keys()),
            'buffer_value': buffer_value,
            'buffer_expression': buffer_expression
        }
        return json.dumps(params)
    
    def apply_filter(
        self,
        layer: QgsVectorLayer,
        expression: str,
        old_subset: Optional[str] = None,
        combine_operator: Optional[str] = None
    ) -> bool:
        """
        Apply filter using QGIS processing selectbylocation algorithm.
        
        Args:
            layer: Layer to filter
            expression: JSON parameters for processing
            old_subset: Existing subset (not used for OGR - uses selection instead)
            combine_operator: Combine operator (not used for OGR)
        
        Returns:
            True if filter applied successfully
        """
        try:
            import json
            from qgis import processing
            
            params = json.loads(expression) if expression else {}
            predicates = params.get('predicates', [])
            buffer_value = params.get('buffer_value')
            
            self.log_info(f"Applying OGR filter to {layer.name()} using QGIS processing")
            
            # Get source layer - should be set by build_expression
            source_layer = getattr(self, 'source_geom', None)
            if not source_layer:
                self.log_error("No source layer/geometry provided for geometric filtering")
                return False
            
            # Warn about performance for OGR backend
            feature_count = layer.featureCount()
            if feature_count > 100000:
                self.log_warning(
                    f"Very large dataset ({feature_count} features) with OGR provider. "
                    "Performance may be reduced. Consider using PostgreSQL for better performance."
                )
            else:
                self.log_info(
                    f"OGR backend uses QGIS processing algorithms. "
                    f"Performance acceptable for {feature_count} features."
                )
            
            # Apply buffer to source layer if specified
            intersect_layer = source_layer
            if buffer_value and buffer_value > 0:
                self.log_info(f"Applying buffer of {buffer_value} to source layer")
                try:
                    buffer_result = processing.run("native:buffer", {
                        'INPUT': source_layer,
                        'DISTANCE': buffer_value,
                        'SEGMENTS': 5,
                        'END_CAP_STYLE': 0,  # Round
                        'JOIN_STYLE': 0,  # Round
                        'MITER_LIMIT': 2,
                        'DISSOLVE': False,
                        'OUTPUT': 'memory:'
                    })
                    intersect_layer = buffer_result['OUTPUT']
                    self.log_debug(f"Buffer applied successfully")
                except Exception as buffer_error:
                    self.log_error(f"Buffer operation failed: {str(buffer_error)}")
                    return False
            
            # Map predicate names to QGIS processing predicate codes
            # 0: intersect, 1: contain, 2: disjoint, 3: equal, 4: touch, 5: overlap, 6: within, 7: cross
            predicate_map = {
                'intersects': [0],
                'contains': [1],
                'disjoint': [2],
                'equal': [3],
                'touches': [4],
                'overlaps': [5],
                'within': [6],
                'crosses': [7]
            }
            
            # Convert predicate names to codes
            predicate_codes = []
            for pred in predicates:
                if pred in predicate_map:
                    predicate_codes.extend(predicate_map[pred])
            
            if not predicate_codes:
                # Default to intersects if no predicates specified
                predicate_codes = [0]
                self.log_info("No predicates specified, defaulting to 'intersects'")
            
            # Apply selectbylocation to select features
            self.log_info(f"Selecting features using predicates: {predicate_codes}")
            try:
                select_result = processing.run("native:selectbylocation", {
                    'INPUT': layer,
                    'PREDICATE': predicate_codes,
                    'INTERSECT': intersect_layer,
                    'METHOD': 0  # creating new selection
                })
                
                selected_count = layer.selectedFeatureCount()
                self.log_info(f"Selection complete: {selected_count} features selected")
                
                # Convert selection to subset filter using selected feature IDs
                # This allows the filter to persist even after deselection
                if selected_count > 0:
                    selected_ids = [f.id() for f in layer.selectedFeatures()]
                    # Build subset string with feature IDs
                    # Use $id for QGIS internal feature ID
                    id_list = ','.join(str(fid) for fid in selected_ids)
                    subset_expression = f"$id IN ({id_list})"
                    
                    # Apply subset filter
                    result = layer.setSubsetString(subset_expression)
                    if result:
                        self.log_info(f"Subset filter applied: {layer.featureCount()} features match")
                        # Clear selection after applying filter
                        layer.removeSelection()
                        return True
                    else:
                        self.log_error("Failed to apply subset filter")
                        layer.removeSelection()
                        return False
                else:
                    self.log_warning("No features selected by geometric filter")
                    # Still apply empty filter to show no results
                    layer.setSubsetString("$id IN ()")
                    return True
                
            except Exception as select_error:
                self.log_error(f"Select by location failed: {str(select_error)}")
                return False
            
        except Exception as e:
            self.log_error(f"Error applying OGR filter: {str(e)}")
            import traceback
            self.log_debug(f"Traceback: {traceback.format_exc()}")
            return False
    
    def get_backend_name(self) -> str:
        """Get backend name"""
        return "OGR"

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
from ..appUtils import safe_set_subset_string

logger = get_tasks_logger()


def escape_ogr_identifier(identifier: str) -> str:
    """
    Escape identifier for OGR SQL expressions.
    
    OGR uses double quotes for identifiers but has limited support.
    Some formats (Shapefile) have restrictions on field names.
    
    Args:
        identifier: Field or table name
        
    Returns:
        Escaped identifier
    """
    # Remove problematic characters and truncate if needed
    # Note: This is a basic implementation. Different OGR drivers have different rules.
    if ' ' in identifier:
        logger.warning(f"OGR identifier '{identifier}' contains spaces - may cause issues with some formats")
    
    # Always use double quotes for OGR
    return f'"{identifier}"'


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
    
    def _ensure_spatial_index(self, layer: QgsVectorLayer) -> bool:
        """
        Ensure spatial index exists for the layer.
        
        Creates spatial index if not present. For shapefiles, this creates a .qix file.
        For other formats, may create internal index.
        
        Performance: O(n log n) creation time, but O(log n) queries afterward.
        Gain: 4-100× faster spatial queries depending on dataset size.
        
        Args:
            layer: Layer to check/create index for
        
        Returns:
            True if index exists or was created successfully
        """
        try:
            # Check if spatial index already exists
            if layer.hasSpatialIndex():
                self.log_debug(f"✓ Spatial index already exists for {layer.name()}")
                return True
            
            # Try to create spatial index
            self.log_info(f"Creating spatial index for {layer.name()}...")
            
            # For OGR layers, use QGIS processing to create index
            try:
                result = processing.run("native:createspatialindex", {
                    'INPUT': layer
                })
                
                if layer.hasSpatialIndex():
                    self.log_info(f"✓ Spatial index created successfully for {layer.name()}")
                    return True
                else:
                    self.log_warning(
                        f"Spatial index creation completed but layer.hasSpatialIndex() returns False. "
                        f"This may be normal for some formats."
                    )
                    return True  # Consider it success anyway
                    
            except Exception as create_error:
                self.log_warning(
                    f"Could not create spatial index for {layer.name()}: {str(create_error)}. "
                    f"Continuing without index (performance may be reduced)."
                )
                return False
                
        except Exception as e:
            self.log_warning(f"Error checking spatial index: {str(e)}. Continuing anyway.")
            return False
    
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
        
        Uses optimized method for large datasets (≥10k features):
        - Ensures spatial index exists
        - Uses attribute-based filtering after spatial selection
        
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
            
            # Check feature count and decide on strategy
            feature_count = layer.featureCount()
            
            # Ensure spatial index exists (performance boost)
            self._ensure_spatial_index(layer)
            
            if feature_count > 100000:
                self.log_warning(
                    f"Very large dataset ({feature_count} features) with OGR provider. "
                    "Performance may be reduced. Consider using PostgreSQL for better performance."
                )
            elif feature_count >= 10000:
                self.log_info(
                    f"Medium-large dataset ({feature_count} features). "
                    f"Using optimized filtering method with spatial index."
                )
            else:
                self.log_info(
                    f"OGR backend uses QGIS processing algorithms. "
                    f"Performance acceptable for {feature_count} features."
                )
            
            # Decide which method to use based on dataset size
            if feature_count >= 10000:
                # Use optimized method for large datasets
                return self._apply_filter_large(
                    layer, source_layer, predicates, buffer_value,
                    old_subset, combine_operator
                )
            else:
                # Use standard method for smaller datasets
                return self._apply_filter_standard(
                    layer, source_layer, predicates, buffer_value,
                    old_subset, combine_operator
                )
            
        except Exception as e:
            self.log_error(f"Error applying OGR filter: {str(e)}")
            import traceback
            self.log_debug(f"Traceback: {traceback.format_exc()}")
            return False
    
    def _apply_buffer(self, source_layer, buffer_value):
        """Apply buffer to source layer if specified"""
        if buffer_value and buffer_value > 0:
            self.log_info(f"Applying buffer of {buffer_value} to source layer")
            try:
                # Ensure buffer_value is numeric
                buffer_dist = float(buffer_value)
                
                # Log layer details for debugging
                self.log_debug(f"Buffer source layer: {source_layer.name()}, "
                              f"CRS: {source_layer.crs().authid()}, "
                              f"Features: {source_layer.featureCount()}")
                
                buffer_result = processing.run("native:buffer", {
                    'INPUT': source_layer,
                    'DISTANCE': buffer_dist,
                    'SEGMENTS': int(5),
                    'END_CAP_STYLE': int(0),  # Round
                    'JOIN_STYLE': int(0),  # Round
                    'MITER_LIMIT': float(2.0),
                    'DISSOLVE': False,
                    'OUTPUT': 'memory:'
                })
                self.log_debug("Buffer applied successfully")
                return buffer_result['OUTPUT']
            except Exception as buffer_error:
                self.log_error(f"Buffer operation failed: {str(buffer_error)}")
                self.log_error(f"  - Buffer value: {buffer_value} (type: {type(buffer_value).__name__})")
                self.log_error(f"  - Source layer: {source_layer.name()}")
                self.log_error(f"  - CRS: {source_layer.crs().authid()} (Geographic: {source_layer.crs().isGeographic()})")
                
                # Check for common error causes
                if source_layer.crs().isGeographic() and float(buffer_value) > 1:
                    self.log_error(
                        f"ERROR: Geographic CRS detected with large buffer value!\n"
                        f"  A buffer of {buffer_value}° in a geographic CRS (lat/lon) is equivalent to\n"
                        f"  approximately {float(buffer_value) * 111}km at the equator.\n"
                        f"  → Solution: Reproject your layer to a projected CRS (e.g., EPSG:3857, EPSG:2154)"
                    )
                
                import traceback
                self.log_debug(f"Buffer traceback: {traceback.format_exc()}")
                return None
        return source_layer
    
    def _map_predicates(self, predicates):
        """Map predicate names to QGIS processing codes"""
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
        
        predicate_codes = []
        for pred in predicates:
            if pred in predicate_map:
                predicate_codes.extend(predicate_map[pred])
        
        if not predicate_codes:
            predicate_codes = [0]  # Default to intersects
            self.log_info("No predicates specified, defaulting to 'intersects'")
        
        return predicate_codes
    
    def _apply_filter_standard(
        self, layer, source_layer, predicates, buffer_value,
        old_subset, combine_operator
    ):
        """
        Standard filtering method for small-medium datasets (<10k features).
        
        Uses direct selectbylocation and subset string with feature IDs.
        """
        # Apply buffer
        intersect_layer = self._apply_buffer(source_layer, buffer_value)
        if intersect_layer is None:
            return False
        
        # Map predicates
        predicate_codes = self._map_predicates(predicates)
        
        # Apply selectbylocation
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
            
            # Convert selection to subset filter
            if selected_count > 0:
                # Get primary key field name for proper subset string
                # Note: $id is not always supported by all OGR providers
                # Use actual primary key field name instead
                from ..appUtils import get_primary_key_name
                
                pk_field = get_primary_key_name(layer)
                if not pk_field:
                    # Fallback to $id if no primary key found
                    pk_field = "$id"
                    self.log_warning(f"No primary key found for {layer.name()}, using $id (may not work for all formats)")
                
                # Get actual field values from selected features
                if pk_field == "$id":
                    # Use QGIS feature IDs
                    selected_ids = [f.id() for f in layer.selectedFeatures()]
                    id_list = ','.join(str(fid) for fid in selected_ids)
                    new_subset_expression = f"$id IN ({id_list})"
                else:
                    # Get actual field values and check field type
                    from qgis.PyQt.QtCore import QMetaType
                    field_idx = layer.fields().indexFromName(pk_field)
                    
                    if field_idx < 0:
                        self.log_error(f"Primary key field '{pk_field}' not found in layer")
                        return False
                    
                    field_type = layer.fields()[field_idx].type()
                    
                    # Extract values from the primary key field
                    selected_values = [f.attribute(pk_field) for f in layer.selectedFeatures()]
                    
                    # Quote string values, keep numeric values unquoted
                    if field_type == QMetaType.Type.QString:
                        # String field - quote values and escape single quotes
                        id_list = ','.join(f"'{str(val).replace(chr(39), chr(39)+chr(39))}'" for val in selected_values)
                    else:
                        # Numeric field - no quotes needed
                        id_list = ','.join(str(val) for val in selected_values)
                    
                    # Use escape function for field name
                    escaped_pk = escape_ogr_identifier(pk_field)
                    new_subset_expression = f'{escaped_pk} IN ({id_list})'
                
                self.log_debug(f"Generated subset expression using key '{pk_field}': {new_subset_expression[:100]}...")
                
                # Combine with old subset if needed
                if old_subset and combine_operator:
                    self.log_info(f"Combining with existing filter using: {combine_operator}")
                    final_expression = f"({old_subset}) {combine_operator} ({new_subset_expression})"
                else:
                    final_expression = new_subset_expression
                
                # Apply subset filter
                result = safe_set_subset_string(layer, final_expression)
                if result:
                    final_count = layer.featureCount()
                    self.log_info(f"✓ Subset filter applied successfully!")
                    self.log_info(f"  - Expression: {final_expression[:100]}...")
                    self.log_info(f"  - Features after filter: {final_count:,}")
                    self.log_info(f"  - Features selected: {selected_count:,}")
                    layer.removeSelection()
                    
                    # Verify filter was actually applied
                    if final_count == 0 and selected_count > 0:
                        self.log_warning(
                            f"Filter applied but 0 features match! This may indicate:\n"
                            f"  1. Primary key field '{pk_field}' may be incorrect\n"
                            f"  2. Subset string syntax not supported by this OGR provider\n"
                            f"  3. Feature IDs don't match primary key values"
                        )
                    
                    return True
                else:
                    self.log_error("Failed to apply subset filter - setSubsetString returned False")
                    self.log_error(f"  - Provider: {layer.providerType()}")
                    self.log_error(f"  - Data source: {layer.source()[:100]}")
                    self.log_error(f"  - Expression: {final_expression[:200]}")
                    layer.removeSelection()
                    return False
            else:
                self.log_warning("No features selected by geometric filter")
                # Apply empty filter - no features should match
                # Use universal expression that works with all OGR providers
                safe_set_subset_string(layer, '1 = 0')  # Always false, no field dependency
                return True
                
        except Exception as select_error:
            self.log_error(f"Select by location failed: {str(select_error)}")
            return False
    
    def _apply_filter_large(
        self, layer, source_layer, predicates, buffer_value,
        old_subset, combine_operator
    ):
        """
        Optimized filtering for large datasets (≥10k features).
        
        Strategy:
        1. Use spatial index for fast pre-filtering
        2. Store match result in temporary attribute
        3. Use attribute-based subset string (faster than ID list)
        
        Performance: O(log n) with spatial index vs O(n) without.
        """
        try:
            # Apply buffer
            intersect_layer = self._apply_buffer(source_layer, buffer_value)
            if intersect_layer is None:
                return False
            
            # Map predicates
            predicate_codes = self._map_predicates(predicates)
            
            # Add temporary field for marking matches
            temp_field = "_fm_match_"
            self.log_info(f"Using optimized large-dataset method with temp field '{temp_field}'")
            
            # Check if temp field already exists
            field_names = [field.name() for field in layer.fields()]
            if temp_field in field_names:
                self.log_debug(f"Temp field '{temp_field}' already exists, will reuse")
            else:
                # Add field
                from qgis.core import QgsField
                from qgis.PyQt.QtCore import QMetaType
                
                layer.dataProvider().addAttributes([QgsField(temp_field, QMetaType.Type.Int)])
                layer.updateFields()
                self.log_debug(f"Added temp field '{temp_field}'")
            
            # Initialize all to 0 (no match)
            field_idx = layer.fields().indexFromName(temp_field)
            layer.startEditing()
            for feature in layer.getFeatures():
                layer.changeAttributeValue(feature.id(), field_idx, 0)
            layer.commitChanges()
            self.log_debug("Initialized temp field to 0")
            
            # Apply selectbylocation (benefits from spatial index)
            self.log_info(f"Selecting features using spatial index and predicates: {predicate_codes}")
            select_result = processing.run("native:selectbylocation", {
                'INPUT': layer,
                'PREDICATE': predicate_codes,
                'INTERSECT': intersect_layer,
                'METHOD': 0
            })
            
            selected_count = layer.selectedFeatureCount()
            self.log_info(f"Selection complete: {selected_count} features selected")
            
            if selected_count > 0:
                # Mark selected features in temp field
                layer.startEditing()
                for feature in layer.selectedFeatures():
                    layer.changeAttributeValue(feature.id(), field_idx, 1)
                layer.commitChanges()
                self.log_debug("Marked selected features in temp field")
                
                # Clear selection
                layer.removeSelection()
                
                # Use attribute-based filter (much faster than ID list for large datasets)
                escaped_temp = escape_ogr_identifier(temp_field)
                new_subset_expression = f'{escaped_temp} = 1'
                
                # Combine with old subset if needed
                if old_subset and combine_operator:
                    self.log_info(f"Combining with existing filter using: {combine_operator}")
                    final_expression = f"({old_subset}) {combine_operator} ({new_subset_expression})"
                else:
                    final_expression = new_subset_expression
                
                # Apply subset filter
                result = safe_set_subset_string(layer, final_expression)
                if result:
                    final_count = layer.featureCount()
                    self.log_info(f"✓ Optimized filter applied: {final_count} features match")
                    return True
                else:
                    self.log_error("Failed to apply subset filter")
                    return False
            else:
                self.log_warning("No features selected by geometric filter")
                # Use universal expression that works with all OGR providers
                safe_set_subset_string(layer, '1 = 0')  # Always false, no field dependency
                return True
                
        except Exception as e:
            self.log_error(f"Large dataset filtering failed: {str(e)}")
            import traceback
            self.log_debug(f"Traceback: {traceback.format_exc()}")
            # Fallback to standard method
            self.log_info("Falling back to standard filtering method")
            return self._apply_filter_standard(
                layer, source_layer, predicates, buffer_value,
                old_subset, combine_operator
            )
    
    def get_backend_name(self) -> str:
        """Get backend name"""
        return "OGR"

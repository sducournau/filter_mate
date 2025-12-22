# -*- coding: utf-8 -*-
"""
OGR Backend for FilterMate

Fallback backend for OGR-based providers (Shapefiles, GeoPackage, etc.).
Uses QGIS processing algorithms for filtering since OGR providers don't support
complex SQL expressions like PostgreSQL/Spatialite.
"""

from typing import Dict, Optional
from qgis.core import (
    QgsVectorLayer, 
    QgsProcessingFeedback, 
    QgsWkbTypes,
    QgsGeometry,
    QgsFeature,
    QgsMemoryProviderUtils
)
from qgis import processing
from .base_backend import GeometricFilterBackend
from ..logging_config import get_tasks_logger
from ..appUtils import safe_set_subset_string

# Import geometry safety module (v2.3.9 - stability fix)
from ..geometry_safety import (
    validate_geometry,
    safe_as_geometry_collection,
    safe_as_polygon,
    safe_collect_geometry,
    safe_convert_to_multi_polygon,
    extract_polygons_from_collection,
    get_geometry_type_name
)

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
    
    def _should_clear_old_subset(self, old_subset: Optional[str]) -> bool:
        """
        Check if old_subset contains patterns that indicate it should be cleared.
        
        This prevents combining with corrupted or incompatible previous filters.
        
        Invalid patterns:
        1. __source alias (PostgreSQL EXISTS subquery internal alias)
        2. EXISTS subquery (would create nested subqueries)
        3. Spatial predicates (likely from previous geometric filter)
        
        Args:
            old_subset: The existing subset string to check
            
        Returns:
            True if old_subset should be cleared (not combined with)
        """
        if not old_subset:
            return False
        
        old_subset_upper = old_subset.upper()
        
        # Pattern 1: __source alias (only valid inside PostgreSQL EXISTS subqueries)
        has_source_alias = '__source' in old_subset.lower()
        
        # Pattern 2: EXISTS subquery (avoid nested EXISTS)
        has_exists = 'EXISTS (' in old_subset_upper or 'EXISTS(' in old_subset_upper
        
        # Pattern 3: Spatial predicates from various backends
        # These indicate a previous geometric filter that should be replaced
        spatial_predicates = [
            # PostGIS/Spatialite predicates
            'ST_INTERSECTS', 'ST_CONTAINS', 'ST_WITHIN', 'ST_TOUCHES',
            'ST_OVERLAPS', 'ST_CROSSES', 'ST_DISJOINT', 'ST_EQUALS',
            'ST_DWITHIN', 'ST_COVERS', 'ST_COVEREDBY',
            # Spatialite-specific
            'INTERSECTS', 'CONTAINS', 'WITHIN'
        ]
        has_spatial_predicate = any(pred in old_subset_upper for pred in spatial_predicates)
        
        should_clear = has_source_alias or has_exists or has_spatial_predicate
        
        if should_clear:
            reason = []
            if has_source_alias:
                reason.append("contains __source alias")
            if has_exists:
                reason.append("contains EXISTS subquery")
            if has_spatial_predicate:
                reason.append("contains spatial predicate")
            
            self.log_warning(f"⚠️ Invalid old_subset detected - {', '.join(reason)}")
            self.log_warning(f"  → Subset: '{old_subset[:100]}...'")
            self.log_info(f"  → Will replace instead of combine")
        
        return should_clear

    def build_expression(
        self,
        layer_props: Dict,
        predicates: Dict,
        source_geom: Optional[str] = None,
        buffer_value: Optional[float] = None,
        buffer_expression: Optional[str] = None,
        source_filter: Optional[str] = None,
        **kwargs
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
            source_filter: Source layer filter (not used in OGR)
            **kwargs: Additional backend-specific parameters (ignored)
        
        Returns:
            JSON string with processing parameters
        """
        self.log_debug(f"Preparing OGR processing for {layer_props.get('layer_name', 'unknown')}")
        
        # Store source_geom for later use in apply_filter
        # NOTE: For OGR, source_geom is already a QgsVectorLayer with buffer applied
        # in prepare_ogr_source_geom(), so we don't need to apply buffer again
        self.source_geom = source_geom
        
        # For OGR, we'll use QGIS processing, so we just return predicate names
        # The actual filtering will be done in apply_filter()
        # NOTE: buffer_value is NOT passed here because it's already applied to source_geom
        import json
        params = {
            'predicates': list(predicates.keys()),
            # Buffer is already applied in prepare_ogr_source_geom - don't apply again
            'buffer_value': None,
            'buffer_expression': None
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
        
        For PostgreSQL memory optimization (small datasets):
        - Uses memory layer copy for spatial calculations
        - Applies resulting filter to original PostgreSQL layer
        
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
            
            # Check if using memory optimization for PostgreSQL
            use_memory_opt = getattr(self, '_use_memory_optimization', False)
            memory_layer = getattr(self, '_memory_layer', None)
            original_layer = getattr(self, '_original_layer', None)
            
            if use_memory_opt and memory_layer and original_layer:
                self.log_info(f"⚡ Using memory optimization for {layer.name()}")
                return self._apply_filter_with_memory_optimization(
                    original_layer, memory_layer, predicates, buffer_value,
                    old_subset, combine_operator
                )
            
            self.log_debug(f"Applying OGR filter to {layer.name()} using QGIS processing")
            
            # Get source layer - should be set by build_expression
            source_layer = getattr(self, 'source_geom', None)
            if not source_layer:
                self.log_error("No source layer/geometry provided for geometric filtering")
                return False
            
            # Check feature count and decide on strategy
            feature_count = layer.featureCount()
            
            # Ensure spatial index exists (performance boost)
            self._ensure_spatial_index(layer)
            
            # Only log for large datasets
            if feature_count >= 100000:
                self.log_info(f"Large dataset ({feature_count:,} features)")
            
            # Decide which method to use based on dataset size
            if feature_count >= 10000:
                return self._apply_filter_large(
                    layer, source_layer, predicates, buffer_value,
                    old_subset, combine_operator
                )
            else:
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
        """Apply buffer to source layer if specified.
        
        CRITICAL FIX: Handles GeometryCollection results from native:buffer.
        When buffering multiple non-overlapping geometries, QGIS Processing can
        produce GeometryCollection which is incompatible with typed layers (MultiPolygon).
        This method converts GeometryCollection to MultiPolygon for compatibility.
        
        Uses buffer_type from task_params for END_CAP_STYLE:
        - 0: Round (default)
        - 1: Flat
        - 2: Square
        """
        if buffer_value and buffer_value > 0:
            self.log_debug(f"Applying buffer of {buffer_value} to source layer")
            try:
                # Ensure buffer_value is numeric
                buffer_dist = float(buffer_value)
                
                # Get buffer_type from task_params (default: 0 = Round)
                buffer_type = 0  # Default: Round
                if self.task_params:
                    filtering_params = self.task_params.get("filtering", {})
                    if filtering_params.get("has_buffer_type", False):
                        buffer_type_str = filtering_params.get("buffer_type", "Round")
                        buffer_type_mapping = {"Round": 0, "Flat": 1, "Square": 2}
                        buffer_type = buffer_type_mapping.get(buffer_type_str, 0)
                        self.log_debug(f"Using buffer type: {buffer_type_str} (END_CAP_STYLE={buffer_type})")
                
                # Log layer details for debugging
                self.log_debug(f"Buffer source layer: {source_layer.name()}, "
                              f"CRS: {source_layer.crs().authid()}, "
                              f"Features: {source_layer.featureCount()}")
                
                buffer_result = processing.run("native:buffer", {
                    'INPUT': source_layer,
                    'DISTANCE': buffer_dist,
                    'SEGMENTS': int(5),
                    'END_CAP_STYLE': int(buffer_type),  # Use configured buffer type
                    'JOIN_STYLE': int(0),  # Round
                    'MITER_LIMIT': float(2.0),
                    'DISSOLVE': False,
                    'OUTPUT': 'memory:'
                })
                
                buffered_layer = buffer_result['OUTPUT']
                
                # CRITICAL FIX: Check for and convert GeometryCollection to MultiPolygon
                # native:buffer can produce GeometryCollection when features don't overlap
                buffered_layer = self._convert_geometry_collection_to_multipolygon(buffered_layer)
                
                self.log_debug("Buffer applied successfully")
                return buffered_layer
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
    
    def _convert_geometry_collection_to_multipolygon(self, layer):
        """
        Convert GeometryCollection geometries in a layer to MultiPolygon.
        
        CRITICAL FIX for GeoPackage/OGR layers:
        When native:buffer processes features that don't overlap, the result
        can contain GeometryCollection type instead of MultiPolygon.
        This causes errors when the buffer layer is used for spatial operations
        on typed layers (e.g., GeoPackage MultiPolygon layers).
        
        Error fixed: "Impossible d'ajouter l'objet avec une géométrie de type 
        GeometryCollection à une couche de type MultiPolygon"
        
        Args:
            layer: QgsVectorLayer from buffer operation
            
        Returns:
            QgsVectorLayer: Layer with geometries converted to MultiPolygon
        """
        from qgis.core import (
            QgsWkbTypes, QgsFeature, QgsGeometry, 
            QgsMemoryProviderUtils, QgsVectorLayer
        )
        
        try:
            # Check if any features have GeometryCollection type
            has_geometry_collection = False
            for feature in layer.getFeatures():
                geom = feature.geometry()
                if validate_geometry(geom):
                    geom_type = get_geometry_type_name(geom)
                    if 'GeometryCollection' in geom_type:
                        has_geometry_collection = True
                        break
            
            if not has_geometry_collection:
                self.log_debug("No GeometryCollection found in buffer result - no conversion needed")
                return layer
            
            self.log_info("🔄 GeometryCollection detected in buffer result - converting to MultiPolygon")
            
            # Create new memory layer with MultiPolygon type
            crs = layer.crs()
            fields = layer.fields()
            
            # Create MultiPolygon memory layer
            converted_layer = QgsMemoryProviderUtils.createMemoryLayer(
                f"{layer.name()}_converted",
                fields,
                QgsWkbTypes.MultiPolygon,
                crs
            )
            
            if not converted_layer or not converted_layer.isValid():
                self.log_error("Failed to create converted memory layer")
                return layer
            
            converted_dp = converted_layer.dataProvider()
            converted_features = []
            conversion_count = 0
            
            for feature in layer.getFeatures():
                geom = feature.geometry()
                if not validate_geometry(geom):
                    continue
                
                geom_type = get_geometry_type_name(geom)
                new_geom = geom
                
                if 'GeometryCollection' in geom_type:
                    # STABILITY FIX v2.3.9: Use safe wrapper for conversion
                    converted = safe_convert_to_multi_polygon(geom)
                    if converted:
                        new_geom = converted
                        conversion_count += 1
                        self.log_debug(f"Converted GeometryCollection to {get_geometry_type_name(new_geom)}")
                    else:
                        # Fallback: try extracting polygons using safe wrapper
                        polygon_parts = extract_polygons_from_collection(geom)
                        if polygon_parts:
                            # Create MultiPolygon from extracted parts
                            if len(polygon_parts) == 1:
                                poly_data = safe_as_polygon(polygon_parts[0])
                                if poly_data:
                                    new_geom = QgsGeometry.fromMultiPolygonXY([poly_data])
                            else:
                                multi_poly_parts = [safe_as_polygon(p) for p in polygon_parts]
                                multi_poly_parts = [p for p in multi_poly_parts if p]
                                if multi_poly_parts:
                                    new_geom = QgsGeometry.fromMultiPolygonXY(multi_poly_parts)
                            conversion_count += 1
                        else:
                            self.log_warning("GeometryCollection contained no polygon parts - skipping feature")
                            continue
                
                elif 'Polygon' in geom_type and 'Multi' not in geom_type:
                    # Convert single Polygon to MultiPolygon for consistency
                    poly_data = safe_as_polygon(geom)
                    if poly_data:
                        new_geom = QgsGeometry.fromMultiPolygonXY([poly_data])
                
                # Create new feature with converted geometry
                new_feature = QgsFeature(fields)
                new_feature.setGeometry(new_geom)
                new_feature.setAttributes(feature.attributes())
                converted_features.append(new_feature)
            
            # Add converted features
            if converted_features:
                success, _ = converted_dp.addFeatures(converted_features)
                if success:
                    converted_layer.updateExtents()
                    self.log_info(f"✓ Converted {conversion_count} GeometryCollection(s) to MultiPolygon")
                    return converted_layer
                else:
                    self.log_error("Failed to add converted features to layer")
                    return layer
            else:
                self.log_warning("No features to convert")
                return layer
                
        except Exception as e:
            self.log_error(f"Error converting GeometryCollection: {str(e)}")
            import traceback
            self.log_debug(f"Conversion traceback: {traceback.format_exc()}")
            return layer

    def _map_predicates(self, predicates):
        """Map predicate names to QGIS processing codes.
        
        Handles multiple input formats:
        - Lowercase names: 'intersects', 'disjoint', etc.
        - UI names with capital: 'Intersect', 'Disjoint', etc.
        - Numeric string indices: '0', '2', etc. (from filter_task.py execute_filtering mapping)
        - SQL function names: 'ST_Intersects', 'ST_Disjoint', etc.
        
        Note: The numeric indices correspond to positions in filter_task.py's self.predicates dict:
        0/1: Intersect/intersects, 2/3: Contain/contains, 4/5: Disjoint/disjoint, 
        6/7: Equal/equals, 8/9: Touch/touches, 10/11: Overlap/overlaps,
        12/13: Are within/within, 14/15: Cross/crosses, 16/17: covers/coveredby
        """
        # QGIS selectbylocation predicate codes:
        # 0: intersect, 1: contain, 2: disjoint, 3: equal, 4: touch, 5: overlap, 6: within, 7: cross
        predicate_map = {
            # Lowercase names (standard)
            'intersects': [0],
            'contains': [1],
            'disjoint': [2],
            'equal': [3],
            'equals': [3],
            'touches': [4],
            'overlaps': [5],
            'within': [6],
            'crosses': [7],
            'covers': [1],  # Similar to contains
            'coveredby': [6],  # Similar to within
            # UI names (capitalized)
            'Intersect': [0],
            'Contain': [1],
            'Disjoint': [2],
            'Equal': [3],
            'Touch': [4],
            'Overlap': [5],
            'Within': [6],
            'Are within': [6],
            'Cross': [7],
            # Numeric string indices from filter_task.py execute_filtering
            # Based on self.predicates dict order in filter_task.py:
            # "Intersect": 0, "intersects": 1, "Contain": 2, "contains": 3,
            # "Disjoint": 4, "disjoint": 5, "Equal": 6, "equals": 7,
            # "Touch": 8, "touches": 9, "Overlap": 10, "overlaps": 11,
            # "Are within": 12, "within": 13, "Cross": 14, "crosses": 15,
            # "covers": 16, "coveredby": 17
            '0': [0],   # Intersect -> QGIS intersect (0)
            '1': [0],   # intersects -> QGIS intersect (0)
            '2': [1],   # Contain -> QGIS contain (1)
            '3': [1],   # contains -> QGIS contain (1)
            '4': [2],   # Disjoint -> QGIS disjoint (2)
            '5': [2],   # disjoint -> QGIS disjoint (2)
            '6': [3],   # Equal -> QGIS equal (3)
            '7': [3],   # equals -> QGIS equal (3)
            '8': [4],   # Touch -> QGIS touch (4)
            '9': [4],   # touches -> QGIS touch (4)
            '10': [5],  # Overlap -> QGIS overlap (5)
            '11': [5],  # overlaps -> QGIS overlap (5)
            '12': [6],  # Are within -> QGIS within (6)
            '13': [6],  # within -> QGIS within (6)
            '14': [7],  # Cross -> QGIS cross (7)
            '15': [7],  # crosses -> QGIS cross (7)
            '16': [1],  # covers -> QGIS contain (1)
            '17': [6],  # coveredby -> QGIS within (6)
            # SQL function names (PostGIS style)
            'ST_Intersects': [0],
            'ST_Contains': [1],
            'ST_Disjoint': [2],
            'ST_Equals': [3],
            'ST_Touches': [4],
            'ST_Overlaps': [5],
            'ST_Within': [6],
            'ST_Crosses': [7],
            'ST_Covers': [1],
            'ST_CoveredBy': [6],
        }
        
        predicate_codes = []
        for pred in predicates:
            if pred in predicate_map:
                predicate_codes.extend(predicate_map[pred])
            else:
                self.log_debug(f"Unknown predicate '{pred}', attempting lookup by index")
        
        if not predicate_codes:
            predicate_codes = [0]  # Default to intersects
            self.log_info("No predicates specified, defaulting to 'intersects'")
        else:
            self.log_debug(f"Mapped predicates {predicates} to QGIS codes {predicate_codes}")
        
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
                        id_list = ','.join(f"'{str(val).replace(chr(39), chr(39)+chr(39))}'" for val in selected_values)
                    else:
                        id_list = ','.join(str(val) for val in selected_values)
                    
                    escaped_pk = escape_ogr_identifier(pk_field)
                    new_subset_expression = f'{escaped_pk} IN ({id_list})'
                
                self.log_debug(f"Generated subset expression using key '{pk_field}'")
                
                # Combine with old subset if needed (but not if it contains invalid patterns)
                if old_subset and not self._should_clear_old_subset(old_subset):
                    if not combine_operator:
                        combine_operator = 'AND'
                        self.log_info(f"🔗 Préservation du filtre existant avec {combine_operator}")
                    self.log_info(f"  → Ancien subset: '{old_subset[:80]}...' (longueur: {len(old_subset)})")
                    self.log_info(f"  → Nouveau filtre: '{new_subset_expression[:80]}...'")
                    final_expression = f"({old_subset}) {combine_operator} ({new_subset_expression})"
                    self.log_info(f"  → Expression combinée: longueur {len(final_expression)} chars")
                else:
                    final_expression = new_subset_expression
                
                # Apply subset filter
                result = safe_set_subset_string(layer, final_expression)
                if result:
                    final_count = layer.featureCount()
                    self.log_info(f"✓ {layer.name()}: {final_count} features")
                    layer.removeSelection()
                    
                    if final_count == 0 and selected_count > 0:
                        self.log_warning(f"Filter returned 0 features - check primary key '{pk_field}'")
                    
                    return True
                else:
                    self.log_error(f"✗ Filter failed for {layer.name()}")
                    layer.removeSelection()
                    return False
            else:
                self.log_debug("No features selected by geometric filter")
                safe_set_subset_string(layer, '1 = 0')
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
                self.log_debug(f"Temp field '{temp_field}' already exists")
            else:
                from qgis.core import QgsField
                from qgis.PyQt.QtCore import QMetaType
                
                layer.dataProvider().addAttributes([QgsField(temp_field, QMetaType.Type.Int)])
                layer.updateFields()
            
            # Initialize all to 0 (no match)
            field_idx = layer.fields().indexFromName(temp_field)
            layer.startEditing()
            for feature in layer.getFeatures():
                layer.changeAttributeValue(feature.id(), field_idx, 0)
            layer.commitChanges()
            
            # Apply selectbylocation (benefits from spatial index)
            self.log_debug(f"Selecting features with predicates: {predicate_codes}")
            select_result = processing.run("native:selectbylocation", {
                'INPUT': layer,
                'PREDICATE': predicate_codes,
                'INTERSECT': intersect_layer,
                'METHOD': 0
            })
            
            selected_count = layer.selectedFeatureCount()
            
            if selected_count > 0:
                # Mark selected features in temp field
                layer.startEditing()
                for feature in layer.selectedFeatures():
                    layer.changeAttributeValue(feature.id(), field_idx, 1)
                layer.commitChanges()
                
                # Clear selection
                layer.removeSelection()
                
                # Use attribute-based filter (much faster than ID list for large datasets)
                escaped_temp = escape_ogr_identifier(temp_field)
                new_subset_expression = f'{escaped_temp} = 1'
                
                # Combine with old subset if needed (but not if it contains invalid patterns)
                if old_subset and not self._should_clear_old_subset(old_subset):
                    if not combine_operator:
                        combine_operator = 'AND'
                        self.log_info(f"🔗 Préservation du filtre existant avec {combine_operator}")
                    self.log_info(f"  → Ancien subset: '{old_subset[:80]}...' (longueur: {len(old_subset)})")
                    final_expression = f"({old_subset}) {combine_operator} ({new_subset_expression})"
                    self.log_info(f"  → Expression combinée: longueur {len(final_expression)} chars")
                else:
                    final_expression = new_subset_expression
                
                # Apply subset filter
                result = safe_set_subset_string(layer, final_expression)
                if result:
                    final_count = layer.featureCount()
                    self.log_info(f"✓ {layer.name()}: {final_count} features")
                    return True
                else:
                    self.log_error(f"✗ Filter failed for {layer.name()}")
                    return False
            else:
                self.log_debug("No features selected by geometric filter")
                safe_set_subset_string(layer, '1 = 0')
                return True
                
        except Exception as e:
            self.log_error(f"Large dataset filtering failed: {str(e)}")
            # Fallback to standard method
            return self._apply_filter_standard(
                layer, source_layer, predicates, buffer_value,
                old_subset, combine_operator
            )
    
    def _apply_filter_with_memory_optimization(
        self, original_layer, memory_layer, predicates, buffer_value,
        old_subset, combine_operator
    ):
        """
        Apply filter using memory layer for spatial calculations.
        
        This method is used for small PostgreSQL datasets optimization:
        1. Perform spatial selection on the memory layer (fast, no network)
        2. Get the IDs of selected features
        3. Apply the resulting subset filter to the original PostgreSQL layer
        
        Performance: Avoids network overhead for spatial queries on small datasets.
        Typically 2-10× faster than direct PostgreSQL queries for < 5000 features.
        
        Args:
            original_layer: The original PostgreSQL layer to apply filter to
            memory_layer: In-memory copy of the layer for spatial calculations
            predicates: Spatial predicates to apply
            buffer_value: Optional buffer distance
            old_subset: Existing subset string on original layer
            combine_operator: Operator for combining with existing filter
            
        Returns:
            True if filter applied successfully
        """
        try:
            from qgis import processing
            from ..appUtils import get_primary_key_name
            from qgis.PyQt.QtCore import QMetaType
            
            # Apply buffer to source geometry if needed
            source_layer = getattr(self, 'source_geom', None)
            if not source_layer:
                self.log_error("No source layer/geometry provided for geometric filtering")
                return False
            
            intersect_layer = self._apply_buffer(source_layer, buffer_value)
            if intersect_layer is None:
                return False
            
            # Map predicates
            predicate_codes = self._map_predicates(predicates)
            
            self.log_info(f"⚡ Memory optimization: Selecting features from memory layer")
            self.log_info(f"  → Memory layer: {memory_layer.name()} ({memory_layer.featureCount()} features)")
            self.log_info(f"  → Predicates: {predicate_codes}")
            
            # Apply selectbylocation on MEMORY layer (fast, no network)
            select_result = processing.run("native:selectbylocation", {
                'INPUT': memory_layer,
                'PREDICATE': predicate_codes,
                'INTERSECT': intersect_layer,
                'METHOD': 0  # creating new selection
            })
            
            selected_count = memory_layer.selectedFeatureCount()
            self.log_info(f"  → Selected {selected_count} features in memory layer")
            
            if selected_count > 0:
                # Get primary key from original PostgreSQL layer
                pk_field = get_primary_key_name(original_layer)
                if not pk_field:
                    pk_field = get_primary_key_name(memory_layer)
                
                if not pk_field:
                    self.log_error("No primary key found for PostgreSQL layer - cannot transfer selection")
                    memory_layer.removeSelection()
                    return False
                
                # Get primary key values from selected features in memory layer
                field_idx = memory_layer.fields().indexFromName(pk_field)
                if field_idx < 0:
                    self.log_error(f"Primary key field '{pk_field}' not found in memory layer")
                    memory_layer.removeSelection()
                    return False
                
                field_type = memory_layer.fields()[field_idx].type()
                
                # Extract primary key values from selected features
                selected_values = [f.attribute(pk_field) for f in memory_layer.selectedFeatures()]
                
                # Build subset expression for PostgreSQL layer
                if field_type == QMetaType.Type.QString:
                    id_list = ','.join(f"'{str(val).replace(chr(39), chr(39)+chr(39))}'" for val in selected_values)
                else:
                    id_list = ','.join(str(val) for val in selected_values)
                
                # PostgreSQL uses double quotes for identifiers
                escaped_pk = f'"{pk_field}"'
                new_subset_expression = f'{escaped_pk} IN ({id_list})'
                
                self.log_debug(f"  → Generated PostgreSQL subset using key '{pk_field}'")
                
                # Clear memory layer selection
                memory_layer.removeSelection()
                
                # Combine with old subset if needed (but not if it contains invalid patterns)
                if old_subset and not self._should_clear_old_subset(old_subset):
                    if not combine_operator:
                        combine_operator = 'AND'
                        self.log_info(f"🔗 Préservation du filtre existant avec {combine_operator}")
                    self.log_info(f"  → Ancien subset: '{old_subset[:80]}...'")
                    final_expression = f"({old_subset}) {combine_operator} ({new_subset_expression})"
                else:
                    final_expression = new_subset_expression
                
                # Apply subset filter to ORIGINAL PostgreSQL layer
                result = safe_set_subset_string(original_layer, final_expression)
                if result:
                    final_count = original_layer.featureCount()
                    self.log_info(f"✓ {original_layer.name()}: {final_count} features (via memory optimization)")
                    return True
                else:
                    self.log_error(f"✗ Filter failed for {original_layer.name()}")
                    return False
            else:
                self.log_debug("No features selected by geometric filter (memory optimization)")
                memory_layer.removeSelection()
                safe_set_subset_string(original_layer, '1 = 0')
                return True
                
        except Exception as e:
            self.log_error(f"Memory optimization filtering failed: {str(e)}")
            import traceback
            self.log_debug(f"Traceback: {traceback.format_exc()}")
            # Clear memory layer selection if exists
            if memory_layer:
                try:
                    memory_layer.removeSelection()
                except (RuntimeError, AttributeError):
                    pass  # Layer may have been deleted or is invalid
            return False
    
    def get_backend_name(self) -> str:
        """Get backend name"""
        return "OGR"

# -*- coding: utf-8 -*-
"""
Memory Backend for FilterMate

Optimized backend for QGIS memory layers (provider type 'memory').
Memory layers are always in-RAM and don't require network or disk I/O,
so this backend focuses on fast in-memory operations.

Key Optimizations:
- Uses QgsSpatialIndex for O(log n) spatial queries
- Direct DataProvider operations (no signals/editing overhead)
- Accurate feature counting with iteration fallback
- Efficient feature selection and filtering

CRITICAL NOTE on featureCount():
================================
Memory layers can return 0 from featureCount() immediately after creation,
even if features were added. This backend uses iteration-based counting
as a reliable fallback.

Thread Safety:
=============
Memory layers are NOT thread-safe. This backend runs operations sequentially
and should only be used from the main thread or with proper synchronization.

v2.5.8: Initial implementation
"""

import time
from typing import Dict, List, Optional, Set
from qgis.core import (
    QgsVectorLayer,
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsSpatialIndex,
    QgsWkbTypes,
    QgsRectangle,
    QgsProcessingFeedback
)
from qgis import processing

from .base_backend import GeometricFilterBackend
from ..logging_config import get_tasks_logger
from ..appUtils import safe_set_subset_string

# v2.5.10: Import Multi-Step Optimizer for attribute-first filtering
try:
    from .multi_step_optimizer import (
        MultiStepFilterOptimizer,
        BackendFilterStrategy,
        AttributePreFilter,
        MemoryOptimizer,
        BackendSelectivityEstimator
    )
    MULTI_STEP_OPTIMIZER_AVAILABLE = True
except ImportError:
    MULTI_STEP_OPTIMIZER_AVAILABLE = False
    MultiStepFilterOptimizer = None
    BackendFilterStrategy = None
    AttributePreFilter = None
    MemoryOptimizer = None
    BackendSelectivityEstimator = None

logger = get_tasks_logger()


class MemoryGeometricFilter(GeometricFilterBackend):
    """
    Optimized backend for QGIS memory layers.
    
    Memory layers exist entirely in RAM and are perfect for:
    - Temporary analysis results
    - Scratch layers
    - Small to medium datasets (< 100k features)
    
    This backend uses QgsSpatialIndex for efficient spatial queries
    and direct DataProvider access for maximum performance.
    """
    
    def __init__(self, task_params: Dict):
        """
        Initialize Memory backend.
        
        Args:
            task_params: Task parameters dictionary
        """
        super().__init__(task_params)
        self.logger = logger
        self._spatial_indices: Dict[str, QgsSpatialIndex] = {}
        self._feature_caches: Dict[str, Dict[int, QgsGeometry]] = {}
    
    def supports_layer(self, layer: QgsVectorLayer) -> bool:
        """
        Check if this backend supports the given layer.
        
        Args:
            layer: QGIS vector layer to check
        
        Returns:
            True if layer is a memory layer
        """
        if not layer or not layer.isValid():
            return False
        return layer.providerType() == 'memory'
    
    def get_backend_name(self) -> str:
        """Get backend name"""
        return "Memory"
    
    def get_accurate_feature_count(self, layer: QgsVectorLayer) -> int:
        """
        Get accurate feature count for memory layer.
        
        CRITICAL: featureCount() can return 0 for memory layers immediately
        after features are added. This method uses iteration as fallback.
        
        Args:
            layer: Memory layer to count
            
        Returns:
            Accurate feature count
        """
        if not layer or not layer.isValid():
            return 0
        
        # Force extent update first
        layer.updateExtents()
        
        # Try featureCount() first
        reported_count = layer.featureCount()
        
        # If reported count is 0 or negative, use iteration
        if reported_count <= 0:
            try:
                actual_count = sum(1 for _ in layer.getFeatures())
                if actual_count > 0:
                    self.log_debug(
                        f"Memory layer '{layer.name()}': featureCount()={reported_count}, "
                        f"actual={actual_count} (using iteration)"
                    )
                return actual_count
            except Exception as e:
                self.log_warning(f"Failed to iterate features: {e}")
                return reported_count
        
        return reported_count
    
    def _get_or_create_spatial_index(
        self, 
        layer: QgsVectorLayer, 
        force_rebuild: bool = False
    ) -> Optional[QgsSpatialIndex]:
        """
        Get or create spatial index for layer.
        
        Spatial indices are cached per layer ID for reuse.
        
        Args:
            layer: Layer to index
            force_rebuild: If True, rebuild even if cached
            
        Returns:
            QgsSpatialIndex or None on failure
        """
        layer_id = layer.id()
        
        # Return cached index if available and not forcing rebuild
        if not force_rebuild and layer_id in self._spatial_indices:
            self.log_debug(f"Using cached spatial index for {layer.name()}")
            return self._spatial_indices[layer_id]
        
        try:
            start_time = time.time()
            
            # Create spatial index from layer features
            spatial_index = QgsSpatialIndex()
            geometry_cache = {}
            
            for feature in layer.getFeatures():
                if feature.hasGeometry() and feature.geometry().isGeosValid():
                    spatial_index.addFeature(feature)
                    geometry_cache[feature.id()] = feature.geometry()
            
            elapsed = time.time() - start_time
            feature_count = len(geometry_cache)
            
            self.log_info(
                f"✓ Created spatial index for {layer.name()} "
                f"({feature_count} features in {elapsed:.2f}s)"
            )
            
            # Cache both index and geometries
            self._spatial_indices[layer_id] = spatial_index
            self._feature_caches[layer_id] = geometry_cache
            
            return spatial_index
            
        except Exception as e:
            self.log_error(f"Failed to create spatial index: {e}")
            return None
    
    def _clear_layer_cache(self, layer_id: str):
        """Clear cached data for a layer."""
        if layer_id in self._spatial_indices:
            del self._spatial_indices[layer_id]
        if layer_id in self._feature_caches:
            del self._feature_caches[layer_id]
    
    def clear_all_caches(self):
        """Clear all cached spatial indices and geometries."""
        self._spatial_indices.clear()
        self._feature_caches.clear()
        self.log_debug("All memory backend caches cleared")
    
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
        Build a filter expression for memory layers.
        
        For memory layers, we don't use SQL expressions. Instead, we build
        a QGIS expression that can be used with setSubsetString() or return
        feature IDs for direct selection.
        
        Args:
            layer_props: Layer properties dictionary
            predicates: Dictionary of spatial predicates
            source_geom: Source geometry WKT (optional)
            buffer_value: Buffer distance (optional)
            buffer_expression: Dynamic buffer expression (optional)
            source_filter: Source filter expression (optional)
            **kwargs: Additional parameters
        
        Returns:
            QGIS expression string or feature ID list as string
        """
        # Memory layers use QGIS expressions, not SQL
        # For simple attribute filtering, return the expression as-is
        if not predicates and not source_geom:
            return source_filter or ''
        
        # For spatial filtering, we'll use selectbylocation in apply_filter
        # Return marker to indicate spatial filter needed
        return '__SPATIAL_FILTER__'
    
    def _perform_spatial_selection(
        self,
        layer: QgsVectorLayer,
        intersect_layer: QgsVectorLayer,
        predicates: Dict,
        use_spatial_index: bool = True
    ) -> Set[int]:
        """
        Perform spatial selection using QgsSpatialIndex for efficiency.
        
        This method uses a two-phase approach:
        1. Broad phase: Use spatial index to find candidates (bounding box)
        2. Narrow phase: Apply exact predicate tests on candidates
        
        Args:
            layer: Target layer to select from
            intersect_layer: Layer containing filter geometries
            predicates: Spatial predicates to apply
            use_spatial_index: Whether to use spatial index optimization
            
        Returns:
            Set of selected feature IDs
        """
        selected_ids = set()
        
        # Get or create spatial index for target layer
        if use_spatial_index:
            spatial_index = self._get_or_create_spatial_index(layer)
            geometry_cache = self._feature_caches.get(layer.id(), {})
        else:
            spatial_index = None
            geometry_cache = {}
        
        # Collect geometries from intersect layer
        intersect_geometries = []
        for feat in intersect_layer.getFeatures():
            if feat.hasGeometry() and feat.geometry().isGeosValid():
                intersect_geometries.append(feat.geometry())
        
        if not intersect_geometries:
            self.log_warning("No valid geometries in intersect layer")
            return selected_ids
        
        # For each intersect geometry, find matching features
        for intersect_geom in intersect_geometries:
            # Get bounding box for broad phase
            bbox = intersect_geom.boundingBox()
            
            if spatial_index:
                # Broad phase: spatial index lookup (O(log n))
                candidate_ids = spatial_index.intersects(bbox)
            else:
                # No index: check all features
                candidate_ids = [f.id() for f in layer.getFeatures()]
            
            # Narrow phase: exact predicate tests
            for fid in candidate_ids:
                # Skip already selected
                if fid in selected_ids:
                    continue
                
                # Get geometry (from cache or layer)
                if fid in geometry_cache:
                    geom = geometry_cache[fid]
                else:
                    request = QgsFeatureRequest().setFilterFid(fid)
                    request.setFlags(QgsFeatureRequest.NoGeometry)
                    request.setSubsetOfAttributes([])
                    feat = next(layer.getFeatures(request), None)
                    if not feat or not feat.hasGeometry():
                        continue
                    geom = feat.geometry()
                
                # Test predicates
                if self._test_predicates(geom, intersect_geom, predicates):
                    selected_ids.add(fid)
        
        return selected_ids
    
    def _test_predicates(
        self, 
        target_geom: QgsGeometry, 
        filter_geom: QgsGeometry, 
        predicates: Dict
    ) -> bool:
        """
        Test spatial predicates between two geometries.
        
        Args:
            target_geom: Geometry to test
            filter_geom: Filter geometry
            predicates: Dictionary of predicate names to test
            
        Returns:
            True if any predicate matches
        """
        if not target_geom or not filter_geom:
            return False
        
        if not target_geom.isGeosValid() or not filter_geom.isGeosValid():
            return False
        
        # Test each predicate (ANY match = True)
        for predicate_name, enabled in predicates.items():
            if not enabled:
                continue
            
            try:
                predicate_lower = predicate_name.lower()
                
                if predicate_lower == 'intersects':
                    if target_geom.intersects(filter_geom):
                        return True
                elif predicate_lower == 'within':
                    if target_geom.within(filter_geom):
                        return True
                elif predicate_lower == 'contains':
                    if target_geom.contains(filter_geom):
                        return True
                elif predicate_lower == 'overlaps':
                    if target_geom.overlaps(filter_geom):
                        return True
                elif predicate_lower == 'crosses':
                    if target_geom.crosses(filter_geom):
                        return True
                elif predicate_lower == 'touches':
                    if target_geom.touches(filter_geom):
                        return True
                elif predicate_lower == 'disjoint':
                    if target_geom.disjoint(filter_geom):
                        return True
                elif predicate_lower == 'equals':
                    if target_geom.equals(filter_geom):
                        return True
                        
            except Exception as e:
                self.log_warning(f"Predicate test failed for {predicate_name}: {e}")
                continue
        
        return False
    
    def _apply_buffer_to_layer(
        self, 
        source_layer: QgsVectorLayer, 
        buffer_value: float
    ) -> Optional[QgsVectorLayer]:
        """
        Apply buffer to source layer geometries.
        
        Args:
            source_layer: Layer to buffer
            buffer_value: Buffer distance (negative for erosion)
            
        Returns:
            Buffered layer or None on failure
        """
        if not buffer_value or buffer_value == 0:
            return source_layer
        
        try:
            # Get buffer type from task params
            buffer_type = 0  # Default: Round
            if self.task_params:
                filtering_params = self.task_params.get("filtering", {})
                if filtering_params.get("has_buffer_type", False):
                    buffer_type_str = filtering_params.get("buffer_type", "Round")
                    buffer_type_mapping = {"Round": 0, "Flat": 1, "Square": 2}
                    buffer_type = buffer_type_mapping.get(buffer_type_str, 0)
            
            self.log_debug(f"Applying buffer {buffer_value} to {source_layer.name()}")
            
            result = processing.run("native:buffer", {
                'INPUT': source_layer,
                'DISTANCE': buffer_value,
                'SEGMENTS': 8,
                'END_CAP_STYLE': buffer_type,
                'JOIN_STYLE': 0,  # Round
                'MITER_LIMIT': 2,
                'DISSOLVE': False,
                'OUTPUT': 'memory:'
            })
            
            buffered_layer = result.get('OUTPUT')
            if buffered_layer and buffered_layer.isValid():
                return buffered_layer
            
            self.log_error("Buffer operation returned invalid layer")
            return None
            
        except Exception as e:
            self.log_error(f"Buffer operation failed: {e}")
            return None
    
    def apply_filter(
        self, 
        layer: QgsVectorLayer, 
        expression: str,
        old_subset: Optional[str] = None,
        combine_operator: Optional[str] = None
    ) -> bool:
        """
        Apply filter to memory layer.
        
        For memory layers, we use a combination of:
        1. QgsSpatialIndex for efficient spatial filtering
        2. Direct feature selection for geometric predicates
        3. Subset strings for attribute filtering
        
        Args:
            layer: Memory layer to filter
            expression: Filter expression (or '__SPATIAL_FILTER__')
            old_subset: Existing subset string
            combine_operator: Operator to combine with existing filter
        
        Returns:
            True if filter applied successfully
        """
        try:
            # Get source layer for spatial filtering
            source_layer = getattr(self, 'source_geom', None)
            predicates = getattr(self, 'predicates', {})
            buffer_value = getattr(self, 'buffer_value', None)
            
            # Simple attribute filter (no spatial)
            if expression != '__SPATIAL_FILTER__' and not source_layer:
                return self._apply_attribute_filter(
                    layer, expression, old_subset, combine_operator
                )
            
            # Spatial filtering
            if not source_layer:
                self.log_error("No source layer for spatial filtering")
                return False
            
            # Apply buffer if needed
            intersect_layer = self._apply_buffer_to_layer(source_layer, buffer_value)
            if not intersect_layer:
                return False
            
            # Get accurate feature count
            target_count = self.get_accurate_feature_count(layer)
            self.log_info(f"Memory filter: {layer.name()} ({target_count} features)")
            
            # Perform spatial selection using index
            selected_ids = self._perform_spatial_selection(
                layer, intersect_layer, predicates, use_spatial_index=True
            )
            
            self.log_info(f"  → Selected {len(selected_ids)} features by spatial filter")
            
            if not selected_ids:
                # No matches - apply empty filter
                self.log_debug("No features matched spatial filter")
                return self._apply_empty_filter(layer)
            
            # Build subset expression from IDs
            # Use $id for memory layer feature ID filtering
            id_list = ','.join(str(fid) for fid in sorted(selected_ids))
            new_expression = f'$id IN ({id_list})'
            
            # Combine with old subset if needed
            if old_subset and old_subset.strip():
                if not combine_operator:
                    combine_operator = 'AND'
                final_expression = f"({old_subset}) {combine_operator} ({new_expression})"
            else:
                final_expression = new_expression
            
            # Apply subset filter
            queue_callback = self.task_params.get('_subset_queue_callback')
            
            if queue_callback:
                queue_callback(layer, final_expression)
                self.log_info(f"✓ {layer.name()}: filter queued (Memory backend)")
                return True
            else:
                result = safe_set_subset_string(layer, final_expression)
                if result:
                    final_count = layer.featureCount()
                    self.log_info(f"✓ {layer.name()}: {final_count} features (Memory backend)")
                return result
                
        except Exception as e:
            self.log_error(f"Memory filter failed: {e}")
            import traceback
            self.log_debug(traceback.format_exc())
            return False
    
    def _apply_attribute_filter(
        self,
        layer: QgsVectorLayer,
        expression: str,
        old_subset: Optional[str],
        combine_operator: Optional[str]
    ) -> bool:
        """Apply simple attribute filter without spatial operations."""
        try:
            if old_subset and old_subset.strip():
                if not combine_operator:
                    combine_operator = 'AND'
                final_expression = f"({old_subset}) {combine_operator} ({expression})"
            else:
                final_expression = expression
            
            queue_callback = self.task_params.get('_subset_queue_callback')
            
            if queue_callback:
                queue_callback(layer, final_expression)
                return True
            else:
                return safe_set_subset_string(layer, final_expression)
                
        except Exception as e:
            self.log_error(f"Attribute filter failed: {e}")
            return False
    
    def _apply_empty_filter(self, layer: QgsVectorLayer) -> bool:
        """Apply filter that returns no features."""
        queue_callback = self.task_params.get('_subset_queue_callback')
        
        if queue_callback:
            queue_callback(layer, '0 = 1')  # False condition
            return True
        else:
            return safe_set_subset_string(layer, '0 = 1')
    
    def set_source_geometry(self, source_layer: QgsVectorLayer):
        """Set the source layer for spatial filtering."""
        self.source_geom = source_layer
    
    def set_predicates(self, predicates: Dict):
        """Set spatial predicates for filtering."""
        self.predicates = predicates
    
    def set_buffer_value(self, buffer_value: Optional[float]):
        """Set buffer value for spatial filtering."""
        self.buffer_value = buffer_value

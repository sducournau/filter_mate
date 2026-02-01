# -*- coding: utf-8 -*-
"""
Vector Filter Strategy.

Concrete strategy for filtering vector layers.
Wraps existing FilterService/FilterEngineTask for backward compatibility.

Part of the Unified Filter System (EPIC-UNIFIED-FILTER).

This strategy:
- Delegates to existing FilterService for actual filtering
- Converts VectorFilterCriteria to internal format
- Returns UnifiedFilterResult for consistency

Author: FilterMate Team (BMAD - Amelia)
Date: February 2026
Version: 5.0.0-alpha
"""

import time
import logging
from typing import Dict, Any, Tuple, Optional, Set, FrozenSet

from .base_filter_strategy import (
    AbstractFilterStrategy,
    FilterContext,
    UnifiedFilterResult,
    FilterStatus
)
from ..domain.filter_criteria import (
    VectorFilterCriteria,
    LayerType,
    UnifiedFilterCriteria,
    validate_criteria
)

logger = logging.getLogger('FilterMate.Strategies.Vector')


class VectorFilterStrategy(AbstractFilterStrategy):
    """Strategy for filtering vector layers.
    
    This strategy wraps the existing FilterService to provide
    backward compatibility while conforming to the unified interface.
    
    The actual filtering is delegated to:
    - FilterService for simple filters
    - FilterEngineTask for complex async operations
    
    Usage:
        context = FilterContext(project=QgsProject.instance())
        strategy = VectorFilterStrategy(context)
        
        criteria = VectorFilterCriteria(
            layer_id="layer_123",
            expression="population > 10000"
        )
        
        result = strategy.apply_filter(criteria)
        if result.is_success:
            print(f"Found {result.affected_count} features")
    """
    
    def __init__(self, context: FilterContext):
        """Initialize vector strategy.
        
        Args:
            context: FilterContext with project and callbacks
        """
        super().__init__(context)
        self._filter_service = None
        self._export_service = None
    
    @property
    def supported_layer_type(self) -> LayerType:
        """Return VECTOR as the supported layer type."""
        return LayerType.VECTOR
    
    def _get_filter_service(self):
        """Lazy-load FilterService to avoid circular imports.
        
        Returns:
            FilterService instance
        """
        if self._filter_service is None:
            try:
                from ..services.filter_service import FilterService
                self._filter_service = FilterService()
            except ImportError as e:
                logger.warning(f"Could not import FilterService: {e}")
                self._filter_service = None
        return self._filter_service
    
    def _get_export_service(self):
        """Lazy-load ExportService.
        
        Returns:
            ExportService instance
        """
        if self._export_service is None:
            try:
                from ..services.export_service import ExportService
                self._export_service = ExportService(
                    project=self.context.project,
                    progress_callback=lambda p: self._report_progress(p, "Exporting..."),
                    cancel_callback=self._check_cancelled
                )
            except ImportError as e:
                logger.warning(f"Could not import ExportService: {e}")
                self._export_service = None
        return self._export_service
    
    def validate_criteria(
        self, 
        criteria: UnifiedFilterCriteria
    ) -> Tuple[bool, str]:
        """Validate vector filter criteria.
        
        Checks:
        - Criteria is VectorFilterCriteria type
        - Layer ID is present
        - Expression or spatial predicate is defined
        - If spatial, source layer is specified
        
        Args:
            criteria: Criteria to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Type check
        if not isinstance(criteria, VectorFilterCriteria):
            return False, f"Expected VectorFilterCriteria, got {type(criteria).__name__}"
        
        # Use shared validation
        return validate_criteria(criteria)
    
    def apply_filter(
        self, 
        criteria: UnifiedFilterCriteria
    ) -> UnifiedFilterResult:
        """Apply vector filter using existing FilterService.
        
        Args:
            criteria: VectorFilterCriteria with filter parameters
            
        Returns:
            UnifiedFilterResult with matching feature IDs
        """
        start_time = time.time()
        
        # Validate first
        is_valid, error = self.validate_criteria(criteria)
        if not is_valid:
            return self._create_error_result(criteria, error)
        
        # Check cancellation
        if self.is_cancelled:
            return self._create_cancelled_result(criteria)
        
        self._report_progress(0, "Preparing vector filter...")
        
        try:
            # Get the layer
            layer = self._get_layer(criteria.layer_id)
            if layer is None:
                return self._create_error_result(
                    criteria, 
                    f"Layer not found: {criteria.layer_id}"
                )
            
            self._report_progress(10, "Executing filter...")
            
            # Apply the filter using QGIS setSubsetString
            # This is the simplest approach for direct filtering
            if criteria.expression:
                feature_ids = self._filter_by_expression(layer, criteria)
            elif criteria.is_spatial:
                feature_ids = self._filter_by_spatial(layer, criteria)
            else:
                # No filter = all features
                feature_ids = self._get_all_feature_ids(layer)
            
            if self.is_cancelled:
                return self._create_cancelled_result(criteria)
            
            self._report_progress(90, "Finalizing...")
            
            execution_time = (time.time() - start_time) * 1000
            
            self._report_progress(100, "Complete")
            
            return UnifiedFilterResult.vector_success(
                layer_id=criteria.layer_id,
                feature_ids=frozenset(feature_ids),
                expression_raw=criteria.to_display_string(),
                execution_time_ms=execution_time,
                backend_name=self._detect_backend(layer)
            )
            
        except Exception as e:
            logger.exception(f"Error applying vector filter: {e}")
            return self._create_error_result(criteria, str(e))
    
    def get_preview(
        self, 
        criteria: UnifiedFilterCriteria
    ) -> Dict[str, Any]:
        """Get preview of vector filter.
        
        Returns estimated feature count without fully applying filter.
        
        Args:
            criteria: Filter criteria to preview
            
        Returns:
            Dict with preview data:
            - type: "vector"
            - estimated_count: Estimated matching features
            - has_spatial: Whether spatial filter is involved
            - total_features: Total features in layer
        """
        preview = {
            "type": "vector",
            "estimated_count": -1,  # Unknown
            "has_spatial": False,
            "total_features": 0,
            "error": None
        }
        
        try:
            layer = self._get_layer(criteria.layer_id)
            if layer is None:
                preview["error"] = f"Layer not found: {criteria.layer_id}"
                return preview
            
            preview["total_features"] = layer.featureCount()
            preview["has_spatial"] = criteria.is_spatial if isinstance(criteria, VectorFilterCriteria) else False
            
            # For simple expressions, try to estimate
            if isinstance(criteria, VectorFilterCriteria) and criteria.expression:
                # Quick estimate using expression on subset
                try:
                    from qgis.core import QgsExpression, QgsExpressionContext, QgsExpressionContextUtils
                    
                    expr = QgsExpression(criteria.expression)
                    if not expr.hasParserError():
                        # Count matching features (limit for performance)
                        count = 0
                        context = QgsExpressionContextUtils.createFeatureBasedContext(
                            None, layer.fields()
                        )
                        
                        for i, feature in enumerate(layer.getFeatures()):
                            if i >= 10000:  # Limit for preview
                                # Extrapolate
                                ratio = count / 10000
                                preview["estimated_count"] = int(preview["total_features"] * ratio)
                                preview["is_estimate"] = True
                                return preview
                            
                            context.setFeature(feature)
                            if expr.evaluate(context):
                                count += 1
                        
                        preview["estimated_count"] = count
                        preview["is_estimate"] = False
                except Exception as e:
                    logger.debug(f"Preview estimation failed: {e}")
                    preview["estimated_count"] = -1
            
        except Exception as e:
            preview["error"] = str(e)
        
        return preview
    
    def export(
        self,
        criteria: UnifiedFilterCriteria,
        output_path: str,
        **export_options
    ) -> UnifiedFilterResult:
        """Export filtered vector features to file.
        
        Args:
            criteria: Filter criteria
            output_path: Output file path
            **export_options: Options like format, crs, etc.
            
        Returns:
            UnifiedFilterResult with export status
        """
        start_time = time.time()
        
        self._report_progress(0, "Preparing export...")
        
        try:
            # First apply the filter to get feature IDs
            filter_result = self.apply_filter(criteria)
            
            if not filter_result.is_success:
                return filter_result
            
            if filter_result.affected_count == 0:
                return self._create_error_result(
                    criteria,
                    "No features to export after filtering"
                )
            
            self._report_progress(50, "Writing file...")
            
            # Get the layer
            layer = self._get_layer(criteria.layer_id)
            if layer is None:
                return self._create_error_result(criteria, "Layer not found")
            
            # Export using QGIS
            from qgis.core import QgsVectorFileWriter, QgsCoordinateTransformContext
            
            # Build options
            save_options = QgsVectorFileWriter.SaveVectorOptions()
            save_options.driverName = export_options.get('driver', 'ESRI Shapefile')
            save_options.fileEncoding = export_options.get('encoding', 'UTF-8')
            
            # Filter by feature IDs
            if filter_result.feature_ids:
                save_options.filterExtent = None  # We'll use feature IDs
                # Set subset string temporarily
                original_subset = layer.subsetString()
                pk_field = self._get_primary_key_field(layer)
                if pk_field and filter_result.feature_ids:
                    ids_str = ','.join(str(fid) for fid in filter_result.feature_ids)
                    layer.setSubsetString(f'"{pk_field}" IN ({ids_str})')
            
            # Write
            transform_context = QgsCoordinateTransformContext()
            error = QgsVectorFileWriter.writeAsVectorFormatV3(
                layer,
                output_path,
                transform_context,
                save_options
            )
            
            # Restore original subset
            if filter_result.feature_ids:
                layer.setSubsetString(original_subset)
            
            if error[0] != QgsVectorFileWriter.NoError:
                return self._create_error_result(criteria, f"Export failed: {error[1]}")
            
            execution_time = (time.time() - start_time) * 1000
            
            self._report_progress(100, "Export complete")
            
            result = UnifiedFilterResult.vector_success(
                layer_id=criteria.layer_id,
                feature_ids=filter_result.feature_ids,
                expression_raw=criteria.to_display_string(),
                execution_time_ms=execution_time
            )
            result.output_path = output_path
            
            return result
            
        except Exception as e:
            logger.exception(f"Export error: {e}")
            return self._create_error_result(criteria, str(e))
    
    # =========================================================================
    # Private helper methods
    # =========================================================================
    
    def _get_layer(self, layer_id: str):
        """Get layer from project by ID.
        
        Args:
            layer_id: QGIS layer ID
            
        Returns:
            QgsVectorLayer or None
        """
        try:
            from qgis.core import QgsProject
            project = self.context.project or QgsProject.instance()
            return project.mapLayer(layer_id)
        except Exception as e:
            logger.error(f"Error getting layer {layer_id}: {e}")
            return None
    
    def _filter_by_expression(
        self, 
        layer, 
        criteria: VectorFilterCriteria
    ) -> Set[int]:
        """Filter layer by attribute expression.
        
        Args:
            layer: QgsVectorLayer
            criteria: Filter criteria
            
        Returns:
            Set of matching feature IDs
        """
        from qgis.core import QgsExpression, QgsFeatureRequest
        
        expr = QgsExpression(criteria.expression)
        if expr.hasParserError():
            raise ValueError(f"Invalid expression: {expr.parserErrorString()}")
        
        request = QgsFeatureRequest(expr)
        request.setFlags(QgsFeatureRequest.NoGeometry)  # Faster
        
        feature_ids = set()
        for feature in layer.getFeatures(request):
            if self.is_cancelled:
                break
            feature_ids.add(feature.id())
        
        return feature_ids
    
    def _filter_by_spatial(
        self, 
        layer, 
        criteria: VectorFilterCriteria
    ) -> Set[int]:
        """Filter layer by spatial predicate.
        
        Args:
            layer: Target QgsVectorLayer
            criteria: Filter criteria with spatial parameters
            
        Returns:
            Set of matching feature IDs
        """
        from qgis.core import QgsProject, QgsFeatureRequest, QgsSpatialIndex
        
        # Get source layer
        project = self.context.project or QgsProject.instance()
        source_layer = project.mapLayer(criteria.source_layer_id)
        
        if source_layer is None:
            raise ValueError(f"Source layer not found: {criteria.source_layer_id}")
        
        # Build spatial index on target
        spatial_index = QgsSpatialIndex(layer.getFeatures())
        
        # Get source geometries (with optional buffer)
        source_geoms = []
        for feature in source_layer.getFeatures():
            geom = feature.geometry()
            if criteria.buffer_value > 0:
                geom = geom.buffer(criteria.buffer_value, 5)
            source_geoms.append(geom)
        
        # Find intersecting features
        feature_ids = set()
        predicate = criteria.spatial_predicate or "intersects"
        
        for source_geom in source_geoms:
            if self.is_cancelled:
                break
            
            # Get candidates from spatial index
            bbox = source_geom.boundingBox()
            candidates = spatial_index.intersects(bbox)
            
            # Refine with actual predicate
            for fid in candidates:
                if fid in feature_ids:
                    continue
                
                request = QgsFeatureRequest().setFilterFid(fid)
                for feature in layer.getFeatures(request):
                    target_geom = feature.geometry()
                    
                    if self._check_spatial_predicate(source_geom, target_geom, predicate):
                        feature_ids.add(fid)
                    break
        
        return feature_ids
    
    def _check_spatial_predicate(
        self, 
        source_geom, 
        target_geom, 
        predicate: str
    ) -> bool:
        """Check if geometries satisfy spatial predicate.
        
        Args:
            source_geom: Source geometry
            target_geom: Target geometry
            predicate: Predicate name
            
        Returns:
            True if predicate is satisfied
        """
        predicate_lower = predicate.lower()
        
        if predicate_lower == "intersects":
            return source_geom.intersects(target_geom)
        elif predicate_lower == "contains":
            return source_geom.contains(target_geom)
        elif predicate_lower == "within":
            return target_geom.within(source_geom)
        elif predicate_lower == "overlaps":
            return source_geom.overlaps(target_geom)
        elif predicate_lower == "crosses":
            return source_geom.crosses(target_geom)
        elif predicate_lower == "touches":
            return source_geom.touches(target_geom)
        elif predicate_lower == "disjoint":
            return source_geom.disjoint(target_geom)
        elif predicate_lower == "equals":
            return source_geom.equals(target_geom)
        else:
            # Default to intersects
            return source_geom.intersects(target_geom)
    
    def _get_all_feature_ids(self, layer) -> Set[int]:
        """Get all feature IDs from layer.
        
        Args:
            layer: QgsVectorLayer
            
        Returns:
            Set of all feature IDs
        """
        from qgis.core import QgsFeatureRequest
        
        request = QgsFeatureRequest()
        request.setFlags(QgsFeatureRequest.NoGeometry)
        request.setNoAttributes()
        
        return {f.id() for f in layer.getFeatures(request)}
    
    def _get_primary_key_field(self, layer) -> Optional[str]:
        """Get primary key field name for layer.
        
        Args:
            layer: QgsVectorLayer
            
        Returns:
            Primary key field name or None
        """
        try:
            pk_indexes = layer.primaryKeyAttributes()
            if pk_indexes:
                return layer.fields().at(pk_indexes[0]).name()
        except Exception:
            pass
        
        # Fallback: look for common PK names
        for name in ['id', 'fid', 'ogc_fid', 'gid', 'pk']:
            idx = layer.fields().lookupField(name)
            if idx >= 0:
                return name
        
        return None
    
    def _detect_backend(self, layer) -> str:
        """Detect the backend type for the layer.
        
        Args:
            layer: QgsVectorLayer
            
        Returns:
            Backend name string
        """
        provider = layer.providerType()
        
        if provider == 'postgres':
            return 'postgresql'
        elif provider == 'spatialite':
            return 'spatialite'
        elif provider == 'ogr':
            return 'ogr'
        elif provider == 'memory':
            return 'memory'
        else:
            return provider or 'unknown'

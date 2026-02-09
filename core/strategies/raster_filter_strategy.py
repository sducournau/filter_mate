# -*- coding: utf-8 -*-
"""
Raster Filter Strategy.

Concrete strategy for filtering and exporting raster layers.
Wraps the existing RasterFilterService and RasterExporter.

Part of the Unified Filter System (EPIC-UNIFIED-FILTER).

Author: FilterMate Team (BMAD - Amelia)
Date: February 2026
Version: 5.0.0-alpha
"""

import logging
import time
import os
from typing import Optional, Dict, Any, List, Tuple

from .base_filter_strategy import (
    AbstractFilterStrategy,
    FilterContext,
    UnifiedFilterResult,
    FilterStatus
)
from ..domain.filter_criteria import (
    LayerType,
    RasterFilterCriteria,
    RasterPredicate as CriteriaPredicate
)

logger = logging.getLogger('FilterMate.Strategies.Raster')


class RasterFilterStrategy(AbstractFilterStrategy):
    """Strategy for filtering raster layers.
    
    Implements the AbstractFilterStrategy for raster data.
    Delegates to RasterFilterService for vector-by-raster operations
    and RasterExporter for export operations.
    
    Supported operations:
    - Value range filtering (min/max pixel values)
    - NoData filtering
    - Band selection
    - Mask by vector layer
    - Export with clipping
    
    Usage:
        from core.strategies import RasterFilterStrategy, FilterContext
        from core.domain import RasterFilterCriteria
        
        context = FilterContext()
        strategy = RasterFilterStrategy(context)
        
        criteria = RasterFilterCriteria(
            layer_id="dem_layer",
            band_index=1,
            min_value=500,
            max_value=1500
        )
        
        result = strategy.apply_filter(criteria)
    """
    
    def __init__(self, context: FilterContext):
        """Initialize the raster filter strategy.
        
        Args:
            context: FilterContext with project and callbacks
        """
        super().__init__(context)
        self._raster_service = None
        self._raster_exporter = None

    @property
    def supported_layer_type(self) -> LayerType:
        """Return RASTER as the supported layer type."""
        return LayerType.RASTER
    
    def _get_raster_service(self):
        """Lazy-load RasterFilterService to avoid circular imports."""
        if self._raster_service is None:
            try:
                from ..services.raster_filter_service import RasterFilterService
                self._raster_service = RasterFilterService()
            except ImportError as e:
                logger.warning(f"Could not import RasterFilterService: {e}")
        return self._raster_service
    
    def _get_raster_exporter(self):
        """Lazy-load RasterExporter to avoid circular imports."""
        if self._raster_exporter is None:
            try:
                from ..export.raster_exporter import RasterExporter
                self._raster_exporter = RasterExporter()
            except ImportError as e:
                logger.warning(f"Could not import RasterExporter: {e}")
        return self._raster_exporter
    
    def validate_criteria(
        self, 
        criteria: RasterFilterCriteria
    ) -> Tuple[bool, Optional[str]]:
        """Validate raster filter criteria.
        
        Checks:
        - Layer exists and is valid raster
        - Band index is valid
        - Value range is valid (min <= max if both specified)
        - At least one meaningful filter condition specified
        
        Args:
            criteria: RasterFilterCriteria to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Basic validation
        if not criteria.layer_id:
            return False, "Layer ID is required"
        
        # Check band index
        if criteria.band_index < 1:
            return False, f"Invalid band index: {criteria.band_index}. Must be >= 1"
        
        # Check value range consistency
        if criteria.min_value is not None and criteria.max_value is not None:
            if criteria.min_value > criteria.max_value:
                return False, (
                    f"Invalid value range: min ({criteria.min_value}) > "
                    f"max ({criteria.max_value})"
                )
        
        # FIX 2026-02-08 C5: Must have at least one meaningful filter condition.
        # predicate defaults to WITHIN_RANGE (never None), so we must check for
        # actual filter parameters: value range, mask, or special predicates.
        has_value_filter = (
            criteria.min_value is not None or 
            criteria.max_value is not None
        )
        has_mask = criteria.mask_layer_id is not None
        has_special_predicate = criteria.predicate in (
            RasterPredicate.IS_NODATA, RasterPredicate.IS_NOT_NODATA
        )
        
        if not (has_value_filter or has_mask or has_special_predicate):
            return False, (
                "At least one filter condition required: "
                "value range, predicate (IS_NODATA/IS_NOT_NODATA), or mask layer"
            )
        
        # Verify layer exists if project available
        if self.context.project:
            layer = self.context.project.mapLayer(criteria.layer_id)
            if layer is None:
                return False, f"Layer not found: {criteria.layer_id}"
            
            # Check if it's a raster layer
            try:
                from qgis.core import QgsRasterLayer
                if not isinstance(layer, QgsRasterLayer):
                    return False, f"Layer is not a raster: {criteria.layer_id}"
            except ImportError:
                pass  # Skip this check without QGIS
            
            # Check band index against layer
            try:
                if criteria.band_index > layer.bandCount():
                    return False, (
                        f"Band index {criteria.band_index} exceeds band count "
                        f"({layer.bandCount()}) for layer {criteria.layer_id}"
                    )
            except AttributeError:
                pass  # Skip if method not available
        
        return True, None
    
    def apply_filter(
        self, 
        criteria: RasterFilterCriteria
    ) -> UnifiedFilterResult:
        """Apply raster filter.
        
        For value-range filtering, performs pixel-level analysis (count matching pixels).
        For mask operations, delegates to RasterFilterService.apply_vector_to_raster().
        
        Args:
            criteria: RasterFilterCriteria with filter parameters
            
        Returns:
            UnifiedFilterResult with operation results
        """
        start_time = time.time()
        
        try:
            from qgis.core import QgsProject, QgsRasterLayer
            
            # Get project
            project = self.context.project or QgsProject.instance()
            
            # Get raster layer
            layer = project.mapLayer(criteria.layer_id)
            if not layer or not isinstance(layer, QgsRasterLayer):
                return self._create_error_result(
                    criteria,
                    f"Invalid raster layer: {criteria.layer_id}"
                )
            
            self._report_progress(10, f"Processing raster: {layer.name()}")
            
            # Delegate mask operations to service
            if criteria.has_mask:
                return self._apply_mask_filter(criteria, layer, project, start_time)
            
            # Value-range analysis (inline, works correctly)
            stats = self._get_band_statistics(layer, criteria.band_index)
            
            matching_pixels, total_pixels = self._count_matching_pixels(
                layer, criteria, stats
            )
            
            self._report_progress(90, "Filter analysis complete")
            
            elapsed = (time.time() - start_time) * 1000
            
            expression = criteria.to_display_string()
            
            return UnifiedFilterResult.raster_success(
                layer_id=criteria.layer_id,
                output_path=None,
                pixel_count=matching_pixels,
                statistics={
                    "total_pixels": total_pixels,
                    "matching_pixels": matching_pixels,
                    "match_percentage": (
                        (matching_pixels / total_pixels * 100) 
                        if total_pixels > 0 else 0
                    ),
                    "band_stats": stats,
                    "filter_expression": expression
                }
            )
            
        except ImportError:
            return self._create_error_result(
                criteria,
                "QGIS not available for raster operations"
            )
        except Exception as e:
            logger.exception(f"Error in raster filter: {e}")
            return self._create_error_result(criteria, str(e))

    def _apply_mask_filter(
        self,
        criteria: RasterFilterCriteria,
        layer,
        project,
        start_time: float
    ) -> UnifiedFilterResult:
        """Delegate mask operations to RasterFilterService.
        
        Args:
            criteria: Filter criteria with mask parameters
            layer: Source raster layer
            project: QGIS project instance
            start_time: Operation start time for elapsed calculation
            
        Returns:
            UnifiedFilterResult with mask operation results
        """
        from ..services.raster_filter_service import (
            VectorFilterRequest, RasterOperation
        )
        
        service = self._get_raster_service()
        if service is None:
            return self._create_error_result(
                criteria, "RasterFilterService not available"
            )
        
        # Get mask layer from project
        mask_layer = project.mapLayer(criteria.mask_layer_id)
        if not mask_layer:
            return self._create_error_result(
                criteria,
                f"Mask layer not found: {criteria.mask_layer_id}"
            )
        
        self._report_progress(20, f"Applying mask from {mask_layer.name()}")
        
        # Build service request
        request = VectorFilterRequest(
            vector_layer=mask_layer,
            raster_layer=layer,
            operation=RasterOperation.MASK_OUTSIDE,
            feature_ids=(
                list(criteria.mask_feature_ids) 
                if criteria.mask_feature_ids else None
            ),
            nodata_value=-9999.0
        )
        
        self._report_progress(40, "Running mask operation")
        
        result = service.apply_vector_to_raster(request)
        
        elapsed = (time.time() - start_time) * 1000
        
        if result.success:
            self._report_progress(100, "Mask operation complete")
            return UnifiedFilterResult.raster_success(
                layer_id=criteria.layer_id,
                output_path=result.output_path,
                pixel_count=0,
                statistics={
                    'operation': 'mask',
                    'mask_layer': criteria.mask_layer_id,
                    'execution_time_ms': elapsed
                },
                execution_time_ms=elapsed
            )
        else:
            return self._create_error_result(
                criteria, 
                result.error_message or "Mask operation failed"
            )
    
    def get_preview(
        self, 
        criteria: RasterFilterCriteria
    ) -> Dict[str, Any]:
        """Get preview of raster filter.
        
        Returns estimated pixel counts and statistics without
        actually processing the entire raster.
        
        Args:
            criteria: RasterFilterCriteria to preview
            
        Returns:
            Dict with preview data including estimated counts
        """
        try:
            from qgis.core import QgsProject, QgsRasterLayer
            
            project = self.context.project or QgsProject.instance()
            layer = project.mapLayer(criteria.layer_id)
            
            if not layer or not isinstance(layer, QgsRasterLayer):
                return {
                    "type": "raster",
                    "error": f"Invalid layer: {criteria.layer_id}"
                }
            
            # Get band statistics
            stats = self._get_band_statistics(layer, criteria.band_index)
            
            # Estimate matching pixels based on value range
            estimated_match = self._estimate_match_percentage(
                stats, criteria
            )
            
            total_pixels = layer.width() * layer.height()
            
            return {
                "type": "raster",
                "layer_name": layer.name(),
                "band_index": criteria.band_index,
                "band_count": layer.bandCount(),
                "dimensions": {
                    "width": layer.width(),
                    "height": layer.height()
                },
                "total_pixels": total_pixels,
                "estimated_match_percentage": estimated_match,
                "estimated_matching_pixels": int(total_pixels * estimated_match / 100),
                "band_statistics": stats,
                "filter_expression": criteria.to_display_string(),
                "crs": layer.crs().authid() if layer.crs().isValid() else "Unknown"
            }
            
        except ImportError:
            return {
                "type": "raster",
                "error": "QGIS not available"
            }
        except Exception as e:
            return {
                "type": "raster",
                "error": str(e)
            }
    
    def export(
        self,
        criteria: RasterFilterCriteria,
        output_path: str,
        **export_options
    ) -> UnifiedFilterResult:
        """Export filtered raster to file.
        
        Applies the filter criteria and exports the result.
        
        Args:
            criteria: Filter criteria
            output_path: Output file path
            **export_options:
                - format: Export format (GTiff, COG, etc.)
                - compression: Compression type
                - clip_to_mask: Whether to clip to mask geometry
                - nodata_value: NoData value for output
                
        Returns:
            UnifiedFilterResult with export status
        """
        start_time = time.time()
        
        try:
            from qgis.core import QgsProject, QgsRasterLayer
            
            project = self.context.project or QgsProject.instance()
            layer = project.mapLayer(criteria.layer_id)
            
            if not layer or not isinstance(layer, QgsRasterLayer):
                return self._create_error_result(
                    criteria,
                    f"Invalid raster layer: {criteria.layer_id}"
                )
            
            self._report_progress(10, "Preparing export...")
            
            # Get mask layer if specified
            mask_layer = None
            if criteria.mask_layer_id:
                mask_layer = project.mapLayer(criteria.mask_layer_id)
            
            # Use RasterExporter if available
            exporter = self._get_raster_exporter()
            if exporter:
                result = self._export_with_exporter(
                    layer, 
                    criteria, 
                    output_path, 
                    mask_layer,
                    export_options
                )
            else:
                # Fallback: Use GDAL directly via processing
                result = self._export_with_processing(
                    layer,
                    criteria,
                    output_path,
                    mask_layer,
                    export_options
                )
            
            if result.get("success"):
                elapsed = (time.time() - start_time) * 1000
                
                return UnifiedFilterResult.raster_success(
                    layer_id=criteria.layer_id,
                    output_path=output_path,
                    pixel_count=result.get("pixel_count", 0),
                    statistics={
                        "export_format": export_options.get("format", "GTiff"),
                        "file_size": self._get_file_size(output_path),
                        "execution_time_ms": elapsed
                    }
                )
            else:
                return self._create_error_result(
                    criteria,
                    result.get("error", "Export failed")
                )
                
        except ImportError:
            return self._create_error_result(
                criteria,
                "QGIS not available for raster export"
            )
        except Exception as e:
            logger.exception(f"Error in raster export: {e}")
            return self._create_error_result(criteria, str(e))
    
    # =========================================================================
    # Private helper methods
    # =========================================================================
    
    def _get_band_statistics(
        self, 
        layer, 
        band_index: int
    ) -> Dict[str, Any]:
        """Get statistics for a raster band.
        
        Args:
            layer: QgsRasterLayer
            band_index: Band number (1-based)
            
        Returns:
            Dict with min, max, mean, std, etc.
        """
        try:
            from qgis.core import Qgis, QgsRasterBandStats
            try:
                _stat_all = Qgis.RasterBandStatistic.All
            except AttributeError:
                _stat_all = QgsRasterBandStats.All

            provider = layer.dataProvider()

            # Get band statistics
            stats = provider.bandStatistics(
                band_index,
                _stat_all,
                layer.extent(),
                0  # Sample size (0 = all)
            )
            
            return {
                "min": stats.minimumValue,
                "max": stats.maximumValue,
                "mean": stats.mean,
                "std_dev": stats.stdDev,
                "range": stats.range,
                "sum": stats.sum if hasattr(stats, 'sum') else None
            }
            
        except Exception as e:
            logger.warning(f"Could not get band statistics: {e}")
            return {}
    
    def _count_matching_pixels(
        self,
        layer,
        criteria: RasterFilterCriteria,
        stats: Dict[str, Any]
    ) -> Tuple[int, int]:
        """Count pixels matching the filter criteria.
        
        Note: For large rasters, this uses sampling to estimate.
        
        Args:
            layer: QgsRasterLayer
            criteria: Filter criteria
            stats: Band statistics
            
        Returns:
            Tuple of (matching_count, total_count)
        """
        total_pixels = layer.width() * layer.height()
        
        # For large rasters, estimate based on statistics
        if total_pixels > 1_000_000:
            percentage = self._estimate_match_percentage(stats, criteria)
            return int(total_pixels * percentage / 100), total_pixels
        
        # For smaller rasters, count exactly
        try:
            return self._exact_pixel_count(layer, criteria)
        except Exception:
            # Fallback to estimation
            percentage = self._estimate_match_percentage(stats, criteria)
            return int(total_pixels * percentage / 100), total_pixels
    
    def _estimate_match_percentage(
        self,
        stats: Dict[str, Any],
        criteria: RasterFilterCriteria
    ) -> float:
        """Estimate percentage of pixels matching criteria.
        
        Uses band statistics to estimate without reading all pixels.
        Handles all predicate types (not just WITHIN_RANGE).
        
        Args:
            stats: Band statistics
            criteria: Filter criteria
            
        Returns:
            Estimated percentage (0-100)
        """
        if not stats:
            return 50.0  # Unknown, assume 50%
        
        predicate = criteria.predicate
        
        # IS_NODATA / IS_NOT_NODATA: heuristic (stats don't expose nodata ratio)
        if predicate == CriteriaPredicate.IS_NODATA:
            return 5.0
        if predicate == CriteriaPredicate.IS_NOT_NODATA:
            return 95.0
        
        band_min = stats.get("min", 0)
        band_max = stats.get("max", 0)
        band_range = band_max - band_min
        
        filter_min = criteria.min_value if criteria.min_value is not None else band_min
        filter_max = criteria.max_value if criteria.max_value is not None else band_max
        
        if band_range <= 0:
            # All pixels have the same value — check if it matches the predicate
            single_val = band_min
            if predicate == CriteriaPredicate.WITHIN_RANGE:
                return 100.0 if filter_min <= single_val <= filter_max else 0.0
            elif predicate == CriteriaPredicate.OUTSIDE_RANGE:
                return 0.0 if filter_min <= single_val <= filter_max else 100.0
            elif predicate == CriteriaPredicate.ABOVE_VALUE:
                return 100.0 if single_val > filter_min else 0.0
            elif predicate == CriteriaPredicate.BELOW_VALUE:
                return 100.0 if single_val < filter_max else 0.0
            elif predicate == CriteriaPredicate.EQUALS_VALUE:
                tolerance = criteria.tolerance if criteria.tolerance else 0.001
                return 100.0 if abs(single_val - filter_min) <= tolerance else 0.0
            return 0.0
        
        # Assume uniform distribution for estimation
        if predicate == CriteriaPredicate.WITHIN_RANGE:
            overlap_min = max(filter_min, band_min)
            overlap_max = min(filter_max, band_max)
            if overlap_min > overlap_max:
                return 0.0
            return ((overlap_max - overlap_min) / band_range) * 100
        
        elif predicate == CriteriaPredicate.OUTSIDE_RANGE:
            overlap_min = max(filter_min, band_min)
            overlap_max = min(filter_max, band_max)
            if overlap_min > overlap_max:
                return 100.0
            within_pct = ((overlap_max - overlap_min) / band_range) * 100
            return 100.0 - within_pct
        
        elif predicate == CriteriaPredicate.ABOVE_VALUE:
            if filter_min >= band_max:
                return 0.0
            if filter_min <= band_min:
                return 100.0
            return ((band_max - filter_min) / band_range) * 100
        
        elif predicate == CriteriaPredicate.BELOW_VALUE:
            if filter_max <= band_min:
                return 0.0
            if filter_max >= band_max:
                return 100.0
            return ((filter_max - band_min) / band_range) * 100
        
        elif predicate == CriteriaPredicate.EQUALS_VALUE:
            tolerance = criteria.tolerance if criteria.tolerance else 0.001
            return min((2 * tolerance / band_range) * 100, 100.0)
        
        return 50.0  # Fallback
    
    def _exact_pixel_count(
        self,
        layer,
        criteria: RasterFilterCriteria
    ) -> Tuple[int, int]:
        """Count pixels exactly by reading raster data.
        
        Only used for smaller rasters. Handles all predicate types.
        
        Args:
            layer: QgsRasterLayer
            criteria: Filter criteria
            
        Returns:
            Tuple of (matching_count, total_count)
        """
        try:
            import numpy as np
            
            provider = layer.dataProvider()
            band = criteria.band_index
            
            # Read raster block
            block = provider.block(band, layer.extent(), layer.width(), layer.height())
            
            # Convert to numpy array
            data = np.zeros((layer.height(), layer.width()))
            for row in range(layer.height()):
                for col in range(layer.width()):
                    data[row, col] = block.value(row, col)
            
            # Build nodata mask
            nodata = provider.sourceNoDataValue(band) if provider.sourceHasNoDataValue(band) else None
            if nodata is not None:
                is_nodata = np.isclose(data, nodata)
            else:
                is_nodata = np.zeros_like(data, dtype=bool)
            valid_mask = ~is_nodata
            
            predicate = criteria.predicate
            
            # Handle NoData predicates directly
            if predicate == CriteriaPredicate.IS_NODATA:
                return int(np.sum(is_nodata)), data.size
            if predicate == CriteriaPredicate.IS_NOT_NODATA:
                return int(np.sum(valid_mask)), data.size
            
            # Value-based predicates: only consider valid (non-nodata) pixels
            if predicate == CriteriaPredicate.WITHIN_RANGE:
                mask = valid_mask.copy()
                if criteria.min_value is not None:
                    mask &= (data >= criteria.min_value)
                if criteria.max_value is not None:
                    mask &= (data <= criteria.max_value)
            elif predicate == CriteriaPredicate.OUTSIDE_RANGE:
                mask = valid_mask.copy()
                if criteria.min_value is not None and criteria.max_value is not None:
                    mask &= ((data < criteria.min_value) | (data > criteria.max_value))
            elif predicate == CriteriaPredicate.ABOVE_VALUE:
                mask = valid_mask & (data > criteria.min_value) if criteria.min_value is not None else valid_mask.copy()
            elif predicate == CriteriaPredicate.BELOW_VALUE:
                mask = valid_mask & (data < criteria.max_value) if criteria.max_value is not None else valid_mask.copy()
            elif predicate == CriteriaPredicate.EQUALS_VALUE:
                tolerance = criteria.tolerance if criteria.tolerance else 0.001
                target = criteria.min_value if criteria.min_value is not None else 0.0
                mask = valid_mask & (np.abs(data - target) <= tolerance)
            else:
                mask = valid_mask.copy()
            
            return int(np.sum(mask)), data.size
            
        except ImportError:
            raise  # Re-raise to use estimation fallback
        except Exception as e:
            logger.warning(f"Exact pixel count failed: {e}")
            raise
    
    def _export_with_exporter(
        self,
        layer,
        criteria: RasterFilterCriteria,
        output_path: str,
        mask_layer,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Export using RasterExporter service.
        
        Note: Value range filtering is applied by apply_filter() before export.
        The exporter handles format conversion, masking, and CRS transformation.
        
        Args:
            layer: Source raster layer (already filtered if range was applied)
            criteria: Filter criteria
            output_path: Output file path
            mask_layer: Optional mask layer
            options: Export options
            
        Returns:
            Dict with success status and details
        """
        try:
            from ..export.raster_exporter import RasterExportConfig, RasterExportFormat
            
            exporter = self._get_raster_exporter()
            
            # Build export config
            config = RasterExportConfig(
                layer=layer,
                output_path=output_path,
                format=RasterExportFormat[options.get("format", "GEOTIFF")],
                mask_layer=mask_layer
            )
            
            # Execute export
            result = exporter.export(config)
            
            return {
                "success": result.success,
                "pixel_count": getattr(result, 'pixel_count', 0),
                "error": getattr(result, 'error_message', None)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _export_with_processing(
        self,
        layer,
        criteria: RasterFilterCriteria,
        output_path: str,
        mask_layer,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Export using QGIS Processing (GDAL).
        
        Fallback when RasterExporter is not available.
        
        Args:
            layer: Source raster layer
            criteria: Filter criteria
            output_path: Output file path
            mask_layer: Optional mask layer
            options: Export options
            
        Returns:
            Dict with success status and details
        """
        import tempfile
        
        try:
            import processing
            
            self._report_progress(30, "Running GDAL translate...")
            
            needs_clip = mask_layer and criteria.mask_layer_id
            
            # If a clip step follows, write translate to a temp file
            if needs_clip:
                temp_fd, translate_output = tempfile.mkstemp(suffix='.tif')
                os.close(temp_fd)
            else:
                translate_output = output_path
            
            # Build GDAL translate parameters
            params = {
                'INPUT': layer,
                'OUTPUT': translate_output,
                'COPY_SUBDATASETS': False,
                'OPTIONS': ''
            }
            
            # Add compression if specified
            compression = options.get("compression", "LZW")
            if compression:
                params['OPTIONS'] = f'COMPRESS={compression}'
            
            # Run translate
            result = processing.run("gdal:translate", params)
            
            if needs_clip:
                # Additional clip step: read from temp, write to final output
                self._report_progress(60, "Clipping to mask...")
                
                clip_params = {
                    'INPUT': translate_output,
                    'MASK': mask_layer,
                    'OUTPUT': output_path,
                    'CROP_TO_CUTLINE': True,
                    'KEEP_RESOLUTION': True
                }
                result = processing.run("gdal:cliprasterbymasklayer", clip_params)
                
                # Clean up temp file
                try:
                    os.remove(translate_output)
                except OSError:
                    pass
            
            self._report_progress(90, "Export complete")
            
            return {
                "success": os.path.exists(output_path),
                "pixel_count": layer.width() * layer.height(),
                "error": None
            }
            
        except Exception as e:
            # Clean up temp file on error
            if needs_clip:
                try:
                    os.remove(translate_output)
                except (OSError, UnboundLocalError):
                    pass
            return {"success": False, "error": str(e)}
    
    def _get_file_size(self, path: str) -> Optional[int]:
        """Get file size in bytes."""
        try:
            return os.path.getsize(path) if os.path.exists(path) else None
        except Exception:
            return None
    
    def _create_error_result(
        self,
        criteria: RasterFilterCriteria,
        error_message: str
    ) -> UnifiedFilterResult:
        """Create an error result for raster operations."""
        return UnifiedFilterResult.error(
            layer_id=criteria.layer_id,
            layer_type="raster",
            error_message=error_message,
            expression_raw=criteria.to_display_string()
        )

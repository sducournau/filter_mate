# -*- coding: utf-8 -*-
"""
FilterMate - Raster Filter Service

Service for bidirectional filtering between raster and vector layers:
- Raster → Vector: Filter vector features based on raster pixel values
- Vector → Raster: Clip/Mask raster using vector geometries

Author: FilterMate Team
Date: January 2026
"""
from typing import Optional, List, Dict, Tuple, Union, Any
from dataclasses import dataclass
from enum import Enum
import tempfile
import os

from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.core import (
    QgsVectorLayer,
    QgsRasterLayer,
    QgsProject,
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsPointXY,
    QgsRectangle,
    QgsCoordinateTransform,
    QgsCoordinateReferenceSystem,
    QgsProcessingFeedback,
    QgsRasterBandStats,
    Qgis
)

from infrastructure.logging import get_logger

logger = get_logger(__name__)


class RasterPredicate(Enum):
    """Predicates for raster value filtering."""
    WITHIN_RANGE = "within_range"       # min <= value <= max
    OUTSIDE_RANGE = "outside_range"     # value < min OR value > max
    ABOVE_VALUE = "above_value"         # value > min
    BELOW_VALUE = "below_value"         # value < max
    EQUALS_VALUE = "equals_value"       # value == min (tolerance)
    IS_NODATA = "is_nodata"             # value is NoData
    IS_NOT_NODATA = "is_not_nodata"     # value is not NoData


class SamplingMethod(Enum):
    """Methods for sampling raster values at vector features."""
    CENTROID = "centroid"               # Sample at feature centroid
    ALL_VERTICES = "all_vertices"       # Sample at all polygon vertices
    ZONAL_MEAN = "zonal_mean"           # Mean value within polygon
    ZONAL_MAX = "zonal_max"             # Max value within polygon
    ZONAL_MIN = "zonal_min"             # Min value within polygon
    ZONAL_MAJORITY = "zonal_majority"   # Most common value (for classified rasters)


class RasterOperation(Enum):
    """Operations for Vector → Raster filtering."""
    CLIP = "clip"                       # Clip raster to vector extent
    MASK_OUTSIDE = "mask_outside"       # Set pixels outside vector to NoData
    MASK_INSIDE = "mask_inside"         # Set pixels inside vector to NoData
    ZONAL_STATS = "zonal_stats"         # Calculate zonal statistics (no output raster)


@dataclass
class RasterFilterRequest:
    """Request for Raster → Vector filtering."""
    raster_layer: QgsRasterLayer
    vector_layer: QgsVectorLayer
    band_index: int = 1
    min_value: float = 0.0
    max_value: float = 0.0
    predicate: RasterPredicate = RasterPredicate.WITHIN_RANGE
    sampling_method: SamplingMethod = SamplingMethod.CENTROID
    tolerance: float = 0.001  # For EQUALS_VALUE predicate


@dataclass
class VectorFilterRequest:
    """Request for Vector → Raster operation."""
    vector_layer: QgsVectorLayer
    raster_layer: QgsRasterLayer
    operation: RasterOperation = RasterOperation.CLIP
    feature_ids: Optional[List[int]] = None  # If None, use all/selected features
    output_path: Optional[str] = None  # If None, create memory layer
    use_selected_only: bool = True
    nodata_value: float = -9999.0


@dataclass
class RasterFilterResult:
    """Result from raster filtering operation."""
    success: bool
    matching_feature_ids: List[int]
    total_features: int
    matching_count: int
    expression: str  # The filter expression applied
    error_message: str = ""
    execution_time_ms: float = 0.0
    statistics: Optional[Dict[str, Any]] = None


@dataclass
class VectorRasterResult:
    """Result from Vector → Raster operation."""
    success: bool
    output_layer: Optional[QgsRasterLayer]
    output_path: Optional[str]
    operation: RasterOperation
    error_message: str = ""
    execution_time_ms: float = 0.0
    statistics: Optional[Dict[str, Any]] = None


class RasterFilterService(QObject):
    """Service for bidirectional raster-vector filtering.
    
    Provides two main operations:
    1. filter_vector_by_raster(): Filter vector features based on raster values
    2. apply_vector_to_raster(): Clip/Mask raster using vector geometries
    
    Signals:
        progressChanged(int, str): Progress percentage and message
        operationCompleted(bool, str): Success status and message
    """
    
    progressChanged = pyqtSignal(int, str)
    operationCompleted = pyqtSignal(bool, str)
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._cancelled = False
    
    def cancel(self):
        """Cancel the current operation."""
        self._cancelled = True
    
    # =========================================================================
    # RASTER → VECTOR FILTERING
    # =========================================================================
    
    def filter_vector_by_raster(self, request: RasterFilterRequest) -> RasterFilterResult:
        """Filter vector features based on raster pixel values.
        
        For each vector feature, samples the raster value at the feature location
        (using the specified sampling method) and includes the feature if the
        sampled value matches the predicate.
        
        Args:
            request: RasterFilterRequest with layer, band, range, predicate
            
        Returns:
            RasterFilterResult with matching feature IDs and statistics
        """
        import time
        start_time = time.time()
        
        self._cancelled = False
        matching_ids = []
        
        try:
            raster = request.raster_layer
            vector = request.vector_layer
            
            if not raster or not raster.isValid():
                return RasterFilterResult(
                    success=False,
                    matching_feature_ids=[],
                    total_features=0,
                    matching_count=0,
                    expression="",
                    error_message="Invalid raster layer"
                )
            
            if not vector or not vector.isValid():
                return RasterFilterResult(
                    success=False,
                    matching_feature_ids=[],
                    total_features=0,
                    matching_count=0,
                    expression="",
                    error_message="Invalid vector layer"
                )
            
            # Setup coordinate transform if CRS differ
            transform = None
            if raster.crs() != vector.crs():
                transform = QgsCoordinateTransform(
                    vector.crs(),
                    raster.crs(),
                    QgsProject.instance()
                )
            
            # Get raster data provider
            provider = raster.dataProvider()
            band = request.band_index
            
            # Get NoData value for this band
            nodata_value = None
            if provider.sourceHasNoDataValue(band):
                nodata_value = provider.sourceNoDataValue(band)
            
            # Iterate features
            features = list(vector.getFeatures())
            total = len(features)
            
            for i, feature in enumerate(features):
                if self._cancelled:
                    break
                
                # Progress update
                if i % 100 == 0:
                    pct = int((i / total) * 100) if total > 0 else 0
                    self.progressChanged.emit(pct, f"Processing feature {i}/{total}")
                
                # Sample raster value
                value = self._sample_raster_value(
                    provider, 
                    feature, 
                    band, 
                    request.sampling_method,
                    transform
                )
                
                # Check predicate
                if self._check_predicate(
                    value, 
                    request.predicate, 
                    request.min_value, 
                    request.max_value,
                    nodata_value,
                    request.tolerance
                ):
                    matching_ids.append(feature.id())
            
            # Build expression for subset string
            expression = self._build_id_expression(matching_ids, vector)
            
            elapsed = (time.time() - start_time) * 1000
            
            result = RasterFilterResult(
                success=True,
                matching_feature_ids=matching_ids,
                total_features=total,
                matching_count=len(matching_ids),
                expression=expression,
                execution_time_ms=elapsed,
                statistics={
                    'sampling_method': request.sampling_method.value,
                    'predicate': request.predicate.value,
                    'range': (request.min_value, request.max_value)
                }
            )
            
            self.operationCompleted.emit(True, f"Filtered {len(matching_ids)}/{total} features")
            return result
            
        except Exception as e:
            logger.error(f"Raster→Vector filtering failed: {e}", exc_info=True)
            return RasterFilterResult(
                success=False,
                matching_feature_ids=[],
                total_features=0,
                matching_count=0,
                expression="",
                error_message=str(e)
            )
    
    def _sample_raster_value(
        self, 
        provider, 
        feature: QgsFeature, 
        band: int,
        method: SamplingMethod,
        transform: Optional[QgsCoordinateTransform]
    ) -> Optional[float]:
        """Sample raster value at feature location."""
        geom = feature.geometry()
        if geom.isEmpty():
            return None
        
        # Transform geometry if needed
        if transform:
            geom.transform(transform)
        
        if method == SamplingMethod.CENTROID:
            point = geom.centroid().asPoint()
            return self._sample_at_point(provider, point, band)
        
        elif method == SamplingMethod.ALL_VERTICES:
            # Return mean of all vertex samples
            values = []
            for vertex in self._get_vertices(geom):
                val = self._sample_at_point(provider, vertex, band)
                if val is not None:
                    values.append(val)
            return sum(values) / len(values) if values else None
        
        elif method in (SamplingMethod.ZONAL_MEAN, SamplingMethod.ZONAL_MAX, 
                        SamplingMethod.ZONAL_MIN, SamplingMethod.ZONAL_MAJORITY):
            return self._zonal_sample(provider, geom, band, method)
        
        return None
    
    def _sample_at_point(self, provider, point: QgsPointXY, band: int) -> Optional[float]:
        """Sample raster value at a single point."""
        try:
            result = provider.sample(point, band)
            if result[1]:  # is valid
                return result[0]
            return None
        except Exception:
            return None
    
    def _get_vertices(self, geom: QgsGeometry) -> List[QgsPointXY]:
        """Extract all vertices from geometry."""
        vertices = []
        for vertex in geom.vertices():
            vertices.append(QgsPointXY(vertex.x(), vertex.y()))
        return vertices
    
    def _zonal_sample(
        self, 
        provider, 
        geom: QgsGeometry, 
        band: int, 
        method: SamplingMethod
    ) -> Optional[float]:
        """Sample raster values within polygon extent (simplified)."""
        # For now, use a grid sampling approach
        # TODO: Use QGIS processing for proper zonal statistics
        bbox = geom.boundingBox()
        
        # Sample on a grid within the bounding box
        x_res = provider.extent().width() / provider.xSize()
        y_res = provider.extent().height() / provider.ySize()
        
        values = []
        x = bbox.xMinimum()
        while x < bbox.xMaximum():
            y = bbox.yMinimum()
            while y < bbox.yMaximum():
                point = QgsPointXY(x, y)
                if geom.contains(point):
                    val = self._sample_at_point(provider, point, band)
                    if val is not None:
                        values.append(val)
                y += y_res
            x += x_res
        
        if not values:
            return None
        
        if method == SamplingMethod.ZONAL_MEAN:
            return sum(values) / len(values)
        elif method == SamplingMethod.ZONAL_MAX:
            return max(values)
        elif method == SamplingMethod.ZONAL_MIN:
            return min(values)
        elif method == SamplingMethod.ZONAL_MAJORITY:
            # Return most common value
            from collections import Counter
            counter = Counter(round(v, 0) for v in values)
            return counter.most_common(1)[0][0] if counter else None
        
        return None
    
    def _check_predicate(
        self,
        value: Optional[float],
        predicate: RasterPredicate,
        min_val: float,
        max_val: float,
        nodata_value: Optional[float],
        tolerance: float
    ) -> bool:
        """Check if value matches the predicate."""
        # Handle None value
        if value is None:
            return predicate == RasterPredicate.IS_NODATA
        
        is_nodata = nodata_value is not None and abs(value - nodata_value) < 0.0001
        
        if predicate == RasterPredicate.IS_NODATA:
            return is_nodata
        
        if predicate == RasterPredicate.IS_NOT_NODATA:
            return not is_nodata
        
        if is_nodata:
            return False
        
        # At this point, value is guaranteed to be a valid float
        if predicate == RasterPredicate.WITHIN_RANGE:
            return min_val <= value <= max_val
        
        elif predicate == RasterPredicate.OUTSIDE_RANGE:
            return value < min_val or value > max_val
        
        elif predicate == RasterPredicate.ABOVE_VALUE:
            return value > min_val
        
        elif predicate == RasterPredicate.BELOW_VALUE:
            return value < max_val
        
        elif predicate == RasterPredicate.EQUALS_VALUE:
            return abs(value - min_val) <= tolerance
        
        return False
    
    def _build_id_expression(self, feature_ids: List[int], layer: QgsVectorLayer) -> str:
        """Build a filter expression from feature IDs."""
        if not feature_ids:
            return "1=0"  # Match nothing
        
        # Get primary key field name
        from infrastructure.utils.layer_utils import get_primary_key_name
        pk_field = get_primary_key_name(layer) or "$id"
        
        if len(feature_ids) <= 100:
            ids_str = ", ".join(str(fid) for fid in feature_ids)
            return f'"{pk_field}" IN ({ids_str})' if pk_field != "$id" else f"$id IN ({ids_str})"
        else:
            # For large sets, use a different approach
            return f"$id IN ({', '.join(str(fid) for fid in feature_ids)})"
    
    # =========================================================================
    # VECTOR → RASTER OPERATIONS
    # =========================================================================
    
    def apply_vector_to_raster(self, request: VectorFilterRequest) -> VectorRasterResult:
        """Apply vector geometry operation to raster (clip/mask).
        
        Uses QGIS processing algorithms to perform the operation.
        
        Args:
            request: VectorFilterRequest with layers, operation, output path
            
        Returns:
            VectorRasterResult with output layer and statistics
        """
        import time
        start_time = time.time()
        
        try:
            import processing
            
            vector = request.vector_layer
            raster = request.raster_layer
            
            if not vector or not vector.isValid():
                return VectorRasterResult(
                    success=False,
                    output_layer=None,
                    output_path=None,
                    operation=request.operation,
                    error_message="Invalid vector layer"
                )
            
            if not raster or not raster.isValid():
                return VectorRasterResult(
                    success=False,
                    output_layer=None,
                    output_path=None,
                    operation=request.operation,
                    error_message="Invalid raster layer"
                )
            
            # Determine output path
            output_path = request.output_path
            if not output_path:
                output_path = tempfile.mktemp(suffix='.tif')
            
            # Get features to use (selected or specified IDs)
            if request.feature_ids:
                # Create temporary layer with specified features
                mask_layer = self._create_temp_mask_layer(vector, request.feature_ids)
            elif request.use_selected_only and vector.selectedFeatureCount() > 0:
                # Use selected features
                mask_layer = self._create_temp_mask_layer(
                    vector, 
                    [f.id() for f in vector.selectedFeatures()]
                )
            else:
                mask_layer = vector
            
            # Execute operation
            if request.operation == RasterOperation.CLIP:
                result = self._clip_raster(raster, mask_layer, output_path)
            elif request.operation == RasterOperation.MASK_OUTSIDE:
                result = self._mask_raster(raster, mask_layer, output_path, 
                                          request.nodata_value, invert=False)
            elif request.operation == RasterOperation.MASK_INSIDE:
                result = self._mask_raster(raster, mask_layer, output_path,
                                          request.nodata_value, invert=True)
            elif request.operation == RasterOperation.ZONAL_STATS:
                result = self._compute_zonal_stats(raster, mask_layer)
                elapsed = (time.time() - start_time) * 1000
                return VectorRasterResult(
                    success=True,
                    output_layer=None,
                    output_path=None,
                    operation=request.operation,
                    execution_time_ms=elapsed,
                    statistics=result
                )
            else:
                return VectorRasterResult(
                    success=False,
                    output_layer=None,
                    output_path=None,
                    operation=request.operation,
                    error_message=f"Unknown operation: {request.operation}"
                )
            
            # Load result as layer
            if result and os.path.exists(result):
                output_layer = QgsRasterLayer(result, f"{raster.name()}_{request.operation.value}")
                if output_layer.isValid():
                    elapsed = (time.time() - start_time) * 1000
                    self.operationCompleted.emit(True, f"Created {request.operation.value} output")
                    return VectorRasterResult(
                        success=True,
                        output_layer=output_layer,
                        output_path=result,
                        operation=request.operation,
                        execution_time_ms=elapsed
                    )
            
            return VectorRasterResult(
                success=False,
                output_layer=None,
                output_path=None,
                operation=request.operation,
                error_message="Failed to create output raster"
            )
            
        except Exception as e:
            logger.error(f"Vector→Raster operation failed: {e}", exc_info=True)
            return VectorRasterResult(
                success=False,
                output_layer=None,
                output_path=None,
                operation=request.operation,
                error_message=str(e)
            )
    
    def _create_temp_mask_layer(
        self, 
        source_layer: QgsVectorLayer, 
        feature_ids: List[int]
    ) -> QgsVectorLayer:
        """Create a temporary layer with specified features."""
        # Create memory layer
        geom_type = source_layer.geometryType()
        geom_type_str = {0: "Point", 1: "LineString", 2: "Polygon"}.get(geom_type, "Polygon")
        crs = source_layer.crs().authid()
        
        temp_layer = QgsVectorLayer(
            f"{geom_type_str}?crs={crs}",
            "temp_mask",
            "memory"
        )
        
        # Copy features
        temp_layer.startEditing()
        for fid in feature_ids:
            feature = source_layer.getFeature(fid)
            if feature.isValid():
                temp_layer.addFeature(feature)
        temp_layer.commitChanges()
        
        return temp_layer
    
    def _clip_raster(
        self, 
        raster: QgsRasterLayer, 
        mask: QgsVectorLayer, 
        output_path: str
    ) -> Optional[str]:
        """Clip raster to vector extent using GDAL."""
        try:
            import processing
            
            params = {
                'INPUT': raster,
                'MASK': mask,
                'SOURCE_CRS': raster.crs(),
                'TARGET_CRS': raster.crs(),
                'NODATA': -9999,
                'ALPHA_BAND': False,
                'CROP_TO_CUTLINE': True,
                'KEEP_RESOLUTION': True,
                'OPTIONS': '',
                'DATA_TYPE': 0,  # Use input layer data type
                'OUTPUT': output_path
            }
            
            result = processing.run("gdal:cliprasterbymasklayer", params)
            return result.get('OUTPUT')
            
        except Exception as e:
            logger.error(f"Clip raster failed: {e}")
            return None
    
    def _mask_raster(
        self, 
        raster: QgsRasterLayer, 
        mask: QgsVectorLayer, 
        output_path: str,
        nodata_value: float,
        invert: bool = False
    ) -> Optional[str]:
        """Mask raster pixels using vector."""
        try:
            import processing
            
            params = {
                'INPUT': raster,
                'MASK': mask,
                'SOURCE_CRS': raster.crs(),
                'TARGET_CRS': raster.crs(),
                'NODATA': nodata_value,
                'ALPHA_BAND': False,
                'CROP_TO_CUTLINE': False,  # Don't crop for mask
                'KEEP_RESOLUTION': True,
                'SET_RESOLUTION': False,
                'OPTIONS': '',
                'DATA_TYPE': 0,
                'OUTPUT': output_path
            }
            
            # For MASK_INSIDE, we need to invert the mask
            if invert:
                # Create inverted mask using difference with extent
                # For now, use clip with inverted flag (if available)
                pass  # TODO: Implement proper inversion
            
            result = processing.run("gdal:cliprasterbymasklayer", params)
            return result.get('OUTPUT')
            
        except Exception as e:
            logger.error(f"Mask raster failed: {e}")
            return None
    
    def _compute_zonal_stats(
        self, 
        raster: QgsRasterLayer, 
        zones: QgsVectorLayer
    ) -> Dict[str, Any]:
        """Compute zonal statistics."""
        try:
            import processing
            
            params = {
                'INPUT': zones,
                'INPUT_RASTER': raster,
                'RASTER_BAND': 1,
                'COLUMN_PREFIX': 'zonal_',
                'STATISTICS': [0, 1, 2, 3, 4, 5, 6],  # count, sum, mean, median, stddev, min, max
                'OUTPUT': 'TEMPORARY_OUTPUT'
            }
            
            result = processing.run("native:zonalstatisticsfb", params)
            
            # Extract statistics from result layer
            output_layer = result.get('OUTPUT')
            if output_layer:
                stats = {
                    'features_processed': output_layer.featureCount(),
                    'stats_computed': True
                }
                return stats
            
            return {'error': 'No output'}
            
        except Exception as e:
            logger.error(f"Zonal stats failed: {e}")
            return {'error': str(e)}


# Singleton instance
_raster_filter_service: Optional[RasterFilterService] = None


def get_raster_filter_service() -> RasterFilterService:
    """Get the singleton RasterFilterService instance."""
    global _raster_filter_service
    if _raster_filter_service is None:
        _raster_filter_service = RasterFilterService()
    return _raster_filter_service

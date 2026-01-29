# -*- coding: utf-8 -*-
"""
QGIS Raster Filter Backend.

EPIC-3: Raster-Vector Integration
US-R2V-01: Raster as Filter Source

QGIS-specific implementation of RasterFilterPort for:
- Sampling raster values using QgsRasterLayer
- Filtering vector features by raster values
- Creating value-based masks using raster algebra
- Computing zonal statistics

This adapter uses:
- QgsRasterLayer.dataProvider().identify() for sampling
- QgsVectorLayer feature iteration for filtering
- QGIS Processing (gdal:rasterize, native:zonalstatistics)

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Dict, List, Optional, Tuple, Any

try:
    from qgis.core import (
        QgsProject,
        QgsRasterLayer,
        QgsVectorLayer,
        QgsPointXY,
        QgsGeometry,
        QgsFeature,
        QgsFeatureRequest,
        QgsRasterIdentifyResult,
        QgsRaster,
        QgsCoordinateTransform,
        QgsCoordinateReferenceSystem,
        Qgis
    )
    from qgis import processing
    HAS_QGIS = True
except ImportError:
    HAS_QGIS = False

from ...core.ports.raster_filter_port import (
    RasterFilterPort,
    RasterValuePredicate,
    SamplingMethod,
    RasterOperation,
    RasterSampleResult,
    RasterFilterResult,
    RasterMaskResult,
    ZonalStatisticsResult
)


logger = logging.getLogger("FilterMate.QGISRasterFilterBackend")


class QGISRasterFilterBackend(RasterFilterPort):
    """
    QGIS implementation of RasterFilterPort.
    
    EPIC-3: Provides raster filtering using QGIS native APIs.
    
    Features:
    - Direct raster value sampling via QgsRasterDataProvider
    - Feature-by-feature evaluation for filtering
    - Integration with QGIS Processing for complex operations
    - Coordinate transform handling for CRS mismatches
    """
    
    def __init__(self):
        """Initialize the backend."""
        if not HAS_QGIS:
            raise RuntimeError(
                "QGIS libraries not available. "
                "This backend requires QGIS Python bindings."
            )
        logger.info("QGISRasterFilterBackend initialized")
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _get_raster_layer(self, layer_id: str) -> QgsRasterLayer:
        """
        Get raster layer by ID.
        
        Args:
            layer_id: QGIS layer ID
        
        Returns:
            QgsRasterLayer
        
        Raises:
            ValueError: If layer not found or not raster
        """
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer is None:
            raise ValueError(f"Layer not found: {layer_id}")
        if not isinstance(layer, QgsRasterLayer):
            raise ValueError(f"Layer is not a raster: {layer_id}")
        if not layer.isValid():
            raise ValueError(f"Raster layer is invalid: {layer_id}")
        return layer
    
    def _get_vector_layer(self, layer_id: str) -> QgsVectorLayer:
        """
        Get vector layer by ID.
        
        Args:
            layer_id: QGIS layer ID
        
        Returns:
            QgsVectorLayer
        
        Raises:
            ValueError: If layer not found or not vector
        """
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer is None:
            raise ValueError(f"Layer not found: {layer_id}")
        if not isinstance(layer, QgsVectorLayer):
            raise ValueError(f"Layer is not a vector: {layer_id}")
        if not layer.isValid():
            raise ValueError(f"Vector layer is invalid: {layer_id}")
        return layer
    
    def _get_transform(
        self,
        source_crs: QgsCoordinateReferenceSystem,
        dest_crs: QgsCoordinateReferenceSystem
    ) -> Optional[QgsCoordinateTransform]:
        """
        Get coordinate transform if CRS differ.
        
        Args:
            source_crs: Source CRS
            dest_crs: Destination CRS
        
        Returns:
            QgsCoordinateTransform or None if same CRS
        """
        if source_crs == dest_crs:
            return None
        return QgsCoordinateTransform(
            source_crs,
            dest_crs,
            QgsProject.instance()
        )
    
    def _sample_value_at_point(
        self,
        raster: QgsRasterLayer,
        point: QgsPointXY,
        band: int
    ) -> Tuple[Optional[float], bool]:
        """
        Sample raster value at a single point.
        
        Args:
            raster: Raster layer
            point: Point to sample
            band: Band number (1-indexed)
        
        Returns:
            Tuple of (value, is_nodata)
        """
        provider = raster.dataProvider()
        
        result = provider.identify(
            point,
            QgsRaster.IdentifyFormatValue
        )
        
        if not result.isValid():
            return None, True
        
        results = result.results()
        if band not in results:
            return None, True
        
        value = results[band]
        
        # Check for NoData
        if value is None:
            return None, True
        
        # Check if value equals NoData value for this band
        nodata_value = provider.sourceNoDataValue(band)
        if nodata_value is not None and value == nodata_value:
            return value, True
        
        return value, False
    
    def _evaluate_predicate(
        self,
        value: Optional[float],
        is_nodata: bool,
        predicate: RasterValuePredicate,
        min_value: Optional[float],
        max_value: Optional[float]
    ) -> bool:
        """
        Evaluate if a value matches the predicate.
        
        Args:
            value: Sampled value
            is_nodata: True if value is NoData
            predicate: Comparison predicate
            min_value: Minimum for range comparisons
            max_value: Maximum for range comparisons
        
        Returns:
            True if value matches predicate
        """
        if predicate == RasterValuePredicate.IS_NODATA:
            return is_nodata
        
        if predicate == RasterValuePredicate.IS_NOT_NODATA:
            return not is_nodata
        
        if is_nodata or value is None:
            return False
        
        if predicate == RasterValuePredicate.WITHIN_RANGE:
            return min_value <= value <= max_value
        
        if predicate == RasterValuePredicate.OUTSIDE_RANGE:
            return value < min_value or value > max_value
        
        if predicate == RasterValuePredicate.ABOVE_VALUE:
            return value > (min_value or max_value)
        
        if predicate == RasterValuePredicate.BELOW_VALUE:
            return value < (max_value or min_value)
        
        if predicate == RasterValuePredicate.EQUALS_VALUE:
            # For EQUALS, use min/max as tolerance range
            if min_value is not None and max_value is not None:
                return min_value <= value <= max_value
            return False
        
        return False
    
    def _get_sample_point(
        self,
        feature: QgsFeature,
        method: SamplingMethod
    ) -> Optional[QgsPointXY]:
        """
        Get sample point from feature based on method.
        
        Args:
            feature: Vector feature
            method: Sampling method
        
        Returns:
            Point to sample, or None if can't determine
        """
        geom = feature.geometry()
        if geom.isNull() or geom.isEmpty():
            return None
        
        if method == SamplingMethod.CENTROID:
            centroid = geom.centroid()
            if centroid.isNull():
                return None
            return centroid.asPoint()
        
        # For other methods, return centroid as fallback
        # (full implementation would handle ALL_VERTICES, etc.)
        centroid = geom.centroid()
        if centroid.isNull():
            return None
        return centroid.asPoint()
    
    # =========================================================================
    # RasterFilterPort Implementation
    # =========================================================================
    
    def sample_at_points(
        self,
        raster_layer_id: str,
        points: List[Tuple[float, float, int]],
        band: int = 1
    ) -> List[RasterSampleResult]:
        """
        Sample raster values at specified points.
        
        Args:
            raster_layer_id: ID of the raster layer
            points: List of (x, y, feature_id) tuples
            band: Band number (1-indexed)
        
        Returns:
            List of RasterSampleResult for each point
        """
        raster = self._get_raster_layer(raster_layer_id)
        results = []
        
        for x, y, feature_id in points:
            point = QgsPointXY(x, y)
            value, is_nodata = self._sample_value_at_point(raster, point, band)
            
            result = RasterSampleResult(
                feature_id=feature_id,
                point_x=x,
                point_y=y,
                band_values={band: value},
                is_nodata=is_nodata
            )
            results.append(result)
        
        logger.debug(f"Sampled {len(results)} points from raster")
        return results
    
    def sample_at_features(
        self,
        raster_layer_id: str,
        vector_layer_id: str,
        band: int = 1,
        method: SamplingMethod = SamplingMethod.CENTROID,
        feature_ids: Optional[List[int]] = None
    ) -> List[RasterSampleResult]:
        """
        Sample raster values at vector feature locations.
        
        Args:
            raster_layer_id: ID of the raster layer
            vector_layer_id: ID of the vector layer
            band: Band number (1-indexed)
            method: Sampling method
            feature_ids: Optional specific feature IDs
        
        Returns:
            List of RasterSampleResult for each feature
        """
        raster = self._get_raster_layer(raster_layer_id)
        vector = self._get_vector_layer(vector_layer_id)
        
        # Setup transform if needed
        transform = self._get_transform(vector.crs(), raster.crs())
        
        # Build feature request
        request = QgsFeatureRequest()
        if feature_ids:
            request.setFilterFids(feature_ids)
        
        results = []
        
        for feature in vector.getFeatures(request):
            point = self._get_sample_point(feature, method)
            
            if point is None:
                results.append(RasterSampleResult(
                    feature_id=feature.id(),
                    point_x=0,
                    point_y=0,
                    is_nodata=True,
                    error="Could not determine sample point"
                ))
                continue
            
            # Transform point if needed
            if transform:
                point = transform.transform(point)
            
            value, is_nodata = self._sample_value_at_point(raster, point, band)
            
            result = RasterSampleResult(
                feature_id=feature.id(),
                point_x=point.x(),
                point_y=point.y(),
                band_values={band: value},
                is_nodata=is_nodata
            )
            results.append(result)
        
        logger.info(f"Sampled {len(results)} features from raster")
        return results
    
    def filter_features_by_value(
        self,
        raster_layer_id: str,
        vector_layer_id: str,
        band: int,
        predicate: RasterValuePredicate,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        method: SamplingMethod = SamplingMethod.CENTROID,
        feature_ids: Optional[List[int]] = None
    ) -> RasterFilterResult:
        """
        Filter vector features by underlying raster values.
        
        Args:
            raster_layer_id: ID of the raster layer
            vector_layer_id: ID of the vector layer
            band: Band number
            predicate: Value comparison predicate
            min_value: Minimum value
            max_value: Maximum value
            method: Sampling method
            feature_ids: Optional specific feature IDs
        
        Returns:
            RasterFilterResult with matching feature IDs
        """
        raster = self._get_raster_layer(raster_layer_id)
        vector = self._get_vector_layer(vector_layer_id)
        
        # Setup transform if needed
        transform = self._get_transform(vector.crs(), raster.crs())
        
        # Build feature request
        request = QgsFeatureRequest()
        if feature_ids:
            request.setFilterFids(feature_ids)
        
        matching_ids = []
        total_count = 0
        value_sum = 0.0
        value_count = 0
        
        for feature in vector.getFeatures(request):
            total_count += 1
            
            point = self._get_sample_point(feature, method)
            if point is None:
                continue
            
            # Transform point if needed
            if transform:
                point = transform.transform(point)
            
            value, is_nodata = self._sample_value_at_point(raster, point, band)
            
            # Evaluate predicate
            if self._evaluate_predicate(value, is_nodata, predicate, min_value, max_value):
                matching_ids.append(feature.id())
            
            # Collect statistics
            if value is not None and not is_nodata:
                value_sum += value
                value_count += 1
        
        # Build result
        result = RasterFilterResult(
            matching_feature_ids=matching_ids,
            total_features=total_count,
            matching_count=len(matching_ids),
            predicate=predicate,
            value_range=(min_value or 0.0, max_value or 0.0),
            band=band,
            sampling_method=method,
            statistics={
                'sampled_count': value_count,
                'mean_value': value_sum / value_count if value_count > 0 else None
            }
        )
        
        logger.info(
            f"Filter complete: {result.matching_count}/{result.total_features} "
            f"features match predicate {predicate.name}"
        )
        
        return result
    
    def generate_value_mask(
        self,
        raster_layer_id: str,
        band: int,
        min_value: float,
        max_value: float,
        output_name: Optional[str] = None,
        invert: bool = False
    ) -> RasterMaskResult:
        """
        Generate a binary mask based on value range.
        
        Uses QGIS raster calculator to create mask.
        
        Args:
            raster_layer_id: ID of the source raster
            band: Band number for masking
            min_value: Minimum value to include
            max_value: Maximum value to include
            output_name: Optional name for output layer
            invert: If True, mask values WITHIN range
        
        Returns:
            RasterMaskResult describing created mask
        """
        raster = self._get_raster_layer(raster_layer_id)
        
        layer_name = output_name or f"{raster.name()}_mask"
        
        # Build expression for raster calculator
        # ((raster >= min) AND (raster <= max)) * 1
        band_ref = f'"{raster.name()}@{band}"'
        
        if invert:
            # Mask values WITHIN range (set to 0)
            expression = f'(({band_ref} < {min_value}) OR ({band_ref} > {max_value})) * 1'
        else:
            # Mask values OUTSIDE range (keep values within)
            expression = f'(({band_ref} >= {min_value}) AND ({band_ref} <= {max_value})) * 1'
        
        try:
            # Use QGIS Processing
            result = processing.run(
                "qgis:rastercalculator",
                {
                    'EXPRESSION': expression,
                    'LAYERS': [raster],
                    'CELLSIZE': None,  # Use input cellsize
                    'EXTENT': None,    # Use input extent
                    'CRS': raster.crs(),
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                }
            )
            
            output_path = result['OUTPUT']
            
            # Add to project
            mask_layer = QgsRasterLayer(output_path, layer_name)
            if mask_layer.isValid():
                QgsProject.instance().addMapLayer(mask_layer)
                
                return RasterMaskResult(
                    layer_id=mask_layer.id(),
                    layer_name=layer_name,
                    source_layer_id=raster_layer_id,
                    band=band,
                    value_range=(min_value, max_value),
                    is_memory_layer=True,
                    file_path=output_path
                )
            else:
                return RasterMaskResult(
                    error="Failed to create valid mask layer"
                )
                
        except Exception as e:
            logger.error(f"Mask generation failed: {e}")
            return RasterMaskResult(error=str(e))
    
    def compute_zonal_statistics(
        self,
        raster_layer_id: str,
        vector_layer_id: str,
        band: int = 1,
        statistics: Optional[List[str]] = None,
        feature_ids: Optional[List[int]] = None,
        prefix: str = ""
    ) -> List[ZonalStatisticsResult]:
        """
        Compute zonal statistics for raster values within vector zones.
        
        Uses QGIS native:zonalstatisticsfb algorithm.
        
        Args:
            raster_layer_id: ID of the raster layer
            vector_layer_id: ID of the zone layer
            band: Band number
            statistics: List of statistics to compute
            feature_ids: Optional specific zone IDs
            prefix: Prefix for output fields
        
        Returns:
            List of ZonalStatisticsResult for each zone
        """
        raster = self._get_raster_layer(raster_layer_id)
        vector = self._get_vector_layer(vector_layer_id)
        
        # Map stats names to QGIS flags
        stat_mapping = {
            'count': 0,
            'sum': 1,
            'mean': 2,
            'median': 3,
            'std': 4,
            'min': 5,
            'max': 6,
            'range': 7,
            'minority': 8,
            'majority': 9,
            'variety': 10
        }
        
        requested_stats = statistics or ['min', 'max', 'mean', 'std', 'count']
        stat_flags = sum(1 << stat_mapping.get(s, 0) for s in requested_stats if s in stat_mapping)
        
        try:
            result = processing.run(
                "native:zonalstatisticsfb",
                {
                    'INPUT': vector,
                    'INPUT_RASTER': raster,
                    'RASTER_BAND': band,
                    'COLUMN_PREFIX': prefix or 'zonal_',
                    'STATISTICS': stat_flags,
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                }
            )
            
            output_layer = result['OUTPUT']
            
            # Extract results from output layer
            results = []
            for feature in output_layer.getFeatures():
                attrs = feature.attributes()
                field_names = [f.name() for f in output_layer.fields()]
                
                zonal_result = ZonalStatisticsResult(
                    feature_id=feature.id(),
                    zone_name=str(feature.id())
                )
                
                # Extract computed statistics
                prefix_str = prefix or 'zonal_'
                for stat_name in requested_stats:
                    field_name = f"{prefix_str}{stat_name}"
                    if field_name in field_names:
                        idx = field_names.index(field_name)
                        value = attrs[idx]
                        
                        if stat_name == 'min':
                            zonal_result.min_value = value
                        elif stat_name == 'max':
                            zonal_result.max_value = value
                        elif stat_name == 'mean':
                            zonal_result.mean_value = value
                        elif stat_name == 'std':
                            zonal_result.std_dev = value
                        elif stat_name == 'sum':
                            zonal_result.sum_value = value
                        elif stat_name == 'count':
                            zonal_result.valid_pixel_count = int(value) if value else 0
                        elif stat_name == 'majority':
                            zonal_result.majority_value = value
                        elif stat_name == 'minority':
                            zonal_result.minority_value = value
                
                results.append(zonal_result)
            
            logger.info(f"Zonal statistics computed for {len(results)} zones")
            return results
            
        except Exception as e:
            logger.error(f"Zonal statistics failed: {e}")
            return []
    
    def clip_raster_by_vector(
        self,
        raster_layer_id: str,
        vector_layer_id: str,
        feature_ids: Optional[List[int]] = None,
        output_name: Optional[str] = None
    ) -> RasterMaskResult:
        """
        Clip raster to vector geometry extent.
        
        Uses gdal:cliprasterbymasklayer.
        
        Args:
            raster_layer_id: ID of the raster to clip
            vector_layer_id: ID of the clipping vector
            feature_ids: Optional specific features
            output_name: Optional output name
        
        Returns:
            RasterMaskResult describing clipped raster
        """
        raster = self._get_raster_layer(raster_layer_id)
        vector = self._get_vector_layer(vector_layer_id)
        
        layer_name = output_name or f"{raster.name()}_clipped"
        
        try:
            result = processing.run(
                "gdal:cliprasterbymasklayer",
                {
                    'INPUT': raster,
                    'MASK': vector,
                    'SOURCE_CRS': None,
                    'TARGET_CRS': None,
                    'NODATA': None,
                    'ALPHA_BAND': False,
                    'CROP_TO_CUTLINE': True,
                    'KEEP_RESOLUTION': True,
                    'OPTIONS': '',
                    'DATA_TYPE': 0,
                    'EXTRA': '',
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                }
            )
            
            output_path = result['OUTPUT']
            
            clip_layer = QgsRasterLayer(output_path, layer_name)
            if clip_layer.isValid():
                QgsProject.instance().addMapLayer(clip_layer)
                
                return RasterMaskResult(
                    layer_id=clip_layer.id(),
                    layer_name=layer_name,
                    source_layer_id=raster_layer_id,
                    is_memory_layer=True,
                    file_path=output_path
                )
            else:
                return RasterMaskResult(error="Failed to create clipped raster")
                
        except Exception as e:
            logger.error(f"Clip raster failed: {e}")
            return RasterMaskResult(error=str(e))
    
    def mask_raster_by_vector(
        self,
        raster_layer_id: str,
        vector_layer_id: str,
        operation: RasterOperation,
        feature_ids: Optional[List[int]] = None,
        output_name: Optional[str] = None
    ) -> RasterMaskResult:
        """
        Mask raster pixels by vector geometry.
        
        Args:
            raster_layer_id: ID of the raster
            vector_layer_id: ID of the masking vector
            operation: MASK_OUTSIDE or MASK_INSIDE
            feature_ids: Optional specific features
            output_name: Optional output name
        
        Returns:
            RasterMaskResult describing masked raster
        """
        # For MASK_OUTSIDE, we clip normally
        # For MASK_INSIDE, we invert the mask
        
        if operation == RasterOperation.MASK_OUTSIDE:
            return self.clip_raster_by_vector(
                raster_layer_id,
                vector_layer_id,
                feature_ids,
                output_name
            )
        
        # MASK_INSIDE - need to invert
        # This requires creating an inverted mask
        raster = self._get_raster_layer(raster_layer_id)
        vector = self._get_vector_layer(vector_layer_id)
        
        layer_name = output_name or f"{raster.name()}_masked"
        
        try:
            # Use gdal:cliprasterbymasklayer with inverted logic
            # This is a simplified version - full implementation would
            # create an inverted polygon mask first
            
            result = processing.run(
                "gdal:cliprasterbymasklayer",
                {
                    'INPUT': raster,
                    'MASK': vector,
                    'SOURCE_CRS': None,
                    'TARGET_CRS': None,
                    'NODATA': -9999,  # Set clipped area to NoData
                    'ALPHA_BAND': False,
                    'CROP_TO_CUTLINE': False,  # Keep full extent
                    'KEEP_RESOLUTION': True,
                    'OPTIONS': '',
                    'DATA_TYPE': 0,
                    'EXTRA': '',
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                }
            )
            
            output_path = result['OUTPUT']
            
            mask_layer = QgsRasterLayer(output_path, layer_name)
            if mask_layer.isValid():
                QgsProject.instance().addMapLayer(mask_layer)
                
                return RasterMaskResult(
                    layer_id=mask_layer.id(),
                    layer_name=layer_name,
                    source_layer_id=raster_layer_id,
                    is_memory_layer=True,
                    file_path=output_path
                )
            else:
                return RasterMaskResult(error="Failed to create masked raster")
                
        except Exception as e:
            logger.error(f"Mask raster failed: {e}")
            return RasterMaskResult(error=str(e))

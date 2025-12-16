# -*- coding: utf-8 -*-
"""
FilterMate - Raster Sampling Task

Asynchronous QgsTask for sampling raster values at vector feature locations.
Supports point sampling, zonal statistics, and batch operations.

Classes:
    RasterSamplingTask: Async task for raster sampling operations
"""

import logging
from typing import Dict, List, Optional, Any, Callable
from enum import Enum

from qgis.core import (
    QgsTask,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsField,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsMessageLog,
    Qgis,
)
from qgis.PyQt.QtCore import QVariant, pyqtSignal, QObject

# Local imports
from ..backends.raster_backend import RasterBackend, RasterBackendError, GDAL_AVAILABLE


logger = logging.getLogger(__name__)


class SamplingMode(Enum):
    """Raster sampling operation modes."""
    POINT_SAMPLE = "point_sample"       # Sample at point locations
    ZONAL_STATS = "zonal_stats"         # Calculate zonal statistics for polygons
    POINT_STATS = "point_stats"         # Sample + calculate stats for points


class RasterSamplingTask(QgsTask):
    """
    Asynchronous task for sampling raster values at vector feature locations.
    
    This task runs in a background thread to avoid blocking the QGIS UI.
    It supports:
    - Point sampling (single band value at each point)
    - Zonal statistics (min, max, mean, std for polygons)
    - Batch processing with progress reporting
    
    Signals:
        sampling_completed: Emitted when sampling is complete
        sampling_failed: Emitted if sampling fails
        
    Example:
        >>> task = RasterSamplingTask(
        ...     "Sample elevations",
        ...     vector_layer=points_layer,
        ...     raster_path="/path/to/dem.tif",
        ...     output_field="elevation",
        ...     band=1
        ... )
        >>> task.taskCompleted.connect(on_complete)
        >>> QgsApplication.taskManager().addTask(task)
    """
    
    # Result signals (emitted on main thread via finished())
    # Note: QgsTask doesn't support custom signals directly,
    # we use a signal emitter helper instead
    
    def __init__(
        self,
        description: str,
        vector_layer: QgsVectorLayer,
        raster_path: str,
        output_field: str = "raster_value",
        band: int = 1,
        mode: SamplingMode = SamplingMode.POINT_SAMPLE,
        sampling_method: str = RasterBackend.SAMPLE_NEAREST,
        feature_ids: Optional[List[int]] = None,
        stats_fields: Optional[List[str]] = None,
        on_complete: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ):
        """
        Initialize the raster sampling task.
        
        Args:
            description: Task description for progress dialog
            vector_layer: Vector layer to sample from (points or polygons)
            raster_path: Path to the raster file
            output_field: Name of field to store sampled values
            band: Raster band number (1-based)
            mode: Sampling mode (POINT_SAMPLE, ZONAL_STATS, POINT_STATS)
            sampling_method: Method for point sampling ('nearest', 'bilinear', 'cubic')
            feature_ids: Optional list of feature IDs to process (all if None)
            stats_fields: For ZONAL_STATS, which stats to compute
                         (default: ['min', 'max', 'mean', 'count'])
            on_complete: Callback function called with results on success
            on_error: Callback function called with error message on failure
        """
        super().__init__(description, QgsTask.CanCancel)
        
        self.vector_layer = vector_layer
        self.raster_path = raster_path
        self.output_field = output_field
        self.band = band
        self.mode = mode
        self.sampling_method = sampling_method
        self.feature_ids = feature_ids
        self.stats_fields = stats_fields or ['min', 'max', 'mean', 'count']
        self.on_complete = on_complete
        self.on_error = on_error
        
        # Results storage
        self.results: Dict[int, Any] = {}
        self.error_message: Optional[str] = None
        self.processed_count: int = 0
        self.total_count: int = 0
        
        # Validate inputs
        if not GDAL_AVAILABLE:
            self.error_message = "GDAL is not available for raster operations"
    
    def run(self) -> bool:
        """
        Execute the sampling task.
        
        This runs in a background thread.
        
        Returns:
            True if successful, False otherwise
        """
        if self.error_message:
            return False
        
        try:
            return self._execute_sampling()
        except RasterBackendError as e:
            self.error_message = f"Raster backend error: {str(e)}"
            logger.error(self.error_message)
            return False
        except Exception as e:
            self.error_message = f"Unexpected error: {str(e)}"
            logger.exception(self.error_message)
            return False
    
    def _execute_sampling(self) -> bool:
        """Execute the actual sampling logic."""
        
        # Open raster backend
        with RasterBackend(self.raster_path) as raster:
            
            # Determine features to process
            if self.feature_ids is not None:
                self.total_count = len(self.feature_ids)
                features = [self.vector_layer.getFeature(fid) for fid in self.feature_ids]
            else:
                self.total_count = self.vector_layer.featureCount()
                features = list(self.vector_layer.getFeatures())
            
            if self.total_count == 0:
                self.results = {}
                return True
            
            layer_crs = self.vector_layer.crs()
            
            # Process each feature
            for i, feature in enumerate(features):
                # Check for cancellation
                if self.isCanceled():
                    return False
                
                # Update progress
                self.setProgress((i + 1) / self.total_count * 100)
                
                fid = feature.id()
                geom = feature.geometry()
                
                if geom.isNull() or geom.isEmpty():
                    self.results[fid] = None
                    continue
                
                # Execute based on mode
                if self.mode == SamplingMode.POINT_SAMPLE:
                    self.results[fid] = self._sample_point(raster, geom, layer_crs)
                    
                elif self.mode == SamplingMode.ZONAL_STATS:
                    self.results[fid] = self._compute_zonal_stats(raster, geom, layer_crs)
                    
                elif self.mode == SamplingMode.POINT_STATS:
                    # For points, sample the value
                    value = self._sample_point(raster, geom, layer_crs)
                    self.results[fid] = {'value': value}
                
                self.processed_count += 1
            
        logger.info(
            f"Raster sampling completed: {self.processed_count}/{self.total_count} features"
        )
        return True
    
    def _sample_point(
        self, 
        raster: RasterBackend, 
        geom: QgsGeometry,
        layer_crs
    ) -> Optional[float]:
        """Sample a single point."""
        # For non-point geometries, use centroid
        if geom.type() != 0:  # Not a point
            geom = geom.centroid()
        
        return raster.sample_point(
            geom, 
            band=self.band, 
            method=self.sampling_method,
            source_crs=layer_crs
        )
    
    def _compute_zonal_stats(
        self, 
        raster: RasterBackend, 
        geom: QgsGeometry,
        layer_crs
    ) -> Dict[str, Optional[float]]:
        """Compute zonal statistics for a polygon."""
        stats = raster.zonal_stats(geom, band=self.band, source_crs=layer_crs)
        
        # Filter to requested stats
        return {k: v for k, v in stats.items() if k in self.stats_fields}
    
    def finished(self, result: bool) -> None:
        """
        Called when the task completes.
        
        This runs on the main thread and is safe for UI updates.
        
        Args:
            result: True if task succeeded, False otherwise
        """
        if result:
            QgsMessageLog.logMessage(
                f"Raster sampling completed: {self.processed_count} features processed",
                "FilterMate",
                Qgis.Info
            )
            if self.on_complete:
                self.on_complete(self.results)
        else:
            error_msg = self.error_message or "Unknown error during raster sampling"
            QgsMessageLog.logMessage(
                f"Raster sampling failed: {error_msg}",
                "FilterMate",
                Qgis.Warning
            )
            if self.on_error:
                self.on_error(error_msg)
    
    def cancel(self) -> None:
        """Cancel the task."""
        logger.info("Raster sampling task cancelled by user")
        super().cancel()
    
    def get_results(self) -> Dict[int, Any]:
        """
        Get the sampling results.
        
        Returns:
            Dictionary mapping feature ID to sampled value(s)
        """
        return self.results
    
    def get_progress_info(self) -> Dict[str, int]:
        """
        Get progress information.
        
        Returns:
            Dictionary with 'processed' and 'total' counts
        """
        return {
            'processed': self.processed_count,
            'total': self.total_count
        }


class RasterValueUpdaterTask(QgsTask):
    """
    Task to update vector layer attributes with sampled raster values.
    
    This task samples raster values and directly updates the vector layer
    with new attribute values. It handles field creation if needed.
    
    Example:
        >>> task = RasterValueUpdaterTask(
        ...     "Add elevations",
        ...     vector_layer=points_layer,
        ...     raster_path="/path/to/dem.tif",
        ...     field_name="elevation"
        ... )
        >>> QgsApplication.taskManager().addTask(task)
    """
    
    def __init__(
        self,
        description: str,
        vector_layer: QgsVectorLayer,
        raster_path: str,
        field_name: str,
        band: int = 1,
        sampling_method: str = RasterBackend.SAMPLE_NEAREST,
        create_field: bool = True,
        on_complete: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ):
        """
        Initialize the updater task.
        
        Args:
            description: Task description
            vector_layer: Vector layer to update
            raster_path: Path to raster file
            field_name: Name of field to store values
            band: Raster band number
            sampling_method: Sampling method
            create_field: Create field if it doesn't exist
            on_complete: Success callback
            on_error: Error callback
        """
        super().__init__(description, QgsTask.CanCancel)
        
        self.vector_layer = vector_layer
        self.raster_path = raster_path
        self.field_name = field_name
        self.band = band
        self.sampling_method = sampling_method
        self.create_field = create_field
        self.on_complete = on_complete
        self.on_error = on_error
        
        self.error_message: Optional[str] = None
        self.updated_count: int = 0
        self.field_index: int = -1
    
    def run(self) -> bool:
        """Execute the update task."""
        if not GDAL_AVAILABLE:
            self.error_message = "GDAL is not available"
            return False
        
        try:
            # Check/create field (must be done carefully for thread safety)
            self.field_index = self.vector_layer.fields().indexOf(self.field_name)
            
            if self.field_index < 0 and self.create_field:
                # Field creation must happen on main thread
                # We'll handle this in finished()
                self.error_message = "FIELD_NEEDED"
                return False
            
            if self.field_index < 0:
                self.error_message = f"Field '{self.field_name}' not found"
                return False
            
            # Sample all features
            with RasterBackend(self.raster_path) as raster:
                layer_crs = self.vector_layer.crs()
                
                self.vector_layer.startEditing()
                
                for feature in self.vector_layer.getFeatures():
                    if self.isCanceled():
                        self.vector_layer.rollBack()
                        return False
                    
                    geom = feature.geometry()
                    if geom.isNull() or geom.isEmpty():
                        continue
                    
                    # Sample point or centroid
                    if geom.type() != 0:
                        geom = geom.centroid()
                    
                    value = raster.sample_point(
                        geom,
                        band=self.band,
                        method=self.sampling_method,
                        source_crs=layer_crs
                    )
                    
                    if value is not None:
                        self.vector_layer.changeAttributeValue(
                            feature.id(),
                            self.field_index,
                            value
                        )
                        self.updated_count += 1
                
                self.vector_layer.commitChanges()
            
            return True
            
        except Exception as e:
            self.error_message = str(e)
            if self.vector_layer.isEditable():
                self.vector_layer.rollBack()
            return False
    
    def finished(self, result: bool) -> None:
        """Handle task completion."""
        if result:
            QgsMessageLog.logMessage(
                f"Updated {self.updated_count} features with raster values",
                "FilterMate",
                Qgis.Info
            )
            if self.on_complete:
                self.on_complete(self.updated_count)
        else:
            if self.error_message == "FIELD_NEEDED":
                # Create field on main thread and retry
                self._create_field_and_retry()
            else:
                QgsMessageLog.logMessage(
                    f"Raster update failed: {self.error_message}",
                    "FilterMate",
                    Qgis.Warning
                )
                if self.on_error:
                    self.on_error(self.error_message)
    
    def _create_field_and_retry(self) -> None:
        """Create the field on the main thread and schedule a new task."""
        from qgis.core import QgsApplication
        
        # Create field
        field = QgsField(self.field_name, QVariant.Double)
        self.vector_layer.startEditing()
        self.vector_layer.addAttribute(field)
        self.vector_layer.commitChanges()
        
        # Create and run new task
        new_task = RasterValueUpdaterTask(
            self.description(),
            self.vector_layer,
            self.raster_path,
            self.field_name,
            self.band,
            self.sampling_method,
            create_field=False,
            on_complete=self.on_complete,
            on_error=self.on_error,
        )
        QgsApplication.taskManager().addTask(new_task)
